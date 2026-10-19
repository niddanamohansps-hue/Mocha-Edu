import uuid

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import Program
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole

from .models import Instructor, StaffMember

PASSWORD = "Pass1234!"


class StaffFixtureMixin:
    """Tenant + user fixtures for staff API tests (mirrors examinations/tests.py)."""

    SCHEMA_NAME = "staff_p04_school"
    DOMAIN = "staff-p04.localhost"
    TENANT_SCHEMAS = ["staff_p04_school", "staff_p04_other"]

    def _build_school(self, schema_name, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=f"School {schema_name}")
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, codenames=None, owner=False):
        user = User.objects.create_user(username=username, email=f"{username}@p04.test", password=PASSWORD)
        with tenant_context(self.school):
            if owner:
                role = Role.objects.get(slug="owner")
            else:
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

    def _make_staff(self, first, last, employee_id, school=None):
        school = school or self.school
        with tenant_context(school):
            profile = Profile.objects.create(first_name=first, last_name=last)
            return StaffMember.objects.create(profile=profile, employee_id=employee_id, designation="Teacher")

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=self.TENANT_SCHEMAS):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="staff_").delete()
        User.objects.filter(username__startswith="p04_").delete()

    def setUp(self):
        self.addCleanup(self._cleanup)
        self.school = self._build_school(self.SCHEMA_NAME, self.DOMAIN)
        self.member = self._make_staff("Asha", "Rao", "EMP-P04-001")

        self.owner = self._build_user("staff_owner", owner=True)
        self.viewer = self._build_user("staff_viewer", codenames=["view_staff"])
        self.manager = self._build_user("staff_manager", codenames=["view_staff", "add_staff", "change_staff"])
        self.activator = self._build_user("staff_activator", codenames=["view_staff", "add_staff", "activate_staff_portal"])
        self.stranger = self._build_user("staff_stranger", codenames=[])

        with tenant_context(self.school):
            Role.objects.get_or_create(
                slug="accountant", defaults={"name": "Accountant", "is_system_role": False}
            )


class StaffApiTests(StaffFixtureMixin, TransactionTestCase):

    # --- Authentication and RBAC -------------------------------------------

    def test_unauthenticated_request_is_rejected(self):
        resp = APIClient().get("/api/staff/members/", HTTP_HOST=self.DOMAIN)
        self.assertIn(resp.status_code, (401, 403))

    def test_user_without_view_staff_cannot_list_staff(self):
        client = self._client_as(self.stranger, self.DOMAIN)
        self.assertEqual(client.get("/api/staff/members/", HTTP_HOST=self.DOMAIN).status_code, 403)

    def test_viewer_can_list_but_cannot_create_staff(self):
        client = self._client_as(self.viewer, self.DOMAIN)
        self.assertEqual(client.get("/api/staff/members/", HTTP_HOST=self.DOMAIN).status_code, 200)
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name="New", last_name="Hire")
        resp = client.post(
            "/api/staff/members/",
            {"profile": str(profile.id), "employee_id": "EMP-P04-002", "designation": "Clerk"},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    # --- Validation and update ----------------------------------------------

    def test_manager_creates_staff_member(self):
        client = self._client_as(self.manager, self.DOMAIN)
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name="Ravi", last_name="Iyer")
        resp = client.post(
            "/api/staff/members/",
            {"profile": str(profile.id), "employee_id": "EMP-P04-003", "designation": "Clerk"},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.assertTrue(StaffMember.objects.filter(employee_id="EMP-P04-003", is_active=True).exists())

    def test_duplicate_employee_id_rejected(self):
        client = self._client_as(self.manager, self.DOMAIN)
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name="Dup", last_name="Id")
        resp = client.post(
            "/api/staff/members/",
            {"profile": str(profile.id), "employee_id": "EMP-P04-001", "designation": "Clerk"},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("employee_id", resp.data)

    def test_update_changes_designation_and_profile_name_but_not_employee_id(self):
        client = self._client_as(self.manager, self.DOMAIN)
        resp = client.patch(
            f"/api/staff/members/{self.member.id}/",
            {"designation": "Senior Teacher", "first_name": "Asha K", "employee_id": "HIJACK-1"},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            member = StaffMember.objects.get(id=self.member.id)
            self.assertEqual(member.designation, "Senior Teacher")
            self.assertEqual(member.profile.first_name, "Asha K")
            self.assertEqual(member.employee_id, "EMP-P04-001", "employee_id must be read-only")

    # --- Instructor onboarding -----------------------------------------------

    def test_instructor_onboarding_creates_linked_instructor_record(self):
        client = self._client_as(self.manager, self.DOMAIN)
        resp = client.post(
            "/api/staff/onboard-instructor/",
            {
                "first_name": "Meera",
                "last_name": "Das",
                "gender": "female",
                "specialization": "Physics",
                "experience_years": 4,
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data["employee_id"].startswith("INS-"))
        with tenant_context(self.school):
            instructor = Instructor.objects.get(id=resp.data["instructor_id"])
            self.assertEqual(instructor.specialization, "Physics")
            self.assertEqual(instructor.staff_member.id, resp.data["staff_id"])

    def test_instructor_onboarding_requires_add_staff(self):
        client = self._client_as(self.viewer, self.DOMAIN)
        resp = client.post(
            "/api/staff/onboard-instructor/",
            {"first_name": "No", "last_name": "Right", "gender": "male"},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    # --- Portal activation ---------------------------------------------------

    def test_activation_rejects_instructor_and_student_roles(self):
        client = self._client_as(self.activator, self.DOMAIN)
        for slug in ("instructor", "student"):
            with self.subTest(role=slug):
                resp = client.post(
                    "/api/staff/activate-staff/",
                    {
                        "staff_id": str(self.member.id),
                        "username": f"p04_{slug}_try",
                        "password": "Init-Pass-123",
                        "role_slug": slug,
                    },
                    HTTP_HOST=self.DOMAIN,
                    format="json",
                )
                self.assertEqual(resp.status_code, 400)

    def test_activation_rejects_owner_role(self):
        """REGRESSION: owner must never be grantable through the generic staff activation
        endpoint. The serializer's own comment says owner is blocked, but the code
        previously allowed it, letting an activate_staff_portal holder mint an owner."""
        client = self._client_as(self.activator, self.DOMAIN)
        resp = client.post(
            "/api/staff/activate-staff/",
            {
                "staff_id": str(self.member.id),
                "username": "p04_owner_try",
                "password": "Init-Pass-123",
                "role_slug": "owner",
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        with tenant_context(self.school):
            self.assertFalse(
                UserRole.objects.filter(user__username__startswith="p04_owner_try", role__slug="owner").exists()
            )

    def test_activation_with_valid_role_creates_account_and_role(self):
        client = self._client_as(self.activator, self.DOMAIN)
        resp = client.post(
            "/api/staff/activate-staff/",
            {
                "staff_id": str(self.member.id),
                "username": "p04_accountant",
                "password": "Init-Pass-123",
                "role_slug": "accountant",
                "email": "p04_accountant@p04.test",
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(User.objects.filter(username__startswith="p04_accountant").exists())
        with tenant_context(self.school):
            self.assertTrue(
                UserRole.objects.filter(user__username__startswith="p04_accountant", role__slug="accountant").exists()
            )

    def test_activation_requires_activate_staff_portal(self):
        client = self._client_as(self.manager, self.DOMAIN)
        resp = client.post(
            "/api/staff/activate-staff/",
            {
                "staff_id": str(self.member.id),
                "username": "p04_blocked",
                "password": "Init-Pass-123",
                "role_slug": "accountant",
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    # --- Tenant isolation ------------------------------------------------------

    def test_staff_member_in_one_school_is_invisible_to_another(self):
        other = self._build_school("staff_p04_other", "staff-p04-other.localhost")
        try:
            self._make_staff("Other", "School", "EMP-OTHER-1", school=other)
            client = self._client_as(self.viewer, self.DOMAIN)
            resp = client.get("/api/staff/members/", HTTP_HOST=self.DOMAIN)
            self.assertEqual(resp.status_code, 200)
            rows = resp.data["results"] if "results" in resp.data else resp.data
            ids = {r["employee_id"] for r in rows}
            self.assertIn("EMP-P04-001", ids)
            self.assertNotIn("EMP-OTHER-1", ids)
        finally:
            connection.set_schema_to_public()
