import datetime

from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import AcademicLevel, Program, Section, Subject, SubjectAssignment
from core.models import AuditLog
from families.models import Parent
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from staff.models import Instructor, StaffMember
from students.models import Student, StudentLevel

from .models import AttendanceSession, AttendanceSettings, StaffAttendance, StudentAttendance
from .services import calculate_attendance_percentage, get_section_roster


class AttendanceFixtureMixin:
    """
    Builds one tenant with a full academic/staff/student chain, reused by
    every attendance test class. Kept as a mixin (not a TestCase itself) so
    it is never picked up by Django's test discovery on its own.
    """

    SCHEMA_NAME = "att_test_school"
    DOMAIN = "atttest.localhost"

    def _build_school(self, schema_name=None, domain=None):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name="Attendance Test School")
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, role_slug):
        user = User.objects.create_user(
            username=username, email=f"{username}@atttest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(
                slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=role)
        return user

    def setUp(self):
        self.school = self._build_school()

        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code="HS")
            level = AcademicLevel.objects.create(program=program, name="Grade 10", order=1)
            self.section_a = Section.objects.create(level=level, name="A", capacity=40)
            self.section_b = Section.objects.create(level=level, name="B", capacity=40)
            self.subject = Subject.objects.create(level=level, name="Math", code="MTH101")

        # Owner
        self.owner_user = self._build_user("att_owner", "owner")

        # Instructor system role seeds with zero permissions by design (only
        # "owner" auto-gets all permissions) - grant what a real admin would
        # grant a teaching role via the Roles UI before it can use this API.
        with tenant_context(self.school):
            from roles.models import Permission

            instructor_role, _ = Role.objects.get_or_create(
                slug="instructor", defaults={"name": "Instructor", "is_system_role": True}
            )
            instructor_role.permissions.set(
                Permission.objects.filter(
                    codename__in=[
                        "view_attendance",
                        "mark_attendance",
                        "change_attendance",
                        "view_attendance_reports",
                    ]
                )
            )

        # Instructor assigned only to Section A
        self.instructor_user = self._build_user("att_instructor", "instructor")
        with tenant_context(self.school):
            instructor_profile = Profile.objects.create(
                user_id=self.instructor_user.id, first_name="Ivy", last_name="Teach"
            )
            staff_member = StaffMember.objects.create(
                profile=instructor_profile, employee_id="EMP-ATT-1", designation="Teacher"
            )
            self.instructor = Instructor.objects.create(
                staff_member=staff_member, specialization="Math"
            )
            SubjectAssignment.objects.create(
                section=self.section_a, subject=self.subject, instructor=self.instructor
            )
            self.instructor_staff_member = staff_member

        # A second instructor with NO assignment anywhere (for permission-denied tests)
        self.unassigned_instructor_user = self._build_user("att_instructor2", "instructor")
        with tenant_context(self.school):
            p2 = Profile.objects.create(
                user_id=self.unassigned_instructor_user.id, first_name="No", last_name="Section"
            )
            sm2 = StaffMember.objects.create(profile=p2, employee_id="EMP-ATT-2", designation="Teacher")
            Instructor.objects.create(staff_member=sm2, specialization="Science")

        # Two students in Section A (current enrollment), one inactive student also in Section A
        self.student_user = self._build_user("att_student1", "student")
        with tenant_context(self.school):
            student_profile = Profile.objects.create(
                user_id=self.student_user.id, first_name="Sam", last_name="Pupil"
            )
            self.student1 = Student.objects.create(
                profile=student_profile, enrollment_id="ENR-ATT-1", status="active"
            )
            StudentLevel.objects.create(
                student=self.student1, level=level, section=self.section_a,
                academic_year="2026", is_current=True,
            )

            profile2 = Profile.objects.create(first_name="Alex", last_name="Second")
            self.student2 = Student.objects.create(
                profile=profile2, enrollment_id="ENR-ATT-2", status="active"
            )
            StudentLevel.objects.create(
                student=self.student2, level=level, section=self.section_a,
                academic_year="2026", is_current=True,
            )

            # Withdrawn student, still has a current StudentLevel row but inactive status -
            # must be excluded from the roster, but any past attendance must survive.
            profile3 = Profile.objects.create(first_name="Wendy", last_name="Withdrawn")
            self.withdrawn_student = Student.objects.create(
                profile=profile3, enrollment_id="ENR-ATT-3", status="withdrawn"
            )
            StudentLevel.objects.create(
                student=self.withdrawn_student, level=level, section=self.section_a,
                academic_year="2026", is_current=True,
            )

        # A second student, NOT owned by student_user, for student-self-access-denial tests
        self.other_student_user = self._build_user("att_student2", "student")
        with tenant_context(self.school):
            other_profile = Profile.objects.create(
                user_id=self.other_student_user.id, first_name="Otto", last_name="Other"
            )
            self.other_student = Student.objects.create(
                profile=other_profile, enrollment_id="ENR-ATT-4", status="active"
            )
            StudentLevel.objects.create(
                student=self.other_student, level=level, section=self.section_b,
                academic_year="2026", is_current=True,
            )

    def tearDown(self):
        connection.set_schema_to_public()
        Organization.objects.filter(schema_name=self.SCHEMA_NAME).first() and self.school.delete(
            force_drop=True
        )

    def _client_as(self, user, password="Pass1234!"):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/",
            {"username": user.username, "password": password},
            HTTP_HOST=self.DOMAIN,
        )
        assert resp.status_code == 200, resp.data
        return client


class AttendanceModelTest(AttendanceFixtureMixin, TransactionTestCase):
    """Model-level constraints, settings defaults/validation, percentage calc."""

    def test_session_unique_per_section_and_date(self):
        with tenant_context(self.school):
            AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 1, 5)
            )
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    AttendanceSession.objects.create(
                        section=self.section_a, academic_year="2026", date=datetime.date(2026, 1, 5)
                    )

    def test_student_attendance_unique_per_session_and_student(self):
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 1, 6)
            )
            StudentAttendance.objects.create(session=session, student=self.student1, status="present")
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    StudentAttendance.objects.create(
                        session=session, student=self.student1, status="absent"
                    )

    def test_staff_attendance_unique_per_staff_and_date(self):
        with tenant_context(self.school):
            StaffAttendance.objects.create(
                staff=self.instructor_staff_member, date=datetime.date(2026, 1, 7), status="present"
            )
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    StaffAttendance.objects.create(
                        staff=self.instructor_staff_member, date=datetime.date(2026, 1, 7), status="absent"
                    )

    def test_settings_defaults(self):
        with tenant_context(self.school):
            settings_obj = AttendanceSettings.get_solo()
            self.assertEqual(settings_obj.status_weights["present"], 1.0)
            self.assertEqual(settings_obj.status_weights["absent"], 0.0)
            self.assertEqual(settings_obj.status_weights["late"], 1.0)
            self.assertEqual(settings_obj.status_weights["half_day"], 0.5)
            self.assertIsNone(settings_obj.status_weights["leave"])
            self.assertEqual(float(settings_obj.minimum_attendance_percentage), 75.00)
            self.assertEqual(settings_obj.lock_after_days, 0)

    def test_settings_rejects_unknown_status_key(self):
        with tenant_context(self.school):
            settings_obj = AttendanceSettings.get_solo()
            settings_obj.status_weights = {"present": 1.0, "sick": 1.0}
            with self.assertRaises(Exception):
                settings_obj.save()

    def test_percentage_calculation_present_absent(self):
        with tenant_context(self.school):
            settings_obj = AttendanceSettings.get_solo()
            pct = calculate_attendance_percentage({"present": 8, "absent": 2}, settings_obj)
            self.assertEqual(pct, 80.0)

    def test_percentage_calculation_late_and_half_day_weighting(self):
        with tenant_context(self.school):
            settings_obj = AttendanceSettings.get_solo()
            # 5 present (5.0) + 2 late (2.0, weight 1.0) + 2 half_day (1.0, weight 0.5) = 8.0 / 9 days
            pct = calculate_attendance_percentage(
                {"present": 5, "late": 2, "half_day": 2}, settings_obj
            )
            self.assertAlmostEqual(pct, (8.0 / 9) * 100, places=2)

    def test_percentage_calculation_leave_excluded_from_denominator(self):
        with tenant_context(self.school):
            settings_obj = AttendanceSettings.get_solo()
            # 5 present out of (5 present + 2 absent) = 71.43%; the 3 leave days don't count at all
            pct = calculate_attendance_percentage(
                {"present": 5, "absent": 2, "leave": 3}, settings_obj
            )
            self.assertAlmostEqual(pct, (5 / 7) * 100, places=2)

    def test_roster_excludes_inactive_students_and_other_sections(self):
        with tenant_context(self.school):
            roster_ids = set(get_section_roster(self.section_a.id).values_list("id", flat=True))
            self.assertIn(self.student1.id, roster_ids)
            self.assertIn(self.student2.id, roster_ids)
            self.assertNotIn(self.withdrawn_student.id, roster_ids, "withdrawn student must not appear in roster")
            self.assertNotIn(self.other_student.id, roster_ids, "student in a different section must not appear")


class AttendanceBulkAndLockTest(AttendanceFixtureMixin, TransactionTestCase):
    def test_roster_endpoint_returns_current_students_only(self):
        client = self._client_as(self.instructor_user)
        resp = client.get(
            f"/api/attendance/sections/{self.section_a.id}/roster/?date=2026-01-05",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        student_ids = {s["student"] for s in resp.data["students"]}
        self.assertEqual(student_ids, {str(self.student1.id), str(self.student2.id)})

    def test_valid_bulk_submission_creates_session_and_records(self):
        client = self._client_as(self.instructor_user)
        payload = {
            "section": str(self.section_a.id),
            "date": "2026-01-10",
            "records": [
                {"student": str(self.student1.id), "status": "present", "remarks": ""},
                {"student": str(self.student2.id), "status": "absent", "remarks": "sick note"},
            ],
        }
        resp = client.post("/api/attendance/sessions/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

        with tenant_context(self.school):
            session = AttendanceSession.objects.get(section=self.section_a, date=datetime.date(2026, 1, 10))
            self.assertEqual(session.student_records.count(), 2)
            self.assertEqual(
                session.student_records.get(student=self.student2).status, "absent"
            )

    def test_invalid_student_rejects_entire_bulk_submission(self):
        client = self._client_as(self.instructor_user)
        import uuid as uuid_module

        payload = {
            "section": str(self.section_a.id),
            "date": "2026-01-11",
            "records": [
                {"student": str(self.student1.id), "status": "present"},
                {"student": str(uuid_module.uuid4()), "status": "present"},
            ],
        }
        resp = client.post("/api/attendance/sessions/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 400)

        with tenant_context(self.school):
            self.assertFalse(
                AttendanceSession.objects.filter(
                    section=self.section_a, date=datetime.date(2026, 1, 11)
                ).exists(),
                "no session should have been created when one record was invalid",
            )

    def test_duplicate_submission_updates_existing_records_without_duplicates(self):
        client = self._client_as(self.instructor_user)
        payload = {
            "section": str(self.section_a.id),
            "date": "2026-01-12",
            "records": [{"student": str(self.student1.id), "status": "present"}],
        }
        resp1 = client.post("/api/attendance/sessions/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp1.status_code, 201)

        payload["records"][0]["status"] = "late"
        resp2 = client.post("/api/attendance/sessions/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp2.status_code, 200, resp2.data)

        with tenant_context(self.school):
            sessions = AttendanceSession.objects.filter(
                section=self.section_a, date=datetime.date(2026, 1, 12)
            )
            self.assertEqual(sessions.count(), 1, "resubmission must not create a duplicate session")
            records = StudentAttendance.objects.filter(session=sessions.first())
            self.assertEqual(records.count(), 1, "resubmission must not create a duplicate student row")
            self.assertEqual(records.first().status, "late")

    def test_locked_session_rejects_normal_edit_and_override_permission_works(self):
        client = self._client_as(self.instructor_user)
        payload = {
            "section": str(self.section_a.id),
            "date": "2026-01-13",
            "records": [{"student": str(self.student1.id), "status": "present"}],
        }
        create_resp = client.post("/api/attendance/sessions/", payload, HTTP_HOST=self.DOMAIN, format="json")
        session_id = create_resp.data["id"]

        # Owner locks it
        owner_client = self._client_as(self.owner_user)
        lock_resp = owner_client.post(
            f"/api/attendance/sessions/{session_id}/lock/", {"is_locked": True},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(lock_resp.status_code, 200, lock_resp.data)
        self.assertTrue(lock_resp.data["is_locked"])

        # Instructor (no edit_locked_attendance) is rejected with 423
        edit_resp = client.patch(
            f"/api/attendance/sessions/{session_id}/",
            {"records": [{"student": str(self.student1.id), "status": "absent"}]},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(edit_resp.status_code, 423, edit_resp.data)

        # Owner, who has edit_locked_attendance via bypass, CAN override
        override_resp = owner_client.patch(
            f"/api/attendance/sessions/{session_id}/",
            {"records": [{"student": str(self.student1.id), "status": "absent"}]},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(override_resp.status_code, 200, override_resp.data)

        with tenant_context(self.school):
            self.assertEqual(
                StudentAttendance.objects.get(session_id=session_id, student=self.student1).status,
                "absent",
            )

    def test_unlocked_session_can_be_edited_normally(self):
        client = self._client_as(self.instructor_user)
        payload = {
            "section": str(self.section_a.id),
            "date": "2026-01-14",
            "records": [{"student": str(self.student1.id), "status": "present"}],
        }
        create_resp = client.post("/api/attendance/sessions/", payload, HTTP_HOST=self.DOMAIN, format="json")
        session_id = create_resp.data["id"]

        edit_resp = client.patch(
            f"/api/attendance/sessions/{session_id}/",
            {"records": [{"student": str(self.student1.id), "status": "late"}]},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(edit_resp.status_code, 200, edit_resp.data)


class AttendanceAuthorizationTest(AttendanceFixtureMixin, TransactionTestCase):
    def test_instructor_can_access_assigned_section(self):
        client = self._client_as(self.instructor_user)
        resp = client.get(
            f"/api/attendance/sections/{self.section_a.id}/roster/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)

    def test_instructor_cannot_access_unassigned_section(self):
        """Section B: the assigned instructor has no SubjectAssignment there."""
        client = self._client_as(self.instructor_user)
        resp = client.get(
            f"/api/attendance/sections/{self.section_b.id}/roster/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)

    def test_instructor_with_no_assignments_anywhere_is_denied(self):
        client = self._client_as(self.unassigned_instructor_user)
        resp = client.get(
            f"/api/attendance/sections/{self.section_a.id}/roster/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)

    def test_instructor_cannot_mark_unassigned_section_via_bulk_post(self):
        """Never trust the section ID from the frontend - re-verified at write time too."""
        client = self._client_as(self.instructor_user)
        payload = {
            "section": str(self.section_b.id),
            "date": "2026-01-15",
            "records": [],
        }
        resp = client.post("/api/attendance/sessions/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertIn(resp.status_code, (400, 403))
        if resp.status_code == 200 or resp.status_code == 201:
            self.fail("instructor must not be able to create a session for an unassigned section")

    def test_student_can_access_own_attendance_history(self):
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 1, 16)
            )
            StudentAttendance.objects.create(session=session, student=self.student1, status="present")

        client = self._client_as(self.student_user)
        resp = client.get(
            f"/api/attendance/students/{self.student1.id}/history/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_student_cannot_access_another_students_attendance(self):
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 1, 17)
            )
            StudentAttendance.objects.create(session=session, student=self.student1, status="present")

        client = self._client_as(self.student_user)
        resp = client.get(
            f"/api/attendance/students/{self.other_student.id}/history/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(
            resp.status_code, 403,
            "SECURITY REGRESSION: a student read another student's attendance by changing the UUID in the URL",
        )

    def test_tenant_a_cannot_access_tenant_b_attendance(self):
        school_b = self._build_school(schema_name="att_test_school_b", domain="atttestb.localhost")
        try:
            with tenant_context(school_b):
                program_b = Program.objects.create(name="HS-B", code="HSB")
                level_b = AcademicLevel.objects.create(program=program_b, name="Grade 10", order=1)
                section_b_other_tenant = Section.objects.create(level=level_b, name="A", capacity=40)
                AttendanceSession.objects.create(
                    section=section_b_other_tenant, academic_year="2026", date=datetime.date(2026, 1, 18)
                )
                b_session_id = AttendanceSession.objects.first().id

            # Log in as tenant A's owner, but hit tenant B's domain with tenant A's session ID.
            client = self._client_as(self.owner_user)
            resp = client.get(
                f"/api/attendance/sections/{section_b_other_tenant.id}/roster/",
                HTTP_HOST=self.DOMAIN,  # tenant A's own domain - section_b_other_tenant doesn't exist here
            )
            self.assertEqual(resp.status_code, 403)

            # And more directly: within tenant A's own schema, tenant B's session must not exist.
            with tenant_context(self.school):
                self.assertFalse(
                    AttendanceSession.objects.filter(id=b_session_id).exists(),
                    "TENANT ISOLATION FAILURE: tenant A can see tenant B's attendance session",
                )
        finally:
            connection.set_schema_to_public()
            school_b.delete(force_drop=True)


class AttendancePermissionTest(AttendanceFixtureMixin, TransactionTestCase):
    def _give_role_only(self, user, codenames):
        """Creates a fresh custom role holding exactly the given permissions."""
        with tenant_context(self.school):
            from roles.models import Permission

            role = Role.objects.create(name=f"custom-{'-'.join(codenames)}"[:80], is_system_role=False)
            role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.filter(user=user).delete()
            UserRole.objects.create(user=user, role=role)

    def test_delete_requires_delete_attendance_session_permission(self):
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 2, 1)
            )
            session_id = session.id

        limited_user = self._build_user("att_limited1", "staff")
        self._give_role_only(limited_user, ["view_attendance"])  # no delete permission
        client = self._client_as(limited_user)

        resp = client.delete(f"/api/attendance/sessions/{session_id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

        with tenant_context(self.school):
            self.assertTrue(AttendanceSession.objects.filter(id=session_id).exists())

    def test_lock_requires_lock_attendance_permission(self):
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 2, 2)
            )
            session_id = session.id

        limited_user = self._build_user("att_limited2", "staff")
        self._give_role_only(limited_user, ["view_attendance"])
        client = self._client_as(limited_user)

        resp = client.post(
            f"/api/attendance/sessions/{session_id}/lock/", {"is_locked": True},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_reports_require_view_attendance_reports_permission(self):
        limited_user = self._build_user("att_limited3", "staff")
        self._give_role_only(limited_user, ["view_attendance"])  # view_attendance, not reports
        client = self._client_as(limited_user)

        resp = client.get("/api/attendance/reports/tenant-summary/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)


class AttendanceAuditTest(AttendanceFixtureMixin, TransactionTestCase):
    def _audit_actions(self):
        with tenant_context(self.school):
            return list(AuditLog.objects.values_list("action", flat=True))

    def test_creation_is_audited_once_per_session_not_per_student(self):
        client = self._client_as(self.instructor_user)
        payload = {
            "section": str(self.section_a.id),
            "date": "2026-03-01",
            "records": [
                {"student": str(self.student1.id), "status": "present"},
                {"student": str(self.student2.id), "status": "absent"},
            ],
        }
        client.post("/api/attendance/sessions/", payload, HTTP_HOST=self.DOMAIN, format="json")

        with tenant_context(self.school):
            creation_logs = AuditLog.objects.filter(action="attendance_marked")
            self.assertEqual(
                creation_logs.count(), 1,
                "one bulk submission for 2 students must produce exactly ONE audit row, not one per student",
            )
            self.assertEqual(creation_logs.first().changes["counts"], {"present": 1, "absent": 1})

    def test_modification_is_audited(self):
        client = self._client_as(self.instructor_user)
        payload = {
            "section": str(self.section_a.id),
            "date": "2026-03-02",
            "records": [{"student": str(self.student1.id), "status": "present"}],
        }
        create_resp = client.post("/api/attendance/sessions/", payload, HTTP_HOST=self.DOMAIN, format="json")
        session_id = create_resp.data["id"]

        client.patch(
            f"/api/attendance/sessions/{session_id}/",
            {"records": [{"student": str(self.student1.id), "status": "absent"}]},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertIn("attendance_modified", self._audit_actions())

    def test_deletion_is_audited(self):
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 3, 3)
            )
            session_id = session.id
        owner_client = self._client_as(self.owner_user)
        owner_client.delete(f"/api/attendance/sessions/{session_id}/", HTTP_HOST=self.DOMAIN)
        self.assertIn("attendance_session_deleted", self._audit_actions())

    def test_lock_and_unlock_are_audited(self):
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 3, 4)
            )
            session_id = session.id
        owner_client = self._client_as(self.owner_user)
        owner_client.post(
            f"/api/attendance/sessions/{session_id}/lock/", {"is_locked": True},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        owner_client.post(
            f"/api/attendance/sessions/{session_id}/lock/", {"is_locked": False},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        actions = self._audit_actions()
        self.assertIn("attendance_locked", actions)
        self.assertIn("attendance_unlocked", actions)

    def test_staff_attendance_marking_is_audited(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post(
            "/api/attendance/staff-sessions/",
            {
                "date": "2026-03-05",
                "records": [{"staff": str(self.instructor_staff_member.id), "status": "present"}],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertIn("staff_attendance_marked", self._audit_actions())

    def test_settings_change_is_audited(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.patch(
            "/api/attendance/settings/",
            {"minimum_attendance_percentage": "80.00"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn("attendance_settings_changed", self._audit_actions())


class AttendanceReportsTest(AttendanceFixtureMixin, TransactionTestCase):
    def test_below_threshold_report(self):
        with tenant_context(self.school):
            settings_obj = AttendanceSettings.get_solo()
            settings_obj.minimum_attendance_percentage = 90.00
            settings_obj.save()

            session1 = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 4, 1)
            )
            session2 = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 4, 2)
            )
            # student1: 1 present, 1 absent -> 50%, below 90% threshold
            StudentAttendance.objects.create(session=session1, student=self.student1, status="present")
            StudentAttendance.objects.create(session=session2, student=self.student1, status="absent")
            # student2: 2 present -> 100%, above threshold
            StudentAttendance.objects.create(session=session1, student=self.student2, status="present")
            StudentAttendance.objects.create(session=session2, student=self.student2, status="present")

        client = self._client_as(self.instructor_user)
        resp = client.get(
            f"/api/attendance/reports/below-threshold/?section={self.section_a.id}",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        flagged_ids = {s["student"] for s in resp.data["students"]}
        self.assertIn(str(self.student1.id), flagged_ids)
        self.assertNotIn(str(self.student2.id), flagged_ids)

    def test_tenant_summary_report(self):
        with tenant_context(self.school):
            session = AttendanceSession.objects.create(
                section=self.section_a, academic_year="2026", date=datetime.date(2026, 4, 3)
            )
            StudentAttendance.objects.create(session=session, student=self.student1, status="present")
            StudentAttendance.objects.create(session=session, student=self.student2, status="absent")

        client = self._client_as(self.owner_user)
        resp = client.get(
            "/api/attendance/reports/tenant-summary/?date=2026-04-03", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["percentage"], 50.0)

    def test_tenant_summary_with_no_sessions_returns_null_percentage(self):
        client = self._client_as(self.owner_user)
        resp = client.get(
            "/api/attendance/reports/tenant-summary/?date=2099-01-01", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["percentage"])


class StaffAttendanceTest(AttendanceFixtureMixin, TransactionTestCase):
    def test_bulk_staff_marking_and_history(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            "/api/attendance/staff-sessions/",
            {
                "date": "2026-05-01",
                "records": [{"staff": str(self.instructor_staff_member.id), "status": "present"}],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        history_resp = owner_client.get(
            f"/api/attendance/staff/{self.instructor_staff_member.id}/history/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(history_resp.status_code, 200)
        self.assertEqual(history_resp.data["counts"], {"present": 1})

    def test_duplicate_staff_submission_updates_not_duplicates(self):
        owner_client = self._client_as(self.owner_user)
        base_payload = {
            "date": "2026-05-02",
            "records": [{"staff": str(self.instructor_staff_member.id), "status": "present"}],
        }
        owner_client.post("/api/attendance/staff-sessions/", base_payload, HTTP_HOST=self.DOMAIN, format="json")
        base_payload["records"][0]["status"] = "late"
        owner_client.post("/api/attendance/staff-sessions/", base_payload, HTTP_HOST=self.DOMAIN, format="json")

        with tenant_context(self.school):
            rows = StaffAttendance.objects.filter(
                staff=self.instructor_staff_member, date=datetime.date(2026, 5, 2)
            )
            self.assertEqual(rows.count(), 1)
            self.assertEqual(rows.first().status, "late")
