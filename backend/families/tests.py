import uuid as uuid_module

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import AcademicLevel, Program, Section
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from students.models import Student, StudentLevel

from .models import Parent, StudentParentRelation


class FamilyFixtureMixin:
    """Mirrors students/examinations/notifications tests.py exactly."""

    SCHEMA_NAME = "family_test_school"
    DOMAIN = "familytest.localhost"

    def _build_school(self, schema_name=None, domain=None, name="Family Test School"):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, role_slug, domain=None):
        domain = domain or self.DOMAIN
        user = User.objects.create_user(
            username=username, email=f"{username}@familytest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(
                slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=role)
        return user

    def _client_as(self, user, password="Pass1234!", domain=None):
        domain = domain or self.DOMAIN
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"username": user.username, "password": password}, HTTP_HOST=domain
        )
        assert resp.status_code == 200, resp.data
        return client

    def _give_role_only(self, user, codenames):
        with tenant_context(self.school):
            unique_suffix = uuid_module.uuid4().hex[:8]
            role = Role.objects.create(
                name=f"custom-{unique_suffix}", slug=f"custom-{unique_suffix}", is_system_role=False
            )
            role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.filter(user=user).delete()
            UserRole.objects.create(user=user, role=role)
        return role

    def _make_student(self, enrollment_id, first_name, last_name):
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name=first_name, last_name=last_name)
            student = Student.objects.create(
                profile=profile, enrollment_id=enrollment_id, status="active"
            )
            StudentLevel.objects.create(
                student=student, level=self.level, section=self.section,
                academic_year="2026", is_current=True,
            )
        return student

    def _make_parent(self, first_name, last_name):
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name=first_name, last_name=last_name)
            parent = Parent.objects.create(profile=profile, occupation="Engineer")
        return parent

    def _link(self, student, parent, relation_type="father", is_primary=True):
        with tenant_context(self.school):
            return StudentParentRelation.objects.create(
                student=student, parent=parent, relation_type=relation_type,
                is_primary_contact=is_primary,
            )

    def setUp(self):
        self.school = self._build_school()

        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code="FAMHS")
            self.level = AcademicLevel.objects.create(program=program, name="Grade 5", order=1)
            self.section = Section.objects.create(level=self.level, name="A", capacity=40)

        self.owner_user = self._build_user("fam_owner", "owner")

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)


class ParentListEndpointTest(FamilyFixtureMixin, TransactionTestCase):
    """
    Focused regression coverage for the families.ParentSerializer.get_children()
    ImportError bug (GET /api/families/parents/ returned HTTP 500 on every
    request before the fix - it imported a `StudentSerializer` that does
    not exist anywhere in students.serializers).
    """

    def test_parent_list_returns_200_not_500(self):
        """The core regression: this must not raise ImportError/500 at all."""
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            student = self._make_student("ENR-FAM-1", "Riya", "Sharma")
        self._link(student, parent)

        client = self._client_as(self.owner_user)
        resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_children_field_serializes_successfully(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            student = self._make_student("ENR-FAM-1", "Riya", "Sharma")
        self._link(student, parent, relation_type="mother", is_primary=True)

        client = self._client_as(self.owner_user)
        resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.data)

        row = next(r for r in resp.data["results"] if r["id"] == str(parent.id))
        self.assertEqual(len(row["children"]), 1)
        child = row["children"][0]
        self.assertEqual(child["relation_type"], "mother")
        self.assertTrue(child["is_primary"])
        self.assertEqual(child["student"]["enrollment_id"], "ENR-FAM-1")
        self.assertEqual(child["student"]["full_name"], "Riya Sharma")
        self.assertEqual(child["student"]["id"], str(student.id))

    def test_parent_with_multiple_children_returns_all_of_them(self):
        with tenant_context(self.school):
            parent = self._make_parent("Vikram", "Mehta")
            student_a = self._make_student("ENR-FAM-A", "Aarav", "Mehta")
            student_b = self._make_student("ENR-FAM-B", "Diya", "Mehta")
        self._link(student_a, parent, relation_type="father", is_primary=True)
        self._link(student_b, parent, relation_type="father", is_primary=False)

        client = self._client_as(self.owner_user)
        resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)
        row = next(r for r in resp.data["results"] if r["id"] == str(parent.id))

        enrollment_ids = {c["student"]["enrollment_id"] for c in row["children"]}
        self.assertEqual(enrollment_ids, {"ENR-FAM-A", "ENR-FAM-B"})

    def test_unrelated_parents_children_are_not_exposed(self):
        """A parent with no StudentParentRelation rows must show an empty
        children list, never another parent's children."""
        with tenant_context(self.school):
            parent_a = self._make_parent("Asha", "Sharma")
            parent_b = self._make_parent("Unrelated", "Guardian")
            student = self._make_student("ENR-FAM-1", "Riya", "Sharma")
        self._link(student, parent_a)

        client = self._client_as(self.owner_user)
        resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)

        row_a = next(r for r in resp.data["results"] if r["id"] == str(parent_a.id))
        row_b = next(r for r in resp.data["results"] if r["id"] == str(parent_b.id))
        self.assertEqual(len(row_a["children"]), 1)
        self.assertEqual(row_b["children"], [])

    def test_pagination_envelope_and_results_intact(self):
        """Confirms the pagination work (commit 71ef0a0) is unaffected by
        this fix - response must still be the standard DRF envelope, not a
        bare array, and the created parent must be among the results."""
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")

        client = self._client_as(self.owner_user)
        resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("count", resp.data)
        self.assertIn("next", resp.data)
        self.assertIn("previous", resp.data)
        self.assertIn("results", resp.data)
        self.assertIn(str(parent.id), [r["id"] for r in resp.data["results"]])

    def test_tenant_isolation_preserved(self):
        """A second tenant's parents/children must never appear in this
        tenant's response."""
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            student = self._make_student("ENR-FAM-1", "Riya", "Sharma")
        self._link(student, parent)

        other_school = self._build_school(schema_name="family_test_school_b", domain="familytestb.localhost")
        try:
            with tenant_context(other_school):
                other_profile = Profile.objects.create(first_name="Other", last_name="Parent")
                other_parent = Parent.objects.create(profile=other_profile, occupation="Doctor")
                other_parent_id = other_parent.id

            client = self._client_as(self.owner_user)
            resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)
            returned_ids = {r["id"] for r in resp.data["results"]}

            self.assertIn(str(parent.id), returned_ids)
            self.assertNotIn(str(other_parent_id), returned_ids)
        finally:
            connection.set_schema_to_public()
            other_school.delete(force_drop=True)

    def test_unauthenticated_request_rejected(self):
        client = APIClient()
        resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)
        self.assertIn(resp.status_code, (401, 403))

    def test_non_owner_without_permission_is_rejected(self):
        """
        ParentViewSet is now gated by the existing, already-seeded Families
        permissions (view_family/add_family/change_family/delete_family)
        rather than the nonexistent "manage_students" codename. A non-owner
        role holding none of these permissions must still be rejected.
        """
        limited_user = self._build_user("fam_limited", "staff")
        self._give_role_only(limited_user, [])
        client = self._client_as(limited_user)
        resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)


class ParentViewSetRBACTest(FamilyFixtureMixin, TransactionTestCase):
    """
    Focused RBAC coverage for ParentViewSet's action-specific permissions
    (view_family/add_family/change_family/delete_family), replacing the
    previously-unsatisfiable "manage_students" check.
    """

    def _make_unlinked_profile(self, first_name="New", last_name="Parent"):
        with tenant_context(self.school):
            return Profile.objects.create(first_name=first_name, last_name=last_name)

    def test_view_family_allows_list_and_retrieve(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
        user = self._build_user("fam_viewer", "staff")
        self._give_role_only(user, ["view_family"])
        client = self._client_as(user)

        resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

        resp = client.get(f"/api/families/parents/{parent.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_view_family_does_not_allow_write_actions(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
        profile = self._make_unlinked_profile()
        user = self._build_user("fam_viewer2", "staff")
        self._give_role_only(user, ["view_family"])
        client = self._client_as(user)

        resp = client.post(
            "/api/families/parents/",
            {"profile": str(profile.id), "occupation": "Engineer"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.patch(
            f"/api/families/parents/{parent.id}/",
            {"occupation": "Doctor"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.delete(f"/api/families/parents/{parent.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_add_family_allows_create_only(self):
        profile = self._make_unlinked_profile()
        with tenant_context(self.school):
            other_parent = self._make_parent("Other", "Parent")
        user = self._build_user("fam_creator", "staff")
        self._give_role_only(user, ["add_family"])
        client = self._client_as(user)

        resp = client.post(
            "/api/families/parents/",
            {"profile": str(profile.id), "occupation": "Engineer"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = client.patch(
            f"/api/families/parents/{other_parent.id}/",
            {"occupation": "Doctor"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.delete(f"/api/families/parents/{other_parent.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_change_family_allows_update_only(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
        profile = self._make_unlinked_profile()
        user = self._build_user("fam_updater", "staff")
        self._give_role_only(user, ["change_family"])
        client = self._client_as(user)

        resp = client.patch(
            f"/api/families/parents/{parent.id}/",
            {"occupation": "Doctor"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = client.post(
            "/api/families/parents/",
            {"profile": str(profile.id), "occupation": "Engineer"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.delete(f"/api/families/parents/{parent.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_delete_family_allows_destroy_only(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            other_parent = self._make_parent("Other", "Parent")
        profile = self._make_unlinked_profile()
        user = self._build_user("fam_deleter", "staff")
        self._give_role_only(user, ["delete_family"])
        client = self._client_as(user)

        resp = client.post(
            "/api/families/parents/",
            {"profile": str(profile.id), "occupation": "Engineer"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.patch(
            f"/api/families/parents/{other_parent.id}/",
            {"occupation": "Doctor"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.delete(f"/api/families/parents/{parent.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 204, resp.data)


class StudentParentRelationViewSetRBACTest(FamilyFixtureMixin, TransactionTestCase):
    """Same action-specific RBAC coverage, for StudentParentRelationViewSet."""

    def test_view_family_allows_list_and_retrieve(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            student = self._make_student("ENR-REL-1", "Riya", "Sharma")
        relation = self._link(student, parent)
        user = self._build_user("rel_viewer", "staff")
        self._give_role_only(user, ["view_family"])
        client = self._client_as(user)

        resp = client.get("/api/families/relations/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

        resp = client.get(f"/api/families/relations/{relation.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_view_family_does_not_allow_write_actions(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            student = self._make_student("ENR-REL-1", "Riya", "Sharma")
        relation = self._link(student, parent)
        user = self._build_user("rel_viewer2", "staff")
        self._give_role_only(user, ["view_family"])
        client = self._client_as(user)

        resp = client.patch(
            f"/api/families/relations/{relation.id}/",
            {"relation_type": "mother"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.delete(f"/api/families/relations/{relation.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_add_family_allows_create_only(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            student = self._make_student("ENR-REL-1", "Riya", "Sharma")
        relation = self._link(student, parent)
        user = self._build_user("rel_creator", "staff")
        self._give_role_only(user, ["add_family"])
        client = self._client_as(user)

        with tenant_context(self.school):
            other_student = self._make_student("ENR-REL-2", "Vikram", "Sharma")
        resp = client.post(
            "/api/families/relations/",
            {
                "student": str(other_student.id), "parent": str(parent.id),
                "relation_type": "guardian", "is_primary_contact": False,
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = client.patch(
            f"/api/families/relations/{relation.id}/",
            {"relation_type": "mother"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.delete(f"/api/families/relations/{relation.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_change_family_allows_update_only(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            student = self._make_student("ENR-REL-1", "Riya", "Sharma")
        relation = self._link(student, parent)
        user = self._build_user("rel_updater", "staff")
        self._give_role_only(user, ["change_family"])
        client = self._client_as(user)

        resp = client.patch(
            f"/api/families/relations/{relation.id}/",
            {"relation_type": "mother"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        with tenant_context(self.school):
            other_student = self._make_student("ENR-REL-2", "Vikram", "Sharma")
        resp = client.post(
            "/api/families/relations/",
            {
                "student": str(other_student.id), "parent": str(parent.id),
                "relation_type": "guardian", "is_primary_contact": False,
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.delete(f"/api/families/relations/{relation.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_delete_family_allows_destroy_only(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            student = self._make_student("ENR-REL-1", "Riya", "Sharma")
            other_student = self._make_student("ENR-REL-2", "Vikram", "Sharma")
        relation = self._link(student, parent)
        other_relation = self._link(other_student, parent, relation_type="guardian", is_primary=False)
        user = self._build_user("rel_deleter", "staff")
        self._give_role_only(user, ["delete_family"])
        client = self._client_as(user)

        resp = client.patch(
            f"/api/families/relations/{other_relation.id}/",
            {"relation_type": "mother"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

        resp = client.delete(f"/api/families/relations/{relation.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 204, resp.data)


class FamilyPermissionBypassTest(FamilyFixtureMixin, TransactionTestCase):
    """
    Confirms the owner-role and superuser bypasses in HasPermission still
    work unchanged after switching ParentViewSet/StudentParentRelationViewSet
    to action-specific Families permissions - these bypasses are evaluated
    before any codename lookup, so they must be unaffected by this fix.
    """

    def test_owner_bypass_allows_all_actions(self):
        with tenant_context(self.school):
            parent = self._make_parent("Asha", "Sharma")
            profile = Profile.objects.create(first_name="New", last_name="Parent")
        client = self._client_as(self.owner_user)

        self.assertEqual(
            client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN).status_code, 200
        )
        resp = client.post(
            "/api/families/parents/",
            {"profile": str(profile.id), "occupation": "Engineer"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        new_parent_id = resp.data["id"]

        resp = client.patch(
            f"/api/families/parents/{new_parent_id}/",
            {"occupation": "Doctor"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200)

        resp = client.delete(f"/api/families/parents/{new_parent_id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 204)

    def test_superuser_bypass_allows_access_without_any_role(self):
        superuser = User.objects.create_user(
            username="fam_superuser", email="fam_superuser@familytest.com", password="Pass1234!"
        )
        superuser.is_superuser = True
        superuser.save()

        client = self._client_as(superuser)
        resp = client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
