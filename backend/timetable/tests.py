import datetime

from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import AcademicLevel, Program, Section, Subject, SubjectAssignment
from core.models import AuditLog
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from staff.models import Instructor, StaffMember
from students.models import Student, StudentLevel

from .models import Period, Room, TimetableEntry, TimetableSubstitution


class TimetableFixtureMixin:
    """Mirrors attendance/tests.py's AttendanceFixtureMixin exactly."""

    SCHEMA_NAME = "tt_test_school"
    DOMAIN = "tttest.localhost"

    def _build_school(self, schema_name=None, domain=None):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name="Timetable Test School")
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, role_slug):
        user = User.objects.create_user(
            username=username, email=f"{username}@tttest.com", password="Pass1234!"
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
            program = Program.objects.create(name="High School", code="HSTT")
            level = AcademicLevel.objects.create(program=program, name="Grade 10", order=1)
            self.section_a = Section.objects.create(level=level, name="A", capacity=40)
            self.section_b = Section.objects.create(level=level, name="B", capacity=40)
            self.subject = Subject.objects.create(level=level, name="Math", code="MTHTT")

            other_level = AcademicLevel.objects.create(program=program, name="Grade 11", order=2)
            self.other_level_subject = Subject.objects.create(
                level=other_level, name="Physics", code="PHYTT"
            )

            self.period = Period.objects.create(
                academic_year="2026", name="Period 1", order=1,
                start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
            )
            self.break_period = Period.objects.create(
                academic_year="2026", name="Break", order=2,
                start_time=datetime.time(8, 45), end_time=datetime.time(9, 0), is_break=True,
            )
            self.room = Room.objects.create(name="Room 101TT", capacity=30)

        # Instructor role: grant relevant permissions (system roles seed with
        # zero permissions - this exact mistake broke the Attendance tests
        # until fixed, so it is not repeated here).
        with tenant_context(self.school):
            from roles.models import Permission

            instructor_role, _ = Role.objects.get_or_create(
                slug="instructor", defaults={"name": "Instructor", "is_system_role": True}
            )
            instructor_role.permissions.set(
                Permission.objects.filter(
                    codename__in=["view_timetable", "manage_timetable", "manage_substitutions"]
                )
            )

        self.instructor_user = self._build_user("tt_instructor", "instructor")
        with tenant_context(self.school):
            instructor_profile = Profile.objects.create(
                user_id=self.instructor_user.id, first_name="Ivy", last_name="Teach"
            )
            staff_member = StaffMember.objects.create(
                profile=instructor_profile, employee_id="EMP-TT-1", designation="Teacher"
            )
            self.instructor = Instructor.objects.create(staff_member=staff_member, specialization="Math")
            SubjectAssignment.objects.create(
                section=self.section_a, subject=self.subject, instructor=self.instructor
            )
            self.instructor_staff_member = staff_member

        # A second instructor, with no assignment anywhere.
        self.other_instructor_user = self._build_user("tt_instructor2", "instructor")
        with tenant_context(self.school):
            p2 = Profile.objects.create(
                user_id=self.other_instructor_user.id, first_name="No", last_name="Assignment"
            )
            sm2 = StaffMember.objects.create(profile=p2, employee_id="EMP-TT-2", designation="Teacher")
            self.other_instructor = Instructor.objects.create(staff_member=sm2, specialization="Science")

        self.owner_user = self._build_user("tt_owner", "owner")

        self.student_user = self._build_user("tt_student", "student")
        with tenant_context(self.school):
            student_profile = Profile.objects.create(
                user_id=self.student_user.id, first_name="Sam", last_name="Pupil"
            )
            self.student = Student.objects.create(
                profile=student_profile, enrollment_id="ENR-TT-1", status="active"
            )
            StudentLevel.objects.create(
                student=self.student, level=level, section=self.section_a,
                academic_year="2026", is_current=True,
            )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)

    def _client_as(self, user, password="Pass1234!"):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"username": user.username, "password": password}, HTTP_HOST=self.DOMAIN
        )
        assert resp.status_code == 200, resp.data
        return client

    def _give_role_only(self, user, codenames):
        with tenant_context(self.school):
            from roles.models import Permission

            role = Role.objects.create(name=f"custom-{'-'.join(codenames)}"[:80], is_system_role=False)
            role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.filter(user=user).delete()
            UserRole.objects.create(user=user, role=role)


class TimetableModelTest(TimetableFixtureMixin, TransactionTestCase):
    def test_period_uniqueness(self):
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Period.objects.create(
                        academic_year="2026", name="Duplicate", order=1,
                        start_time=datetime.time(9, 0), end_time=datetime.time(9, 45),
                    )

    def test_room_uniqueness(self):
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Room.objects.create(name="Room 101TT", capacity=10)

    def test_section_slot_uniqueness(self):
        with tenant_context(self.school):
            TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                day_of_week=0, period=self.period,
            )
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    TimetableEntry.objects.create(
                        academic_year="2026", section=self.section_a, subject=self.subject,
                        day_of_week=0, period=self.period,
                    )

    def test_instructor_slot_uniqueness(self):
        with tenant_context(self.school):
            TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                instructor=self.instructor, day_of_week=1, period=self.period,
            )
            SubjectAssignment.objects.create(
                section=self.section_b, subject=self.subject, instructor=self.instructor
            )
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    TimetableEntry.objects.create(
                        academic_year="2026", section=self.section_b, subject=self.subject,
                        instructor=self.instructor, day_of_week=1, period=self.period,
                    )

    def test_room_slot_uniqueness(self):
        with tenant_context(self.school):
            TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                room=self.room, day_of_week=2, period=self.period,
            )
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    TimetableEntry.objects.create(
                        academic_year="2026", section=self.section_b, subject=self.subject,
                        room=self.room, day_of_week=2, period=self.period,
                    )

    def test_substitution_uniqueness(self):
        with tenant_context(self.school):
            entry = TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                instructor=self.instructor, day_of_week=3, period=self.period,
            )
            TimetableSubstitution.objects.create(timetable_entry=entry, date=datetime.date(2026, 1, 5))
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    TimetableSubstitution.objects.create(
                        timetable_entry=entry, date=datetime.date(2026, 1, 5)
                    )

    def test_multiple_null_instructor_and_room_do_not_conflict(self):
        """PostgreSQL NULL semantics - two entries with no instructor/room set must coexist."""
        with tenant_context(self.school):
            TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                day_of_week=4, period=self.period,
            )
            SubjectAssignment.objects.create(
                section=self.section_b, subject=self.subject, instructor=None
            )
            entry2 = TimetableEntry.objects.create(
                academic_year="2026", section=self.section_b, subject=self.subject,
                day_of_week=4, period=self.period,
            )
            self.assertIsNotNone(entry2.id)


class TimetableAPITest(TimetableFixtureMixin, TransactionTestCase):
    def _valid_payload(self, **overrides):
        payload = {
            "academic_year": "2026",
            "section": str(self.section_a.id),
            "subject": str(self.subject.id),
            "instructor": str(self.instructor.id),
            "day_of_week": 0,
            "period": str(self.period.id),
        }
        payload.update(overrides)
        return payload

    def test_break_period_cannot_receive_entry(self):
        owner_client = self._client_as(self.owner_user)
        payload = self._valid_payload(period=str(self.break_period.id))
        resp = owner_client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("period", resp.data)

    def test_instructor_must_have_subject_assignment(self):
        owner_client = self._client_as(self.owner_user)
        payload = self._valid_payload(instructor=str(self.other_instructor.id))
        resp = owner_client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("instructor", resp.data)

    def test_period_academic_year_must_match(self):
        with tenant_context(self.school):
            other_year_period = Period.objects.create(
                academic_year="2027", name="P1-2027", order=1,
                start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
            )
        owner_client = self._client_as(self.owner_user)
        payload = self._valid_payload(period=str(other_year_period.id))
        resp = owner_client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("period", resp.data)

    def test_subject_must_belong_to_section_level(self):
        owner_client = self._client_as(self.owner_user)
        payload = self._valid_payload(subject=str(self.other_level_subject.id), instructor="")
        payload["instructor"] = None
        resp = owner_client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("subject", resp.data)

    def test_valid_entry_creation(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            "/api/timetable/entries/", self._valid_payload(), HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.assertTrue(TimetableEntry.objects.filter(section=self.section_a, day_of_week=0).exists())

    def test_update_entry(self):
        owner_client = self._client_as(self.owner_user)
        create_resp = owner_client.post(
            "/api/timetable/entries/", self._valid_payload(), HTTP_HOST=self.DOMAIN, format="json"
        )
        entry_id = create_resp.data["id"]
        resp = owner_client.patch(
            f"/api/timetable/entries/{entry_id}/", {"instructor": None}, HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data["instructor"])

    def test_delete_entry(self):
        owner_client = self._client_as(self.owner_user)
        create_resp = owner_client.post(
            "/api/timetable/entries/", self._valid_payload(), HTTP_HOST=self.DOMAIN, format="json"
        )
        entry_id = create_resp.data["id"]
        resp = owner_client.delete(f"/api/timetable/entries/{entry_id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 204)
        with tenant_context(self.school):
            self.assertFalse(TimetableEntry.objects.filter(id=entry_id).exists())

    def test_section_conflict_clean_error(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post("/api/timetable/entries/", self._valid_payload(), HTTP_HOST=self.DOMAIN, format="json")
        resp = owner_client.post(
            "/api/timetable/entries/",
            self._valid_payload(instructor=None),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already has a timetable entry", str(resp.data))

    def test_instructor_conflict_clean_error(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post("/api/timetable/entries/", self._valid_payload(), HTTP_HOST=self.DOMAIN, format="json")
        with tenant_context(self.school):
            SubjectAssignment.objects.create(
                section=self.section_b, subject=self.subject, instructor=self.instructor
            )
        resp = owner_client.post(
            "/api/timetable/entries/",
            self._valid_payload(section=str(self.section_b.id)),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already scheduled", str(resp.data))

    def test_room_conflict_clean_error(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post(
            "/api/timetable/entries/", self._valid_payload(room=str(self.room.id)), HTTP_HOST=self.DOMAIN, format="json"
        )
        resp = owner_client.post(
            "/api/timetable/entries/",
            self._valid_payload(section=str(self.section_b.id), instructor=None, room=str(self.room.id)),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already occupied", str(resp.data))


class TimetableAuthorizationTest(TimetableFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.entry_a = TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                instructor=self.instructor, day_of_week=0, period=self.period,
            )

    def test_owner_access(self):
        client = self._client_as(self.owner_user)
        resp = client.get(f"/api/timetable/sections/{self.section_a.id}/timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_instructor_can_access_assigned_section(self):
        client = self._client_as(self.instructor_user)
        resp = client.get(f"/api/timetable/sections/{self.section_a.id}/timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_instructor_cannot_access_unrelated_section(self):
        client = self._client_as(self.instructor_user)
        resp = client.get(f"/api/timetable/sections/{self.section_b.id}/timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_instructor_cannot_assign_self_to_unrelated_subject_section(self):
        client = self._client_as(self.other_instructor_user)
        payload = {
            "academic_year": "2026", "section": str(self.section_b.id), "subject": str(self.subject.id),
            "instructor": str(self.other_instructor.id), "day_of_week": 1, "period": str(self.period.id),
        }
        resp = client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertIn(resp.status_code, (400, 403))

    def test_staff_with_manage_permission_can_manage(self):
        staff_user = self._build_user("tt_staff", "staff")
        self._give_role_only(staff_user, ["view_timetable", "manage_timetable"])
        client = self._client_as(staff_user)
        payload = {
            "academic_year": "2026", "section": str(self.section_b.id), "subject": str(self.subject.id),
            "instructor": None, "day_of_week": 2, "period": str(self.period.id),
        }
        resp = client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_student_can_view_own_current_section(self):
        client = self._client_as(self.student_user)
        self._give_role_only(self.student_user, ["view_timetable"])
        client = self._client_as(self.student_user)
        resp = client.get("/api/timetable/my-timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["role"], "student")
        self.assertEqual(resp.data["section"], str(self.section_a.id))

    def test_student_cannot_modify_timetable(self):
        self._give_role_only(self.student_user, ["view_timetable"])
        client = self._client_as(self.student_user)
        payload = {
            "academic_year": "2026", "section": str(self.section_a.id), "subject": str(self.subject.id),
            "instructor": None, "day_of_week": 5, "period": str(self.period.id),
        }
        resp = client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_view_another_section(self):
        self._give_role_only(self.student_user, ["view_timetable"])
        client = self._client_as(self.student_user)
        resp = client.get(f"/api/timetable/sections/{self.section_b.id}/timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_view_arbitrary_instructor_timetable(self):
        self._give_role_only(self.student_user, ["view_timetable"])
        client = self._client_as(self.student_user)
        resp = client.get(
            f"/api/timetable/instructors/{self.instructor.id}/timetable/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)

    def test_instructor_can_view_own_instructor_timetable(self):
        client = self._client_as(self.instructor_user)
        resp = client.get(
            f"/api/timetable/instructors/{self.instructor.id}/timetable/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)


class TimetableTenantIsolationTest(TimetableFixtureMixin, TransactionTestCase):
    def test_tenant_a_cannot_access_tenant_b_timetable(self):
        school_b = self._build_school(schema_name="tt_test_school_b", domain="tttestb.localhost")
        try:
            with tenant_context(school_b):
                program_b = Program.objects.create(name="HS-B", code="HSBTT")
                level_b = AcademicLevel.objects.create(program=program_b, name="Grade 10", order=1)
                section_b_other = Section.objects.create(level=level_b, name="A", capacity=40)
                period_b = Period.objects.create(
                    academic_year="2026", name="P1", order=1,
                    start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
                )
                subject_b = Subject.objects.create(level=level_b, name="Math", code="MTHBTT")
                entry_b = TimetableEntry.objects.create(
                    academic_year="2026", section=section_b_other, subject=subject_b,
                    day_of_week=0, period=period_b,
                )
                entry_b_id = entry_b.id

            owner_client = self._client_as(self.owner_user)
            resp = owner_client.get(
                f"/api/timetable/sections/{section_b_other.id}/timetable/", HTTP_HOST=self.DOMAIN
            )
            self.assertEqual(resp.status_code, 403)

            with tenant_context(self.school):
                self.assertFalse(
                    TimetableEntry.objects.filter(id=entry_b_id).exists(),
                    "TENANT ISOLATION FAILURE: tenant A can see tenant B's timetable entry",
                )
        finally:
            connection.set_schema_to_public()
            school_b.delete(force_drop=True)


class TimetablePermissionTest(TimetableFixtureMixin, TransactionTestCase):
    def test_view_timetable_enforced(self):
        limited_user = self._build_user("tt_limited1", "staff")
        self._give_role_only(limited_user, [])
        client = self._client_as(limited_user)
        resp = client.get("/api/timetable/entries/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_manage_timetable_enforced(self):
        limited_user = self._build_user("tt_limited2", "staff")
        self._give_role_only(limited_user, ["view_timetable"])
        client = self._client_as(limited_user)
        payload = {
            "academic_year": "2026", "section": str(self.section_a.id), "subject": str(self.subject.id),
            "instructor": None, "day_of_week": 0, "period": str(self.period.id),
        }
        resp = client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_manage_periods_enforced(self):
        limited_user = self._build_user("tt_limited3", "staff")
        self._give_role_only(limited_user, ["view_timetable"])
        client = self._client_as(limited_user)
        resp = client.post(
            "/api/timetable/periods/",
            {"academic_year": "2026", "name": "X", "order": 99, "start_time": "10:00", "end_time": "10:45"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_manage_rooms_enforced(self):
        limited_user = self._build_user("tt_limited4", "staff")
        self._give_role_only(limited_user, ["view_timetable"])
        client = self._client_as(limited_user)
        resp = client.post(
            "/api/timetable/rooms/", {"name": "New Room", "capacity": 20}, HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_manage_substitutions_enforced(self):
        with tenant_context(self.school):
            entry = TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                instructor=self.instructor, day_of_week=0, period=self.period,
            )
        limited_user = self._build_user("tt_limited5", "staff")
        self._give_role_only(limited_user, ["view_timetable"])
        client = self._client_as(limited_user)
        resp = client.post(
            f"/api/timetable/entries/{entry.id}/substitute/",
            {"date": "2026-02-01", "substitute_instructor": str(self.other_instructor.id)},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)


class TimetableSubstitutionTest(TimetableFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.entry = TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                instructor=self.instructor, day_of_week=0, period=self.period,
            )

    def test_create_substitution(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            f"/api/timetable/entries/{self.entry.id}/substitute/",
            {"date": "2026-02-01", "substitute_instructor": str(self.other_instructor.id), "reason": "sick"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_duplicate_substitution_rejected(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post(
            f"/api/timetable/entries/{self.entry.id}/substitute/",
            {"date": "2026-02-02", "substitute_instructor": str(self.other_instructor.id)},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        resp = owner_client.post(
            f"/api/timetable/entries/{self.entry.id}/substitute/",
            {"date": "2026-02-02", "substitute_instructor": str(self.other_instructor.id)},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already exists", str(resp.data))

    def test_invalid_substitute_rejected(self):
        import uuid as uuid_module

        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            f"/api/timetable/entries/{self.entry.id}/substitute/",
            {"date": "2026-02-03", "substitute_instructor": str(uuid_module.uuid4())},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_conflicting_substitute_rejected(self):
        """other_instructor is regularly scheduled at day 1/period elsewhere - cannot substitute here too."""
        with tenant_context(self.school):
            SubjectAssignment.objects.create(
                section=self.section_b, subject=self.subject, instructor=self.other_instructor
            )
            conflicting_entry = TimetableEntry.objects.create(
                academic_year="2026", section=self.section_b, subject=self.subject,
                instructor=self.other_instructor, day_of_week=0, period=self.period,
            )

        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            f"/api/timetable/entries/{self.entry.id}/substitute/",
            {"date": "2026-02-04", "substitute_instructor": str(self.other_instructor.id)},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already regularly scheduled", str(resp.data))


class TimetableAuditTest(TimetableFixtureMixin, TransactionTestCase):
    def _actions(self):
        with tenant_context(self.school):
            return list(AuditLog.objects.values_list("action", flat=True))

    def test_creation_audited(self):
        owner_client = self._client_as(self.owner_user)
        payload = {
            "academic_year": "2026", "section": str(self.section_a.id), "subject": str(self.subject.id),
            "instructor": str(self.instructor.id), "day_of_week": 0, "period": str(self.period.id),
        }
        owner_client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertIn("timetable_entry_created", self._actions())

    def test_update_audited(self):
        owner_client = self._client_as(self.owner_user)
        payload = {
            "academic_year": "2026", "section": str(self.section_a.id), "subject": str(self.subject.id),
            "instructor": str(self.instructor.id), "day_of_week": 0, "period": str(self.period.id),
        }
        create_resp = owner_client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        owner_client.patch(
            f"/api/timetable/entries/{create_resp.data['id']}/", {"instructor": None},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertIn("timetable_entry_updated", self._actions())

    def test_delete_audited(self):
        owner_client = self._client_as(self.owner_user)
        payload = {
            "academic_year": "2026", "section": str(self.section_a.id), "subject": str(self.subject.id),
            "instructor": str(self.instructor.id), "day_of_week": 0, "period": str(self.period.id),
        }
        create_resp = owner_client.post("/api/timetable/entries/", payload, HTTP_HOST=self.DOMAIN, format="json")
        owner_client.delete(f"/api/timetable/entries/{create_resp.data['id']}/", HTTP_HOST=self.DOMAIN)
        self.assertIn("timetable_entry_deleted", self._actions())

    def test_substitution_audited(self):
        with tenant_context(self.school):
            entry = TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                instructor=self.instructor, day_of_week=0, period=self.period,
            )
        owner_client = self._client_as(self.owner_user)
        owner_client.post(
            f"/api/timetable/entries/{entry.id}/substitute/",
            {"date": "2026-02-05", "substitute_instructor": str(self.other_instructor.id)},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertIn("timetable_substitution_created", self._actions())


class TimetableSectionAndInstructorViewTest(TimetableFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            TimetableEntry.objects.create(
                academic_year="2026", section=self.section_a, subject=self.subject,
                instructor=self.instructor, room=self.room, day_of_week=0, period=self.period,
            )

    def test_section_weekly_timetable_response_shape(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.get(f"/api/timetable/sections/{self.section_a.id}/timetable/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        row = resp.data[0]
        self.assertIn("day_of_week", row)
        self.assertIn("period_name", row)
        self.assertIn("subject_name", row)
        self.assertIn("instructor_name", row)
        self.assertIn("room_name", row)

    def test_instructor_timetable_response(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.get(
            f"/api/timetable/instructors/{self.instructor.id}/timetable/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_filtering_by_academic_year(self):
        with tenant_context(self.school):
            Period.objects.create(
                academic_year="2027", name="P1-27", order=1,
                start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
            )
            other_year_period = Period.objects.get(academic_year="2027")
            SubjectAssignment.objects.create(
                section=self.section_b, subject=self.subject, instructor=None
            )
            TimetableEntry.objects.create(
                academic_year="2027", section=self.section_b, subject=self.subject,
                day_of_week=0, period=other_year_period,
            )

        owner_client = self._client_as(self.owner_user)
        resp = owner_client.get(
            "/api/timetable/entries/?academic_year=2027", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["academic_year"], "2027")
