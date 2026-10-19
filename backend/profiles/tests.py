import uuid

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Domain, Organization
from profiles.models import InstitutionProfile, Profile
from roles.models import Permission, Role, UserRole

PASSWORD = "Pass1234!"


class ProfilesFixtureMixin:
    """Tenant + user fixtures for profile API tests (mirrors examinations/tests.py)."""

    SCHEMA_NAME = "prof_p04_school"
    DOMAIN = "profiles-p04.localhost"
    TENANT_SCHEMAS = ["prof_p04_school", "prof_p04_other"]

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=self.TENANT_SCHEMAS):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="prof_").delete()

    def _build_school(self, schema_name, domain, name):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, codenames=None):
        user = User.objects.create_user(username=username, email=f"{username}@p04.test", password=PASSWORD)
        with tenant_context(self.school):
            slug = f"p04-{uuid.uuid4().hex[:10]}"
            role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
            role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
        return user

    def _client_as(self, user, host):
        client = APIClient()
        resp = client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD}, HTTP_HOST=host)
        assert resp.status_code == 200, resp.data
        return client

    def setUp(self):
        self.addCleanup(self._cleanup)
        self.school = self._build_school(self.SCHEMA_NAME, self.DOMAIN, "Profiles School")
        self.alice = self._build_user("prof_alice")
        self.bob = self._build_user("prof_bob")
        self.viewer = self._build_user("prof_viewer", codenames=["view_institution_profile"])
        self.editor = self._build_user(
            "prof_editor", codenames=["view_institution_profile", "change_institution_profile"]
        )
        self.stranger = self._build_user("prof_stranger", codenames=[])
        with tenant_context(self.school):
            self.alice_profile = Profile.objects.get(user_id=self.alice.id)
            self.bob_profile = Profile.objects.get(user_id=self.bob.id)
            self.alice_profile.first_name = "Alice"
            self.alice_profile.save(update_fields=["first_name"])
            self.bob_profile.first_name = "Bob"
            self.bob_profile.save(update_fields=["first_name"])


class MyProfileApiTests(ProfilesFixtureMixin, TransactionTestCase):

    def test_unauthenticated_request_is_rejected(self):
        resp = APIClient().get("/api/profiles/me/", HTTP_HOST=self.DOMAIN)
        self.assertIn(resp.status_code, (401, 403))

    def test_get_returns_only_the_callers_own_profile(self):
        client = self._client_as(self.alice, self.DOMAIN)
        resp = client.get("/api/profiles/me/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["first_name"], "Alice")
        self.assertEqual(str(resp.data["user_id"]), str(self.alice.id))
        self.assertNotIn("Bob", str(resp.data))

    def test_patch_updates_own_profile(self):
        client = self._client_as(self.alice, self.DOMAIN)
        resp = client.patch("/api/profiles/me/", {"phone": "9000000001"}, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            self.alice_profile.refresh_from_db()
            self.assertEqual(self.alice_profile.phone, "9000000001")

    def test_patch_rejects_overlong_name(self):
        client = self._client_as(self.alice, self.DOMAIN)
        resp = client.patch(
            "/api/profiles/me/", {"first_name": "x" * 51}, HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("first_name", resp.data)

    def test_cannot_reassign_or_modify_another_users_profile_via_body(self):
        """IDOR: /me/ takes no profile id. Body fields that identify another user
        (user_id, id) are read-only and must be ignored; Bob's profile stays intact."""
        client = self._client_as(self.alice, self.DOMAIN)
        resp = client.patch(
            "/api/profiles/me/",
            {"id": str(self.bob_profile.id), "user_id": str(self.bob.id), "first_name": "Hacked"},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            self.bob_profile.refresh_from_db()
            self.alice_profile.refresh_from_db()
            self.assertEqual(self.bob_profile.first_name, "Bob")
            self.assertEqual(self.alice_profile.first_name, "Hacked")
            self.assertEqual(self.alice_profile.user_id, self.alice.id)

    def test_access_without_profile_returns_404_and_does_not_auto_create(self):
        newcomer = self._build_user("prof_newcomer")
        with tenant_context(self.school):
            Profile.objects.filter(user_id=newcomer.id).delete()
        client = self._client_as(newcomer, self.DOMAIN)
        resp = client.get("/api/profiles/me/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)
        with tenant_context(self.school):
            self.assertFalse(Profile.objects.filter(user_id=newcomer.id).exists())

    def test_cross_tenant_user_cannot_authenticate_or_inject_profile(self):
        other = self._build_school("prof_p04_other", "profiles-p04-other.localhost", "Other School")
        other_user = User.objects.create_user(
            username="prof_outsider", email="outsider@other.test", password=PASSWORD
        )
        try:
            with tenant_context(other):
                slug = f"other-{uuid.uuid4().hex[:10]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                UserRole.objects.create(user=other_user, role=role)
                Profile.objects.create(user_id=other_user.id, first_name="Outsider", local_username="outsider_local")

            client = APIClient()

            # 1. Login into school A with School B credentials must be rejected
            resp = client.post(
                "/api/auth/login/",
                {"username": other_user.username, "password": PASSWORD},
                HTTP_HOST=self.DOMAIN,
            )
            self.assertIn(resp.status_code, (400, 401))

            # 2. Even if force-authenticated, calling GET /api/profiles/me/ on School A returns 404
            client.force_authenticate(user=other_user)
            resp = client.get("/api/profiles/me/", HTTP_HOST=self.DOMAIN)
            self.assertEqual(resp.status_code, 404)

            # 3. Assert NO profile was auto-created in School A
            with tenant_context(self.school):
                self.assertFalse(Profile.objects.filter(user_id=other_user.id).exists())

            # 4. Calling PATCH /api/profiles/me/ on School A returns 404 and does not create a profile
            resp = client.patch("/api/profiles/me/", {"first_name": "Injected"}, HTTP_HOST=self.DOMAIN)
            self.assertEqual(resp.status_code, 404)
            with tenant_context(self.school):
                self.assertFalse(Profile.objects.filter(user_id=other_user.id).exists())
        finally:
            connection.set_schema_to_public()

    def test_same_user_gets_separate_profile_per_school(self):
        other = self._build_school("prof_p04_other", "profiles-p04-other.localhost", "Other School")
        try:
            with tenant_context(other):
                from roles.models import Role as R
                slug = f"p04-{uuid.uuid4().hex[:10]}"
                role = R.objects.create(name=slug, slug=slug, is_system_role=False)
                UserRole.objects.create(user=self.alice, role=role)
                Profile.objects.create(user_id=self.alice.id, first_name="Alice in Other")

            client_a = self._client_as(self.alice, self.DOMAIN)
            profile_a = client_a.get("/api/profiles/me/", HTTP_HOST=self.DOMAIN).data["id"]
            client_b = self._client_as(self.alice, "profiles-p04-other.localhost")
            profile_b = client_b.get("/api/profiles/me/", HTTP_HOST="profiles-p04-other.localhost").data["id"]
            self.assertNotEqual(profile_a, profile_b)
        finally:
            connection.set_schema_to_public()


class InstitutionProfileApiTests(ProfilesFixtureMixin, TransactionTestCase):

    def test_get_requires_view_institution_profile(self):
        client = self._client_as(self.stranger, self.DOMAIN)
        self.assertEqual(client.get("/api/profiles/institution/", HTTP_HOST=self.DOMAIN).status_code, 403)

    def test_viewer_reads_institution_name_from_tenant(self):
        client = self._client_as(self.viewer, self.DOMAIN)
        resp = client.get("/api/profiles/institution/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["name"], "Profiles School")

    def test_patch_requires_change_institution_profile(self):
        client = self._client_as(self.viewer, self.DOMAIN)
        resp = client.patch(
            "/api/profiles/institution/", {"tagline": "Nope"}, HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_editor_updates_tagline_and_name_persists_to_organization(self):
        client = self._client_as(self.editor, self.DOMAIN)
        resp = client.patch(
            "/api/profiles/institution/",
            {"tagline": "Learning Together", "name": "Renamed Profiles School"},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            self.assertEqual(
                InstitutionProfile.objects.get(organization_id=self.school.id).tagline, "Learning Together"
            )
        connection.set_schema_to_public()
        self.assertEqual(Organization.objects.get(id=self.school.id).name, "Renamed Profiles School")

    def test_institution_profile_is_scoped_to_the_requesting_school(self):
        other = self._build_school("prof_p04_other", "profiles-p04-other.localhost", "Other School")
        try:
            with tenant_context(other):
                from roles.models import Role as R
                # Creating any role assignment in the other tenant provisions its own InstitutionProfile.
                user = User.objects.get(username="prof_viewer")
                slug = f"p04-{uuid.uuid4().hex[:10]}"
                role = R.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename="view_institution_profile"))
                UserRole.objects.create(user=user, role=role)
                InstitutionProfile.objects.get_or_create(organization_id=other.id)

            client = self._client_as(self.viewer, "profiles-p04-other.localhost")
            resp = client.get("/api/profiles/institution/", HTTP_HOST="profiles-p04-other.localhost")
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data["name"], "Other School")
            self.assertNotEqual(resp.data["name"], "Profiles School")
        finally:
            connection.set_schema_to_public()
