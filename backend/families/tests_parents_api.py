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


class ParentsApiTests(TransactionTestCase):
    SCHEMA_A = "parents_api_school_a"
    DOMAIN_A = "parents-a.localhost"
    SCHEMA_B = "parents_api_school_b"
    DOMAIN_B = "parents-b.localhost"

    def _build_school(self, schema_name, domain, name):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, school, username, codenames=None, is_owner=False):
        user = User.objects.create_user(
            username=username, email=f"{username}@parentstest.test", password="Pass1234!"
        )
        with tenant_context(school):
            if is_owner:
                role, _ = Role.objects.get_or_create(
                    slug="owner", defaults={"name": "Owner", "is_system_role": True}
                )
            else:
                unique_suffix = uuid_module.uuid4().hex[:8]
                role = Role.objects.create(
                    name=f"custom-{unique_suffix}",
                    slug=f"custom-{unique_suffix}",
                    is_system_role=False,
                )
                if codenames:
                    role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.create(user=user, role=role)
        return user

    def _client_as(self, user, domain=None):
        domain = domain or self.DOMAIN_A
        client = APIClient()
        resp = client.post(
            "/api/auth/login/",
            {"username": user.username, "password": "Pass1234!"},
            HTTP_HOST=domain,
        )
        assert resp.status_code == 200, resp.data
        return client

    def setUp(self):
        self.school_a = self._build_school(self.SCHEMA_A, self.DOMAIN_A, "Parents School A")
        self.school_b = self._build_school(self.SCHEMA_B, self.DOMAIN_B, "Parents School B")

        with tenant_context(self.school_a):
            program = Program.objects.create(name="Primary", code="PRIM-A")
            self.level_a = AcademicLevel.objects.create(program=program, name="Class 1", order=1)
            self.section_a = Section.objects.create(level=self.level_a, name="A", capacity=30)

        with tenant_context(self.school_b):
            program_b = Program.objects.create(name="Primary B", code="PRIM-B")
            self.level_b = AcademicLevel.objects.create(program=program_b, name="Class 1 B", order=1)
            self.section_b = Section.objects.create(level=self.level_b, name="B", capacity=30)

        self.owner_a = self._build_user(self.school_a, "owner_a", is_owner=True)
        self.staff_viewer_a = self._build_user(self.school_a, "viewer_a", codenames=["view_family"])
        self.staff_manager_a = self._build_user(
            self.school_a,
            "manager_a",
            codenames=["view_family", "add_family", "change_family", "delete_family"],
        )
        self.owner_b = self._build_user(self.school_b, "owner_b", is_owner=True)

    def tearDown(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA_A, self.SCHEMA_B]):
            school.delete(force_drop=True)
        User.objects.filter(username__endswith="_a").delete()
        User.objects.filter(username__endswith="_b").delete()

    def _make_student(self, school, level, section, enrollment_id, first_name, last_name):
        with tenant_context(school):
            profile = Profile.objects.create(first_name=first_name, last_name=last_name)
            student = Student.objects.create(
                profile=profile, enrollment_id=enrollment_id, status="active"
            )
            StudentLevel.objects.create(
                student=student, level=level, section=section,
                academic_year="2026", is_current=True,
            )
        return student

    def test_create_parent_with_flat_profile_fields(self):
        """Creates a parent and linked profile in one transaction using flat fields."""
        client = self._client_as(self.staff_manager_a)
        payload = {
            "first_name": "Suresh",
            "middle_name": "Kumar",
            "last_name": "Patel",
            "phone": "9876543210",
            "email": "suresh.patel@example.test",
            "gender": "male",
            "address": "42 MG Road, Ahmedabad",
            "occupation": "Pediatrician",
            "office_address": "City Hospital",
            "income_level": "High",
        }
        res = client.post("/api/families/parents/", payload, format="json", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res.status_code, 201, res.data)
        parent_id = res.data["id"]

        with tenant_context(self.school_a):
            parent = Parent.objects.select_related("profile").get(id=parent_id)
            self.assertEqual(parent.occupation, "Pediatrician")
            self.assertEqual(parent.profile.first_name, "Suresh")
            self.assertEqual(parent.profile.last_name, "Patel")
            self.assertEqual(parent.profile.phone, "9876543210")
            self.assertEqual(parent.profile.email, "suresh.patel@example.test")

        # Read shape preserves profile_details and children
        self.assertIn("profile_details", res.data)
        self.assertEqual(res.data["profile_details"]["first_name"], "Suresh")
        self.assertEqual(res.data["profile_details"]["email"], "suresh.patel@example.test")
        self.assertIn("children", res.data)
        self.assertEqual(res.data["children"], [])

    def test_create_parent_with_nested_profile_dict(self):
        """Creates parent with nested profile dictionary."""
        client = self._client_as(self.staff_manager_a)
        payload = {
            "profile": {
                "first_name": "Sunita",
                "last_name": "Deshmukh",
                "phone": "9123456789",
                "email": "sunita@example.test",
                "gender": "female",
            },
            "occupation": "Professor",
        }
        res = client.post("/api/families/parents/", payload, format="json", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["profile_details"]["first_name"], "Sunita")
        self.assertEqual(res.data["profile_details"]["last_name"], "Deshmukh")
        self.assertEqual(res.data["profile_details"]["email"], "sunita@example.test")

    def test_create_parent_requires_first_and_last_name(self):
        """Missing first_name or last_name without an existing profile raises validation error."""
        client = self._client_as(self.staff_manager_a)
        payload = {
            "phone": "9876543210",
            "occupation": "Banker",
        }
        res = client.post("/api/families/parents/", payload, format="json", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res.status_code, 400)
        self.assertIn("first_name", res.data)
        self.assertIn("last_name", res.data)

    def test_edit_parent_and_profile_fields(self):
        """Editing parent updates both Parent and Profile fields atomically."""
        client = self._client_as(self.staff_manager_a)
        create_res = client.post(
            "/api/families/parents/",
            {
                "first_name": "Ramesh",
                "last_name": "Verma",
                "phone": "9000000001",
                "occupation": "Clerk",
            },
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        parent_id = create_res.data["id"]

        patch_res = client.patch(
            f"/api/families/parents/{parent_id}/",
            {
                "first_name": "Rameshwar",
                "phone": "9000000002",
                "email": "rameshwar@example.test",
                "occupation": "Senior Manager",
            },
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(patch_res.status_code, 200, patch_res.data)
        self.assertEqual(patch_res.data["occupation"], "Senior Manager")
        self.assertEqual(patch_res.data["profile_details"]["first_name"], "Rameshwar")
        self.assertEqual(patch_res.data["profile_details"]["phone"], "9000000002")
        self.assertEqual(patch_res.data["profile_details"]["email"], "rameshwar@example.test")

    def test_link_and_unlink_child(self):
        """Links child to parent and unlinks cleanly."""
        student = self._make_student(self.school_a, self.level_a, self.section_a, "ENR-001", "Aarav", "Patel")
        client = self._client_as(self.staff_manager_a)

        parent_res = client.post(
            "/api/families/parents/",
            {"first_name": "Kishore", "last_name": "Patel", "occupation": "Lawyer"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        parent_id = parent_res.data["id"]

        # Link child
        link_payload = {
            "student": str(student.id),
            "parent": parent_id,
            "relation_type": "father",
            "is_primary_contact": True,
            "can_pickup": True,
        }
        link_res = client.post("/api/families/relations/", link_payload, format="json", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(link_res.status_code, 201, link_res.data)
        relation_id = link_res.data["id"]
        self.assertEqual(link_res.data["student_name"], "Aarav Patel")
        self.assertEqual(link_res.data["parent_name"], "Kishore Patel")
        self.assertEqual(link_res.data["student_enrollment_id"], "ENR-001")

        # Verify parent retrieve now shows this child
        detail_res = client.get(f"/api/families/parents/{parent_id}/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(len(detail_res.data["children"]), 1)
        self.assertEqual(detail_res.data["children"][0]["relation_type"], "father")
        self.assertTrue(detail_res.data["children"][0]["is_primary"])

        # Unlink child
        del_res = client.delete(f"/api/families/relations/{relation_id}/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(del_res.status_code, 204)

        detail_res2 = client.get(f"/api/families/parents/{parent_id}/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(len(detail_res2.data["children"]), 0)

    def test_duplicate_link_prevented(self):
        """Linking the same child to the same parent twice is blocked with 400 validation error."""
        student = self._make_student(self.school_a, self.level_a, self.section_a, "ENR-002", "Diya", "Nair")
        client = self._client_as(self.staff_manager_a)

        parent_res = client.post(
            "/api/families/parents/",
            {"first_name": "Radha", "last_name": "Nair"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        parent_id = parent_res.data["id"]

        link_payload = {
            "student": str(student.id),
            "parent": parent_id,
            "relation_type": "mother",
            "is_primary_contact": True,
        }
        res1 = client.post("/api/families/relations/", link_payload, format="json", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res1.status_code, 201)

        # Duplicate link attempt
        res2 = client.post("/api/families/relations/", link_payload, format="json", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res2.status_code, 400)
        self.assertIn("already linked", str(res2.data).lower())

    def test_primary_contact_switch(self):
        """Setting a new primary contact unsets the old primary contact for that student."""
        student = self._make_student(self.school_a, self.level_a, self.section_a, "ENR-003", "Kabir", "Mehta")
        client = self._client_as(self.staff_manager_a)

        father_res = client.post(
            "/api/families/parents/",
            {"first_name": "Anil", "last_name": "Mehta"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        mother_res = client.post(
            "/api/families/parents/",
            {"first_name": "Bhavna", "last_name": "Mehta"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        father_id = father_res.data["id"]
        mother_id = mother_res.data["id"]

        # Link Father as primary
        res_f = client.post(
            "/api/families/relations/",
            {"student": str(student.id), "parent": father_id, "relation_type": "father", "is_primary_contact": True},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(res_f.status_code, 201)
        rel_father_id = res_f.data["id"]

        # Link Mother as primary
        res_m = client.post(
            "/api/families/relations/",
            {"student": str(student.id), "parent": mother_id, "relation_type": "mother", "is_primary_contact": True},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(res_m.status_code, 201)

        with tenant_context(self.school_a):
            rel_father = StudentParentRelation.objects.get(id=rel_father_id)
            self.assertFalse(rel_father.is_primary_contact, "Father must be unset as primary contact")

            rel_mother = StudentParentRelation.objects.get(id=res_m.data["id"])
            self.assertTrue(rel_mother.is_primary_contact, "Mother must now be primary contact")

    def test_search_and_student_filter(self):
        """Tests search by name and phone, and filtering by ?student=<id>."""
        student_x = self._make_student(self.school_a, self.level_a, self.section_a, "ENR-004", "Varun", "Kapoor")
        student_y = self._make_student(self.school_a, self.level_a, self.section_a, "ENR-005", "Tanvi", "Joshi")
        client = self._client_as(self.staff_manager_a)

        p1_res = client.post(
            "/api/families/parents/",
            {"first_name": "Rajesh", "last_name": "Kapoor", "phone": "9988776655"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        p2_res = client.post(
            "/api/families/parents/",
            {"first_name": "Deepak", "last_name": "Joshi", "phone": "9123123123"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        p1_id = p1_res.data["id"]
        p2_id = p2_res.data["id"]

        # Link student_x to p1
        client.post(
            "/api/families/relations/",
            {"student": str(student_x.id), "parent": p1_id, "relation_type": "father"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )

        # Search by name
        res_name = client.get("/api/families/parents/?search=Rajesh", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res_name.status_code, 200)
        self.assertEqual(len(res_name.data["results"]), 1)
        self.assertEqual(res_name.data["results"][0]["id"], p1_id)

        # Search by phone
        res_phone = client.get("/api/families/parents/?search=9123123123", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res_phone.status_code, 200)
        self.assertEqual(len(res_phone.data["results"]), 1)
        self.assertEqual(res_phone.data["results"][0]["id"], p2_id)

        # Filter by student
        res_student = client.get(f"/api/families/parents/?student={student_x.id}", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res_student.status_code, 200)
        self.assertEqual(len(res_student.data["results"]), 1)
        self.assertEqual(res_student.data["results"][0]["id"], p1_id)

    def test_permission_denials(self):
        """Enforces view_family, add_family, change_family, delete_family RBAC."""
        anon_client = APIClient()
        # 1. Unauthenticated -> 401
        res = anon_client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN_A)
        self.assertIn(res.status_code, [401, 403])

        # 2. Viewer can view but cannot create (403)
        viewer_client = self._client_as(self.staff_viewer_a)
        res_view = viewer_client.get("/api/families/parents/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res_view.status_code, 200)

        res_create = viewer_client.post(
            "/api/families/parents/",
            {"first_name": "No", "last_name": "Perm"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(res_create.status_code, 403)

        # 3. Manager can create
        mgr_client = self._client_as(self.staff_manager_a)
        res_create_ok = mgr_client.post(
            "/api/families/parents/",
            {"first_name": "Has", "last_name": "Perm"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(res_create_ok.status_code, 201)
        created_id = res_create_ok.data["id"]

        # 4. Viewer cannot update or delete
        res_patch = viewer_client.patch(
            f"/api/families/parents/{created_id}/",
            {"occupation": "Hacker"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(res_patch.status_code, 403)

        res_del = viewer_client.delete(f"/api/families/parents/{created_id}/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(res_del.status_code, 403)

    def test_tenant_isolation(self):
        """Parents and student links in School A are invisible and immutable in School B."""
        client_a = self._client_as(self.owner_a, domain=self.DOMAIN_A)
        client_b = self._client_as(self.owner_b, domain=self.DOMAIN_B)

        p_a = client_a.post(
            "/api/families/parents/",
            {"first_name": "TenantA", "last_name": "Parent"},
            format="json",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(p_a.status_code, 201)
        parent_a_id = p_a.data["id"]

        # School B list should be empty
        list_b = client_b.get("/api/families/parents/", HTTP_HOST=self.DOMAIN_B)
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(len(list_b.data["results"]), 0)

        # School B retrieve returns 404
        ret_b = client_b.get(f"/api/families/parents/{parent_a_id}/", HTTP_HOST=self.DOMAIN_B)
        self.assertEqual(ret_b.status_code, 404)

        # School B update returns 404
        patch_b = client_b.patch(
            f"/api/families/parents/{parent_a_id}/",
            {"occupation": "Cross Tenant Edit"},
            format="json",
            HTTP_HOST=self.DOMAIN_B,
        )
        self.assertEqual(patch_b.status_code, 404)

