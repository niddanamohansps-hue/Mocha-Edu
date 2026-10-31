import datetime
import uuid as uuid_module
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, Program, Section, Subject
from accounts.models import User
from attendance.models import AttendanceSession, StudentAttendance
from core.models import AuditLog
from examinations.models import ExamMark, ExamSchedule, Examination, ExamType, GradeBoundary
from examinations.services import publish_examination
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from students.models import Student, StudentLevel
from timetable.models import Period, Room, TimetableEntry

from .services import user_can_access_child


class ParentPortalFixtureMixin:
    """Mirrors attendance/timetable/examinations tests.py exactly."""

    SCHEMA_NAME = "pp_test_school"
    DOMAIN = "pptest.localhost"

    def _build_school(self, schema_name=None, domain=None, name="Parent Portal Test School"):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, role_slug):
        user = User.objects.create_user(
            username=username, email=f"{username}@pptest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(
                slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=role)
        return user

    def _give_role_only(self, user, codenames):
        """Replaces the user's role(s) with a single custom role carrying
        exactly these permissions - system roles seed with zero permissions
        except owner, so every test must grant explicitly (the Attendance
        permission-fixture mistake is not repeated here)."""
        with tenant_context(self.school):
            role = Role.objects.create(
                name=f"custom-{uuid_module.uuid4().hex[:8]}", is_system_role=False
            )
            role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.filter(user=user).delete()
            UserRole.objects.create(user=user, role=role)
        return role

    def _client_as(self, user, password="Pass1234!"):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"username": user.username, "password": password}, HTTP_HOST=self.DOMAIN
        )
        assert resp.status_code == 200, resp.data
        return client

    def _make_parent(self, username, first_name, last_name):
        """Builds an already-activated Parent (User + Profile + Parent +
        'parent' UserRole) directly via ORM - activation itself is tested
        separately, end-to-end, through the real API in
        ParentPortalActivationTests."""
        user = User.objects.create_user(
            username=username, email=f"{username}@pptest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            profile = Profile.objects.create(
                user_id=user.id, first_name=first_name, last_name=last_name
            )
            parent = Parent.objects.create(profile=profile, occupation="Engineer")
            parent_role, _ = Role.objects.get_or_create(
                slug="parent", defaults={"name": "Parent", "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=parent_role)
        return user, parent

    def _make_student(self, enrollment_id, first_name, last_name, section):
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name=first_name, last_name=last_name)
            student = Student.objects.create(
                profile=profile, enrollment_id=enrollment_id, status="active"
            )
            StudentLevel.objects.create(
                student=student, level=section.level, section=section,
                academic_year="2026", is_current=True,
            )
        return student

    def setUp(self):
        self.school = self._build_school()

        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code="HSPP")
            level = AcademicLevel.objects.create(program=program, name="Grade 10", order=1)
            self.section_a = Section.objects.create(level=level, name="A", capacity=40)
            self.subject = Subject.objects.create(level=level, name="Math", code="MTHPP")

            self.period = Period.objects.create(
                academic_year="2026", name="Period 1", order=1,
                start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
            )
            self.room = Room.objects.create(name="Room PP1", capacity=30)

            TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                day_of_week=0, period=self.period, room=self.room,
            )

            self.exam_type = ExamType.objects.create(name="Mid-Term", order=1)
            self.examination = Examination.objects.create(
                academic_year="2026", name="Mid-Term 2026", exam_type=self.exam_type,
                start_date=datetime.date(2026, 6, 1), end_date=datetime.date(2026, 6, 10),
            )
            GradeBoundary.objects.create(
                academic_year="2026", min_percentage=Decimal("0"), max_percentage=Decimal("100"),
                grade_label="A", grade_point=Decimal("4.0"),
            )
            self.exam_schedule = ExamSchedule.objects.create(
                examination=self.examination, academic_year="2026", subject=self.subject,
                section=self.section_a, date=datetime.date(2026, 6, 2),
                start_time=datetime.time(9, 0), end_time=datetime.time(11, 0),
                max_marks=Decimal("100"), pass_marks=Decimal("40"),
            )

        self.student1 = self._make_student("ENR-PP-1", "Sam", "Pupil", self.section_a)
        self.student2 = self._make_student("ENR-PP-2", "Sue", "Pupil", self.section_a)
        self.student3 = self._make_student("ENR-PP-3", "Otto", "Other", self.section_a)

        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 6, 2)
            )
            StudentAttendance.objects.create(session=session, student=self.student1, status="present")
            StudentAttendance.objects.create(session=session, student=self.student2, status="absent")

            ExamMark.objects.create(
                exam_schedule=self.exam_schedule, student=self.student1, marks_obtained=Decimal("80")
            )
            ExamMark.objects.create(
                exam_schedule=self.exam_schedule, student=self.student2, marks_obtained=Decimal("30")
            )
            publish_examination(self.examination)

        self.parent1_user, self.parent1 = self._make_parent("pp_parent1", "Pat", "Guardian")
        self.parent2_user, self.parent2 = self._make_parent("pp_parent2", "Pam", "Guardian")

        with tenant_context(self.school):
            StudentParentRelation.objects.create(
                student=self.student1, parent=self.parent1, relation_type="mother", is_primary_contact=True
            )
            StudentParentRelation.objects.create(
                student=self.student2, parent=self.parent1, relation_type="mother"
            )
            StudentParentRelation.objects.create(
                student=self.student3, parent=self.parent2, relation_type="father", is_primary_contact=True
            )

        self.non_parent_user = self._build_user("pp_staff", "staff")
        self.owner_user = self._build_user("pp_owner", "owner")

        # A second, separate tenant to prove cross-tenant isolation.
        self.school2 = self._build_school(
            schema_name="pp_test_school2", domain="pptest2.localhost", name="Parent Portal Test School 2"
        )
        with tenant_context(self.school2):
            program2 = Program.objects.create(name="Other School", code="OSPP")
            level2 = AcademicLevel.objects.create(program=program2, name="Grade 1", order=1)
            section2 = Section.objects.create(level=level2, name="A", capacity=10)
            profile2 = Profile.objects.create(first_name="Cross", last_name="Tenant")
            self.other_tenant_student = Student.objects.create(
                profile=profile2, enrollment_id="ENR-OT-1", status="active"
            )
            StudentLevel.objects.create(
                student=self.other_tenant_student, level=level2, section=section2,
                academic_year="2026", is_current=True,
            )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        self.school2.delete(force_drop=True)


class ParentPortalStructureTests(ParentPortalFixtureMixin, TransactionTestCase):
    def test_parent_portal_app_has_no_models(self):
        from django.apps import apps as django_apps

        config = django_apps.get_app_config("parent_portal")
        self.assertEqual(list(config.get_models()), [])


class ParentPortalActivationTests(ParentPortalFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.fresh_profile = Profile.objects.create(first_name="Fresh", last_name="Parent")
            self.fresh_parent = Parent.objects.create(profile=self.fresh_profile, occupation="Doctor")

    def _activate(self, client, username, parent_id=None):
        return client.post(
            "/api/families/activate-parent/",
            {
                "parent_id": str(parent_id or self.fresh_parent.id),
                "username": username,
                "password": "TempPass123!",
            },
            HTTP_HOST=self.DOMAIN,
        )

    def test_parent_role_seeded(self):
        with tenant_context(self.school):
            self.assertTrue(Role.objects.filter(slug="parent", is_system_role=True).exists())

    def test_parent_role_default_permissions(self):
        """New parent roles get only the limited, approved defaults (see roles.signals); results,
        fee data and payment initiation require explicit owner configuration."""
        with tenant_context(self.school):
            role = Role.objects.get(slug="parent")
            self.assertEqual(
                set(role.permissions.values_list("codename", flat=True)),
                {
                    "view_own_children", "view_child_attendance", "view_child_timetable",
                    "view_calendar_events", "view_child_homework", "view_child_ptm",
                },
            )

    def test_parent_portal_permissions_seeded(self):
        """
        Originally asserted exactly the 4 Parent Portal-milestone codenames;
        the Fees milestone deliberately added a 5th ('view_child_fees') to
        this same "Parent Portal" module (see fees design report S12/S17),
        so this expectation is updated to match - not a regression. The online-payment
        milestone likewise added 'pay_child_fees' to the same module.
        """
        with tenant_context(self.school):
            codenames = set(
                Permission.objects.filter(module="Parent Portal").values_list("codename", flat=True)
            )
            self.assertEqual(
                codenames,
                {
                    "view_own_children", "view_child_attendance", "view_child_timetable",
                    "view_child_results", "view_child_fees", "pay_child_fees",
                },
            )

    def test_activation_creates_user_and_links_profile(self):
        client = self._client_as(self.owner_user)
        resp = self._activate(client, "freshparent1")
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.fresh_profile.refresh_from_db()
            self.assertIsNotNone(self.fresh_profile.user_id)
            self.assertEqual(self.fresh_profile.local_username, "freshparent1")

    def test_activation_assigns_parent_role(self):
        client = self._client_as(self.owner_user)
        resp = self._activate(client, "freshparent2")
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.fresh_profile.refresh_from_db()
            self.assertTrue(
                UserRole.objects.filter(user_id=self.fresh_profile.user_id, role__slug="parent").exists()
            )

    def test_activation_does_not_create_duplicate_profile(self):
        client = self._client_as(self.owner_user)
        resp = self._activate(client, "freshparent3")
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.fresh_profile.refresh_from_db()
            matching = Profile.objects.filter(user_id=self.fresh_profile.user_id)
            self.assertEqual(matching.count(), 1)
            self.assertEqual(matching.first().id, self.fresh_profile.id)

    def test_activation_does_not_create_duplicate_user(self):
        client = self._client_as(self.owner_user)
        resp = self._activate(client, "freshparent3b")
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.fresh_profile.refresh_from_db()
            self.assertEqual(User.objects.filter(id=self.fresh_profile.user_id).count(), 1)

    def test_activation_sets_encrypted_temp_password_and_needs_change(self):
        client = self._client_as(self.owner_user)
        resp = self._activate(client, "freshparent4")
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.fresh_profile.refresh_from_db()
            user = User.objects.get(id=self.fresh_profile.user_id)
            self.assertTrue(user.needs_password_change)
            self.assertIsNotNone(user.initial_password_display)

    def test_duplicate_activation_rejected(self):
        client = self._client_as(self.owner_user)
        first = self._activate(client, "freshparent5")
        self.assertEqual(first.status_code, 201, first.data)
        second = self._activate(client, "freshparent5b")
        self.assertEqual(second.status_code, 400)

    def test_nonexistent_parent_activation_rejected(self):
        client = self._client_as(self.owner_user)
        resp = self._activate(client, "ghost", parent_id=uuid_module.uuid4())
        self.assertEqual(resp.status_code, 400)

    def test_activation_requires_change_family_permission(self):
        client = self._client_as(self.non_parent_user)
        resp = self._activate(client, "freshparent6")
        self.assertEqual(resp.status_code, 403)

    def test_activated_parent_can_login(self):
        client = self._client_as(self.owner_user)
        resp = self._activate(client, "freshparent7")
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.fresh_profile.refresh_from_db()
            user = User.objects.get(id=self.fresh_profile.user_id)
        login_client = APIClient()
        login_resp = login_client.post(
            "/api/auth/login/", {"username": user.username, "password": "TempPass123!"}, HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(login_resp.status_code, 200)

    def test_credential_distribution_lists_activated_parent(self):
        client = self._client_as(self.owner_user)
        resp = self._activate(client, "freshparent8")
        self.assertEqual(resp.status_code, 201, resp.data)
        listing = client.get("/api/families/credentials-parents/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(listing.status_code, 200)
        usernames = [row["username"] for row in listing.data]
        self.assertIn("freshparent8", usernames)

    def test_credential_distribution_creates_audit_log(self):
        client = self._client_as(self.owner_user)
        resp = self._activate(client, "freshparent9")
        self.assertEqual(resp.status_code, 201, resp.data)
        client.get("/api/families/credentials-parents/", HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            self.assertTrue(
                AuditLog.objects.filter(action="credentials_viewed", model_name="Parent").exists()
            )


class ParentMeViewTests(ParentPortalFixtureMixin, TransactionTestCase):
    def test_me_returns_parent_info(self):
        client = self._client_as(self.parent1_user)
        resp = client.get("/api/parent-portal/me/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["parent_id"], str(self.parent1.id))
        self.assertEqual(resp.data["children_count"], 2)

    def test_me_rejects_non_parent(self):
        client = self._client_as(self.non_parent_user)
        resp = client.get("/api/parent-portal/me/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_me_rejects_owner_without_parent_record(self):
        # Explicit proof there is NO owner-bypass in parent_portal.
        client = self._client_as(self.owner_user)
        resp = client.get("/api/parent-portal/me/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)


class LinkedChildrenViewTests(ParentPortalFixtureMixin, TransactionTestCase):
    def test_lists_own_children(self):
        self._give_role_only(self.parent1_user, ["view_own_children"])
        client = self._client_as(self.parent1_user)
        resp = client.get("/api/parent-portal/children/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        ids = {row["student_id"] for row in resp.data}
        self.assertEqual(ids, {str(self.student1.id), str(self.student2.id)})

    def test_multiple_children_supported_from_one_account(self):
        self._give_role_only(self.parent1_user, ["view_own_children"])
        client = self._client_as(self.parent1_user)
        resp = client.get("/api/parent-portal/children/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(len(resp.data), 2)

    def test_does_not_list_other_parents_children(self):
        self._give_role_only(self.parent1_user, ["view_own_children"])
        client = self._client_as(self.parent1_user)
        resp = client.get("/api/parent-portal/children/", HTTP_HOST=self.DOMAIN)
        ids = {row["student_id"] for row in resp.data}
        self.assertNotIn(str(self.student3.id), ids)

    def test_response_excludes_internal_fields(self):
        self._give_role_only(self.parent1_user, ["view_own_children"])
        client = self._client_as(self.parent1_user)
        resp = client.get("/api/parent-portal/children/", HTTP_HOST=self.DOMAIN)
        row = resp.data[0]
        self.assertNotIn("profile_id", row)
        self.assertNotIn("user_id", row)

    def test_requires_view_own_children_permission(self):
        self._give_role_only(self.parent1_user, [])  # explicitly no permissions
        client = self._client_as(self.parent1_user)
        resp = client.get("/api/parent-portal/children/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_non_parent_with_permission_still_denied(self):
        # Defense-in-depth: even if a non-parent role is misconfigured with
        # this permission, get_parent_for_user still returns None.
        self._give_role_only(self.non_parent_user, ["view_own_children"])
        client = self._client_as(self.non_parent_user)
        resp = client.get("/api/parent-portal/children/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.get("/api/parent-portal/children/", HTTP_HOST=self.DOMAIN)
        self.assertIn(resp.status_code, (401, 403))


class ChildAuthorizationTests(ParentPortalFixtureMixin, TransactionTestCase):
    def test_parent_can_access_own_child_attendance(self):
        self._give_role_only(self.parent1_user, ["view_child_attendance"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/attendance/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_parent_cannot_access_unrelated_student_attendance(self):
        self._give_role_only(self.parent1_user, ["view_child_attendance"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student3.id}/attendance/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_parent_a_cannot_access_parent_b_child(self):
        self._give_role_only(self.parent2_user, ["view_child_attendance"])
        client = self._client_as(self.parent2_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/attendance/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_removing_relation_immediately_revokes_access(self):
        self._give_role_only(self.parent1_user, ["view_child_attendance"])
        client = self._client_as(self.parent1_user)
        ok = client.get(f"/api/parent-portal/children/{self.student1.id}/attendance/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(ok.status_code, 200)

        with tenant_context(self.school):
            StudentParentRelation.objects.filter(student=self.student1, parent=self.parent1).delete()

        again = client.get(f"/api/parent-portal/children/{self.student1.id}/attendance/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(again.status_code, 403)

    def test_nonexistent_student_id_denied(self):
        self._give_role_only(self.parent1_user, ["view_child_attendance"])
        client = self._client_as(self.parent1_user)
        resp = client.get(
            f"/api/parent-portal/children/{uuid_module.uuid4()}/attendance/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)

    def test_enumeration_gives_identical_response_for_nonexistent_and_unrelated(self):
        self._give_role_only(self.parent1_user, ["view_child_attendance"])
        client = self._client_as(self.parent1_user)
        nonexistent = client.get(
            f"/api/parent-portal/children/{uuid_module.uuid4()}/attendance/", HTTP_HOST=self.DOMAIN
        )
        unrelated = client.get(
            f"/api/parent-portal/children/{self.student3.id}/attendance/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(nonexistent.status_code, unrelated.status_code)
        self.assertEqual(nonexistent.data, unrelated.data)

    def test_cross_tenant_student_denied(self):
        self._give_role_only(self.parent1_user, ["view_child_attendance"])
        client = self._client_as(self.parent1_user)
        resp = client.get(
            f"/api/parent-portal/children/{self.other_tenant_student.id}/attendance/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)

    def test_frontend_selected_child_cannot_bypass_backend(self):
        # Simulates a manipulated frontend simply requesting an arbitrary
        # student_id in the URL - the backend independently re-verifies the
        # relationship regardless of what the client claims was "selected".
        self._give_role_only(self.parent1_user, ["view_child_timetable"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student3.id}/timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_owner_has_no_bypass_for_child_access(self):
        self._give_role_only(self.owner_user, ["view_child_attendance"])
        client = self._client_as(self.owner_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/attendance/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_user_can_access_child_service_true_case(self):
        with tenant_context(self.school):
            self.assertTrue(user_can_access_child(self.parent1_user, self.student1.id))

    def test_user_can_access_child_service_false_case(self):
        with tenant_context(self.school):
            self.assertFalse(user_can_access_child(self.parent1_user, self.student3.id))

    def test_user_can_access_child_service_false_for_non_parent(self):
        with tenant_context(self.school):
            self.assertFalse(user_can_access_child(self.non_parent_user, self.student1.id))


class ChildAttendanceViewTests(ParentPortalFixtureMixin, TransactionTestCase):
    def test_returns_expected_counts_and_percentage(self):
        self._give_role_only(self.parent1_user, ["view_child_attendance"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/attendance/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["counts"], {"present": 1})
        self.assertEqual(resp.data["percentage"], 100.0)

    def test_absent_child_counts_reflect_status(self):
        self._give_role_only(self.parent1_user, ["view_child_attendance"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student2.id}/attendance/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["counts"], {"absent": 1})

    def test_requires_view_child_attendance_permission(self):
        self._give_role_only(self.parent1_user, [])  # explicitly no permissions
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/attendance/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)


class ChildTimetableViewTests(ParentPortalFixtureMixin, TransactionTestCase):
    def test_returns_section_timetable(self):
        self._give_role_only(self.parent1_user, ["view_child_timetable"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["subject_name"], "Math")

    def test_requires_view_child_timetable_permission(self):
        self._give_role_only(self.parent1_user, [])  # explicitly no permissions
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_unrelated_child_denied(self):
        self._give_role_only(self.parent2_user, ["view_child_timetable"])
        client = self._client_as(self.parent2_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)


class ChildResultsViewTests(ParentPortalFixtureMixin, TransactionTestCase):
    def test_returns_only_published_results(self):
        self._give_role_only(self.parent1_user, ["view_child_results"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/results/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        # ChildExamResultSerializer's "examination" is a ModelSerializer FK
        # field, so resp.data holds the raw UUID (not yet JSON-rendered to a
        # string) - compare UUID to UUID, not UUID to str.
        self.assertEqual(resp.data[0]["examination"], self.examination.id)

    def test_unpublished_examination_never_appears(self):
        with tenant_context(self.school):
            unpublished_exam = Examination.objects.create(
                academic_year="2026", name="Unpublished Quiz", exam_type=self.exam_type,
                start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 7, 5),
            )
            schedule2 = ExamSchedule.objects.create(
                examination=unpublished_exam, academic_year="2026", subject=self.subject,
                section=self.section_a, date=datetime.date(2026, 7, 2),
                start_time=datetime.time(9, 0), end_time=datetime.time(11, 0),
                max_marks=Decimal("100"), pass_marks=Decimal("40"),
            )
            ExamMark.objects.create(
                exam_schedule=schedule2, student=self.student1, marks_obtained=Decimal("90")
            )
            # deliberately NOT published

        self._give_role_only(self.parent1_user, ["view_child_results"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/results/", HTTP_HOST=self.DOMAIN)
        exam_ids = {row["examination"] for row in resp.data}
        self.assertNotIn(unpublished_exam.id, exam_ids)

    def test_unrelated_child_results_denied(self):
        self._give_role_only(self.parent1_user, ["view_child_results"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student3.id}/results/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)


class ChildUpcomingExamsViewTests(ParentPortalFixtureMixin, TransactionTestCase):
    def test_returns_future_schedule_for_own_child(self):
        with tenant_context(self.school):
            # A distinct subject is required here - self.examination already
            # has a schedule for (self.subject, self.section_a) from setUp(),
            # and ExamSchedule enforces unique_together on
            # (examination, subject, section).
            second_subject = Subject.objects.create(
                level=self.section_a.level, name="Science", code="SCIPP"
            )
            ExamSchedule.objects.create(
                examination=self.examination, academic_year="2026", subject=second_subject,
                section=self.section_a, date=datetime.date(2099, 1, 1),
                start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
                max_marks=Decimal("50"), pass_marks=Decimal("20"),
            )
        self._give_role_only(self.parent1_user, ["view_child_results"])
        client = self._client_as(self.parent1_user)
        resp = client.get(
            f"/api/parent-portal/children/{self.student1.id}/upcoming-exams/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)
        # This view returns a plain dict (not run through a Serializer), so
        # resp.data still holds the raw datetime.date object.
        self.assertTrue(any(row["date"] == datetime.date(2099, 1, 1) for row in resp.data))

    def test_unrelated_child_denied(self):
        self._give_role_only(self.parent1_user, ["view_child_results"])
        client = self._client_as(self.parent1_user)
        resp = client.get(
            f"/api/parent-portal/children/{self.student3.id}/upcoming-exams/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)

    def test_requires_permission(self):
        client = self._client_as(self.parent1_user)
        resp = client.get(
            f"/api/parent-portal/children/{self.student1.id}/upcoming-exams/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)


class ChildReportCardViewTests(ParentPortalFixtureMixin, TransactionTestCase):
    def test_report_card_includes_student_summary(self):
        self._give_role_only(self.parent1_user, ["view_child_results"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/report-card/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["student"]["enrollment_id"], "ENR-PP-1")
        self.assertEqual(len(resp.data["examinations"]), 1)

    def test_report_card_unrelated_child_denied(self):
        self._give_role_only(self.parent2_user, ["view_child_results"])
        client = self._client_as(self.parent2_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/report-card/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_report_card_requires_permission(self):
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/report-card/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)
