import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
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
from timetable.models import Period, Room

from .models import ExamMark, ExamResult, ExamSchedule, Examination, ExamType, GradeBoundary


class ExamFixtureMixin:
    """Mirrors attendance/tests.py and timetable/tests.py exactly."""

    SCHEMA_NAME = "exam_test_school"
    DOMAIN = "examtest.localhost"

    def _build_school(self, schema_name=None, domain=None):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name="Exam Test School")
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, role_slug):
        user = User.objects.create_user(
            username=username, email=f"{username}@examtest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(
                slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=role)
        return user

    def _give_role_only(self, user, codenames):
        import uuid as uuid_module

        with tenant_context(self.school):
            from roles.models import Permission

            role = Role.objects.create(name=f"custom-{uuid_module.uuid4().hex[:8]}", is_system_role=False)
            role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.filter(user=user).delete()
            UserRole.objects.create(user=user, role=role)

    def setUp(self):
        self.school = self._build_school()

        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code="HSEX")
            level = AcademicLevel.objects.create(program=program, name="Grade 10", order=1)
            self.section_a = Section.objects.create(level=level, name="A", capacity=40)
            self.section_b = Section.objects.create(level=level, name="B", capacity=40)
            self.subject = Subject.objects.create(level=level, name="Math", code="MTHEX")

            other_level = AcademicLevel.objects.create(program=program, name="Grade 11", order=2)
            self.other_level_subject = Subject.objects.create(level=other_level, name="Physics", code="PHYEX")
            self.second_subject = Subject.objects.create(level=level, name="Science", code="SCIEX")

            self.exam_type = ExamType.objects.create(name="Mid-Term", order=1)
            self.examination = Examination.objects.create(
                academic_year="2026", name="Mid-Term 2026", exam_type=self.exam_type,
                start_date=datetime.date(2026, 6, 1), end_date=datetime.date(2026, 6, 10),
            )

            self.period = Period.objects.create(
                academic_year="2026", name="Period 1", order=1,
                start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
            )
            self.room = Room.objects.create(name="Exam Hall 1", capacity=100)

            GradeBoundary.objects.create(
                academic_year="2026", min_percentage=Decimal("90"), max_percentage=Decimal("100"),
                grade_label="A+", grade_point=Decimal("4.0"),
            )
            GradeBoundary.objects.create(
                academic_year="2026", min_percentage=Decimal("40"), max_percentage=Decimal("89.99"),
                grade_label="B", grade_point=Decimal("3.0"),
            )
            GradeBoundary.objects.create(
                academic_year="2026", min_percentage=Decimal("0"), max_percentage=Decimal("39.99"),
                grade_label="F", grade_point=Decimal("0.0"),
            )

        # Instructor role seeds with zero permissions - grant what a real
        # admin would grant via the Roles UI (the exact Attendance mistake
        # is not repeated here).
        with tenant_context(self.school):
            from roles.models import Permission

            instructor_role, _ = Role.objects.get_or_create(
                slug="instructor", defaults={"name": "Instructor", "is_system_role": True}
            )
            instructor_role.permissions.set(
                Permission.objects.filter(
                    codename__in=["view_examinations", "manage_examinations", "enter_marks"]
                )
            )

        self.instructor_user = self._build_user("exam_instructor", "instructor")
        with tenant_context(self.school):
            instructor_profile = Profile.objects.create(
                user_id=self.instructor_user.id, first_name="Ivy", last_name="Teach"
            )
            staff_member = StaffMember.objects.create(
                profile=instructor_profile, employee_id="EMP-EX-1", designation="Teacher"
            )
            self.instructor = Instructor.objects.create(staff_member=staff_member, specialization="Math")
            SubjectAssignment.objects.create(section=self.section_a, subject=self.subject, instructor=self.instructor)
            self.instructor_staff_member = staff_member

        self.other_instructor_user = self._build_user("exam_instructor2", "instructor")
        with tenant_context(self.school):
            p2 = Profile.objects.create(user_id=self.other_instructor_user.id, first_name="No", last_name="Assignment")
            sm2 = StaffMember.objects.create(profile=p2, employee_id="EMP-EX-2", designation="Teacher")
            self.other_instructor = Instructor.objects.create(staff_member=sm2, specialization="Science")

        self.owner_user = self._build_user("exam_owner", "owner")

        self.student_user = self._build_user("exam_student", "student")
        with tenant_context(self.school):
            student_profile = Profile.objects.create(user_id=self.student_user.id, first_name="Sam", last_name="Pupil")
            self.student = Student.objects.create(profile=student_profile, enrollment_id="ENR-EX-1", status="active")
            StudentLevel.objects.create(
                student=self.student, level=level, section=self.section_a, academic_year="2026", is_current=True
            )

            profile2 = Profile.objects.create(first_name="Alex", last_name="Second")
            self.student2 = Student.objects.create(profile=profile2, enrollment_id="ENR-EX-2", status="active")
            StudentLevel.objects.create(
                student=self.student2, level=level, section=self.section_a, academic_year="2026", is_current=True
            )

        self.other_student_user = self._build_user("exam_student2", "student")
        with tenant_context(self.school):
            other_profile = Profile.objects.create(user_id=self.other_student_user.id, first_name="Otto", last_name="Other")
            self.other_student = Student.objects.create(profile=other_profile, enrollment_id="ENR-EX-3", status="active")
            StudentLevel.objects.create(
                student=self.other_student, level=level, section=self.section_b, academic_year="2026", is_current=True
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

    def _create_schedule(self, **overrides):
        defaults = dict(
            academic_year="2026", section=self.section_a, subject=self.subject,
            date=datetime.date(2026, 6, 2), start_time=datetime.time(9, 0), end_time=datetime.time(11, 0),
            max_marks=Decimal("100"), pass_marks=Decimal("40"),
        )
        defaults.update(overrides)
        with tenant_context(self.school):
            return ExamSchedule.objects.create(examination=self.examination, **defaults)


class ExamModelTest(ExamFixtureMixin, TransactionTestCase):
    def test_exam_type_created(self):
        with tenant_context(self.school):
            self.assertEqual(ExamType.objects.count(), 1)

    def test_examination_created(self):
        with tenant_context(self.school):
            self.assertEqual(self.examination.academic_year, "2026")
            self.assertFalse(self.examination.is_published)

    def test_exam_schedule_unique_examination_subject_section(self):
        self._create_schedule()
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    ExamSchedule.objects.create(
                        examination=self.examination, academic_year="2026", section=self.section_a,
                        subject=self.subject, date=datetime.date(2026, 6, 3),
                        start_time=datetime.time(9, 0), end_time=datetime.time(11, 0),
                        max_marks=Decimal("100"), pass_marks=Decimal("40"),
                    )

    def test_exam_mark_unique_schedule_student(self):
        schedule = self._create_schedule()
        with tenant_context(self.school):
            ExamMark.objects.create(exam_schedule=schedule, student=self.student, marks_obtained=80)
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    ExamMark.objects.create(exam_schedule=schedule, student=self.student, marks_obtained=90)

    def test_exam_result_unique_examination_student(self):
        with tenant_context(self.school):
            ExamResult.objects.create(
                examination=self.examination, student=self.student, academic_year="2026",
                total_marks_obtained=80, total_max_marks=100, percentage=80, overall_grade="B", is_pass=True,
            )
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    ExamResult.objects.create(
                        examination=self.examination, student=self.student, academic_year="2026",
                        total_marks_obtained=70, total_max_marks=100, percentage=70, overall_grade="B", is_pass=True,
                    )

    def test_grade_boundary_rejects_overlap(self):
        with tenant_context(self.school):
            with self.assertRaises(DjangoValidationError):
                GradeBoundary.objects.create(
                    academic_year="2026", min_percentage=85, max_percentage=95, grade_label="A", grade_point=3.5
                )

    def test_grade_boundary_rejects_min_greater_than_max(self):
        with tenant_context(self.school):
            with self.assertRaises(DjangoValidationError):
                GradeBoundary.objects.create(
                    academic_year="2027", min_percentage=80, max_percentage=50, grade_label="X"
                )

    def test_grade_boundary_rejects_out_of_range_percentage(self):
        with tenant_context(self.school):
            with self.assertRaises(DjangoValidationError):
                GradeBoundary.objects.create(
                    academic_year="2027", min_percentage=-10, max_percentage=50, grade_label="X"
                )


class ExamScheduleBusinessRuleTest(ExamFixtureMixin, TransactionTestCase):
    def _payload(self, **overrides):
        payload = {
            "examination": str(self.examination.id), "academic_year": "2026",
            "subject": str(self.subject.id), "section": str(self.section_a.id),
            "date": "2026-06-02", "start_time": "09:00", "end_time": "11:00",
            "max_marks": "100.00", "pass_marks": "40.00",
        }
        payload.update(overrides)
        return payload

    def test_subject_must_belong_to_section_level(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            "/api/examinations/schedules/", self._payload(subject=str(self.other_level_subject.id)),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("subject", resp.data)

    def test_academic_year_must_match_examination(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            "/api/examinations/schedules/", self._payload(academic_year="2027"),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("academic_year", resp.data)

    def test_period_academic_year_must_match(self):
        with tenant_context(self.school):
            other_year_period = Period.objects.create(
                academic_year="2027", name="P1-27", order=1,
                start_time=datetime.time(8, 0), end_time=datetime.time(8, 45),
            )
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            "/api/examinations/schedules/", self._payload(period=str(other_year_period.id)),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("period", resp.data)

    def test_date_must_be_within_examination_range(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            "/api/examinations/schedules/", self._payload(date="2026-07-01"),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date", resp.data)

    def test_start_time_must_be_before_end_time(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            "/api/examinations/schedules/", self._payload(start_time="11:00", end_time="09:00"),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("start_time", resp.data)

    def test_valid_schedule_creation(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            "/api/examinations/schedules/", self._payload(), HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_section_overlap_rejected(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post("/api/examinations/schedules/", self._payload(), HTTP_HOST=self.DOMAIN, format="json")
        resp = owner_client.post(
            "/api/examinations/schedules/",
            self._payload(subject=str(self.second_subject.id), start_time="10:00", end_time="12:00"),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("section", resp.data)

    def test_room_overlap_rejected(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post(
            "/api/examinations/schedules/", self._payload(room=str(self.room.id)),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        resp = owner_client.post(
            "/api/examinations/schedules/",
            self._payload(section=str(self.section_b.id), room=str(self.room.id), start_time="10:00", end_time="12:00"),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("room", resp.data)

    def test_pass_marks_cannot_exceed_max_marks(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(
            "/api/examinations/schedules/", self._payload(pass_marks="150.00"),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("pass_marks", resp.data)

    def test_update_schedule(self):
        owner_client = self._client_as(self.owner_user)
        create_resp = owner_client.post(
            "/api/examinations/schedules/", self._payload(), HTTP_HOST=self.DOMAIN, format="json"
        )
        schedule_id = create_resp.data["id"]
        resp = owner_client.patch(
            f"/api/examinations/schedules/{schedule_id}/", {"max_marks": "120.00"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_delete_schedule(self):
        owner_client = self._client_as(self.owner_user)
        create_resp = owner_client.post(
            "/api/examinations/schedules/", self._payload(), HTTP_HOST=self.DOMAIN, format="json"
        )
        schedule_id = create_resp.data["id"]
        resp = owner_client.delete(f"/api/examinations/schedules/{schedule_id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 204)


class ExamMarksTest(ExamFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.schedule = self._create_schedule()

    def _marks_payload(self, **overrides):
        payload = {
            "records": [
                {"student": str(self.student.id), "marks_obtained": 78, "is_absent": False, "remarks": ""},
                {"student": str(self.student2.id), "marks_obtained": None, "is_absent": True, "remarks": "sick"},
            ]
        }
        payload.update(overrides)
        return payload

    def test_negative_marks_rejected(self):
        client = self._client_as(self.instructor_user)
        payload = {"records": [{"student": str(self.student.id), "marks_obtained": -5, "is_absent": False}]}
        resp = client.post(f"/api/examinations/schedules/{self.schedule.id}/marks/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_marks_exceeding_max_rejected(self):
        client = self._client_as(self.instructor_user)
        payload = {"records": [{"student": str(self.student.id), "marks_obtained": 999, "is_absent": False}]}
        resp = client.post(f"/api/examinations/schedules/{self.schedule.id}/marks/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_bulk_insertion(self):
        client = self._client_as(self.instructor_user)
        resp = client.post(
            f"/api/examinations/schedules/{self.schedule.id}/marks/", self._marks_payload(),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            self.assertEqual(ExamMark.objects.filter(exam_schedule=self.schedule).count(), 2)
            absent_mark = ExamMark.objects.get(exam_schedule=self.schedule, student=self.student2)
            self.assertTrue(absent_mark.is_absent)
            self.assertIsNone(absent_mark.marks_obtained)

    def test_invalid_student_rejects_entire_batch(self):
        import uuid as uuid_module

        client = self._client_as(self.instructor_user)
        payload = {
            "records": [
                {"student": str(self.student.id), "marks_obtained": 78, "is_absent": False},
                {"student": str(uuid_module.uuid4()), "marks_obtained": 50, "is_absent": False},
            ]
        }
        resp = client.post(f"/api/examinations/schedules/{self.schedule.id}/marks/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 400)
        with tenant_context(self.school):
            self.assertEqual(ExamMark.objects.filter(exam_schedule=self.schedule).count(), 0)

    def test_idempotent_resubmission_updates_not_duplicates(self):
        client = self._client_as(self.instructor_user)
        client.post(f"/api/examinations/schedules/{self.schedule.id}/marks/", self._marks_payload(), HTTP_HOST=self.DOMAIN, format="json")
        updated_payload = self._marks_payload()
        updated_payload["records"][0]["marks_obtained"] = 90
        client.post(f"/api/examinations/schedules/{self.schedule.id}/marks/", updated_payload, HTTP_HOST=self.DOMAIN, format="json")
        with tenant_context(self.school):
            self.assertEqual(ExamMark.objects.filter(exam_schedule=self.schedule).count(), 2)
            self.assertEqual(ExamMark.objects.get(exam_schedule=self.schedule, student=self.student).marks_obtained, 90)

    def test_locked_schedule_rejects_marks_submission(self):
        owner_client = self._client_as(self.owner_user)
        self._give_role_only(self.owner_user, ["view_examinations", "manage_examinations", "manage_marks"])
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/schedules/{self.schedule.id}/lock/", {"is_locked": True}, HTTP_HOST=self.DOMAIN, format="json")

        client = self._client_as(self.instructor_user)
        resp = client.post(f"/api/examinations/schedules/{self.schedule.id}/marks/", self._marks_payload(), HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 423)


class ExamPublicationTest(ExamFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.schedule = self._create_schedule()
        with tenant_context(self.school):
            ExamMark.objects.create(exam_schedule=self.schedule, student=self.student, marks_obtained=80)
            ExamMark.objects.create(exam_schedule=self.schedule, student=self.student2, marks_obtained=30)

    def test_publish_creates_result_snapshots(self):
        owner_client = self._client_as(self.owner_user)
        resp = owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            self.assertEqual(ExamResult.objects.filter(examination=self.examination).count(), 2)
            result = ExamResult.objects.get(examination=self.examination, student=self.student)
            self.assertEqual(result.percentage, Decimal("80.00"))
            self.assertTrue(result.is_pass)
            fail_result = ExamResult.objects.get(examination=self.examination, student=self.student2)
            self.assertFalse(fail_result.is_pass)

    def test_published_flag_and_timestamp_set(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            exam = Examination.objects.get(id=self.examination.id)
            self.assertTrue(exam.is_published)
            self.assertIsNotNone(exam.published_at)

    def test_cannot_publish_twice(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)
        resp = owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)

    def test_published_examination_cannot_be_edited(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)
        resp = owner_client.patch(
            f"/api/examinations/examinations/{self.examination.id}/", {"name": "Renamed"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_result_immutable_after_grading_change(self):
        """Publishing snapshots the result; later changing GradeBoundary must not alter it."""
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            before = ExamResult.objects.get(examination=self.examination, student=self.student).overall_grade
            GradeBoundary.objects.filter(grade_label="B").delete()
            GradeBoundary.objects.create(
                academic_year="2026", min_percentage=Decimal("40"), max_percentage=Decimal("89.99"),
                grade_label="RENAMED", grade_point=Decimal("3.0"),
            )
            after = ExamResult.objects.get(examination=self.examination, student=self.student).overall_grade
            self.assertEqual(before, after, "Published result must not change when grading config changes later")


class ExamAuthorizationTest(ExamFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.schedule = self._create_schedule()

    def test_owner_access(self):
        client = self._client_as(self.owner_user)
        resp = client.get("/api/examinations/schedules/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_instructor_can_enter_marks_for_own_schedule(self):
        client = self._client_as(self.instructor_user)
        payload = {"records": [{"student": str(self.student.id), "marks_obtained": 80, "is_absent": False}]}
        resp = client.post(f"/api/examinations/schedules/{self.schedule.id}/marks/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_instructor_cannot_modify_another_instructors_schedule_marks(self):
        client = self._client_as(self.other_instructor_user)
        payload = {"records": [{"student": str(self.student.id), "marks_obtained": 80, "is_absent": False}]}
        resp = client.post(f"/api/examinations/schedules/{self.schedule.id}/marks/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_student_can_view_own_results_only_after_publication(self):
        with tenant_context(self.school):
            ExamMark.objects.create(exam_schedule=self.schedule, student=self.student, marks_obtained=80)
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)

        client = self._client_as(self.student_user)
        resp = client.get(f"/api/examinations/students/{self.student.id}/results/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_student_cannot_view_another_students_results_idor(self):
        with tenant_context(self.school):
            ExamMark.objects.create(exam_schedule=self.schedule, student=self.student, marks_obtained=80)
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)

        client = self._client_as(self.student_user)
        resp = client.get(f"/api/examinations/students/{self.other_student.id}/results/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(
            resp.status_code, 403,
            "SECURITY REGRESSION: a student read another student's exam results by changing the UUID in the URL",
        )

    def test_unpublished_exam_has_no_result_for_student(self):
        """Result rows literally don't exist pre-publication - not just filtered."""
        with tenant_context(self.school):
            ExamMark.objects.create(exam_schedule=self.schedule, student=self.student, marks_obtained=80)
        client = self._client_as(self.student_user)
        resp = client.get(f"/api/examinations/students/{self.student.id}/results/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)


class ExamTenantIsolationTest(ExamFixtureMixin, TransactionTestCase):
    def test_tenant_a_cannot_access_tenant_b_examination_data(self):
        school_b = self._build_school(schema_name="exam_test_school_b", domain="examtestb.localhost")
        try:
            with tenant_context(school_b):
                exam_type_b = ExamType.objects.create(name="Final", order=1)
                examination_b = Examination.objects.create(
                    academic_year="2026", name="Final B", exam_type=exam_type_b,
                    start_date=datetime.date(2026, 6, 1), end_date=datetime.date(2026, 6, 10),
                )
                examination_b_id = examination_b.id

            owner_client = self._client_as(self.owner_user)
            resp = owner_client.get(f"/api/examinations/examinations/{examination_b_id}/", HTTP_HOST=self.DOMAIN)
            self.assertEqual(resp.status_code, 404)

            with tenant_context(self.school):
                self.assertFalse(
                    Examination.objects.filter(id=examination_b_id).exists(),
                    "TENANT ISOLATION FAILURE: tenant A can see tenant B's examination",
                )
        finally:
            connection.set_schema_to_public()
            school_b.delete(force_drop=True)


class ExamPermissionTest(ExamFixtureMixin, TransactionTestCase):
    def test_view_examinations_enforced(self):
        limited_user = self._build_user("exam_limited1", "staff")
        self._give_role_only(limited_user, [])
        client = self._client_as(limited_user)
        resp = client.get("/api/examinations/examinations/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_manage_examinations_enforced(self):
        limited_user = self._build_user("exam_limited2", "staff")
        self._give_role_only(limited_user, ["view_examinations"])
        client = self._client_as(limited_user)
        resp = client.post(
            "/api/examinations/examinations/",
            {"academic_year": "2026", "name": "X", "exam_type": str(self.exam_type.id), "start_date": "2026-01-01", "end_date": "2026-01-10"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_enter_marks_enforced(self):
        schedule = self._create_schedule()
        limited_user = self._build_user("exam_limited3", "staff")
        self._give_role_only(limited_user, ["view_examinations"])
        client = self._client_as(limited_user)
        payload = {"records": [{"student": str(self.student.id), "marks_obtained": 80, "is_absent": False}]}
        resp = client.post(f"/api/examinations/schedules/{schedule.id}/marks/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_manage_marks_enforced_for_lock(self):
        schedule = self._create_schedule()
        limited_user = self._build_user("exam_limited4", "staff")
        self._give_role_only(limited_user, ["view_examinations", "manage_examinations"])
        client = self._client_as(limited_user)
        resp = client.post(f"/api/examinations/schedules/{schedule.id}/lock/", {"is_locked": True}, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_publish_results_enforced(self):
        limited_user = self._build_user("exam_limited5", "staff")
        self._give_role_only(limited_user, ["view_examinations", "manage_examinations"])
        client = self._client_as(limited_user)
        resp = client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_view_results_enforced(self):
        with tenant_context(self.school):
            schedule = self._create_schedule()
            ExamMark.objects.create(exam_schedule=schedule, student=self.student, marks_obtained=80)
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)

        limited_user = self._build_user("exam_limited6", "staff")
        self._give_role_only(limited_user, [])
        client = self._client_as(limited_user)
        resp = client.get(f"/api/examinations/students/{self.student.id}/results/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_manage_grading_enforced(self):
        limited_user = self._build_user("exam_limited7", "staff")
        self._give_role_only(limited_user, ["view_examinations"])
        client = self._client_as(limited_user)
        resp = client.post(
            "/api/examinations/grading/",
            {"academic_year": "2028", "min_percentage": "0", "max_percentage": "100", "grade_label": "X"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_view_exam_reports_enforced(self):
        limited_user = self._build_user("exam_limited8", "staff")
        self._give_role_only(limited_user, ["view_examinations"])
        client = self._client_as(limited_user)
        resp = client.get(f"/api/examinations/reports/below-passing/?examination={self.examination.id}", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)


class ExamAuditTest(ExamFixtureMixin, TransactionTestCase):
    def _actions(self):
        with tenant_context(self.school):
            return list(AuditLog.objects.values_list("action", flat=True))

    def test_examination_crud_audited(self):
        owner_client = self._client_as(self.owner_user)
        create_resp = owner_client.post(
            "/api/examinations/examinations/",
            {"academic_year": "2026", "name": "Unit Test 1", "exam_type": str(self.exam_type.id), "start_date": "2026-02-01", "end_date": "2026-02-05"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        exam_id = create_resp.data["id"]
        owner_client.patch(f"/api/examinations/examinations/{exam_id}/", {"name": "Renamed"}, HTTP_HOST=self.DOMAIN, format="json")
        owner_client.delete(f"/api/examinations/examinations/{exam_id}/", HTTP_HOST=self.DOMAIN)
        actions = self._actions()
        self.assertIn("examination_created", actions)
        self.assertIn("examination_updated", actions)
        self.assertIn("examination_deleted", actions)

    def test_schedule_crud_audited(self):
        owner_client = self._client_as(self.owner_user)
        payload = {
            "examination": str(self.examination.id), "academic_year": "2026", "subject": str(self.subject.id),
            "section": str(self.section_a.id), "date": "2026-06-02", "start_time": "09:00", "end_time": "11:00",
            "max_marks": "100.00", "pass_marks": "40.00",
        }
        create_resp = owner_client.post("/api/examinations/schedules/", payload, HTTP_HOST=self.DOMAIN, format="json")
        schedule_id = create_resp.data["id"]
        owner_client.patch(f"/api/examinations/schedules/{schedule_id}/", {"max_marks": "90.00"}, HTTP_HOST=self.DOMAIN, format="json")
        owner_client.delete(f"/api/examinations/schedules/{schedule_id}/", HTTP_HOST=self.DOMAIN)
        actions = self._actions()
        self.assertIn("exam_schedule_created", actions)
        self.assertIn("exam_schedule_updated", actions)
        self.assertIn("exam_schedule_deleted", actions)

    def test_marks_submission_audited_once_not_per_student(self):
        schedule = self._create_schedule()
        client = self._client_as(self.instructor_user)
        payload = {
            "records": [
                {"student": str(self.student.id), "marks_obtained": 80, "is_absent": False},
                {"student": str(self.student2.id), "marks_obtained": 60, "is_absent": False},
            ]
        }
        client.post(f"/api/examinations/schedules/{schedule.id}/marks/", payload, HTTP_HOST=self.DOMAIN, format="json")
        with tenant_context(self.school):
            submitted_logs = AuditLog.objects.filter(action="marks_submitted")
            self.assertEqual(submitted_logs.count(), 1, "one bulk submission must produce exactly ONE audit row")
            self.assertEqual(submitted_logs.first().changes["total_records"], 2)

    def test_lock_unlock_audited(self):
        schedule = self._create_schedule()
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/schedules/{schedule.id}/lock/", {"is_locked": True}, HTTP_HOST=self.DOMAIN, format="json")
        owner_client.post(f"/api/examinations/schedules/{schedule.id}/lock/", {"is_locked": False}, HTTP_HOST=self.DOMAIN, format="json")
        actions = self._actions()
        self.assertIn("marks_locked", actions)
        self.assertIn("marks_unlocked", actions)

    def test_publication_audited(self):
        schedule = self._create_schedule()
        with tenant_context(self.school):
            ExamMark.objects.create(exam_schedule=schedule, student=self.student, marks_obtained=80)
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)
        self.assertIn("results_published", self._actions())

    def test_grading_config_change_audited(self):
        owner_client = self._client_as(self.owner_user)
        owner_client.post(
            "/api/examinations/grading/",
            {"academic_year": "2029", "min_percentage": "0", "max_percentage": "100", "grade_label": "X"},
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertIn("grading_config_changed", self._actions())


class ExamReportsTest(ExamFixtureMixin, TransactionTestCase):
    def test_below_passing_report(self):
        schedule = self._create_schedule()
        with tenant_context(self.school):
            ExamMark.objects.create(exam_schedule=schedule, student=self.student, marks_obtained=80)
            ExamMark.objects.create(exam_schedule=schedule, student=self.student2, marks_obtained=20)
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)

        resp = owner_client.get(f"/api/examinations/reports/below-passing/?examination={self.examination.id}", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        flagged = {s["student"] for s in resp.data["students"]}
        self.assertIn(str(self.student2.id), flagged)
        self.assertNotIn(str(self.student.id), flagged)

    def test_student_report_card(self):
        schedule = self._create_schedule()
        with tenant_context(self.school):
            ExamMark.objects.create(exam_schedule=schedule, student=self.student, marks_obtained=80)
        owner_client = self._client_as(self.owner_user)
        owner_client.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)

        resp = owner_client.get(f"/api/examinations/students/{self.student.id}/report-card/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["examinations"]), 1)
        self.assertEqual(resp.data["student"]["enrollment_id"], "ENR-EX-1")


class ExamResultNotificationTest(ExamFixtureMixin, TransactionTestCase):
    """
    Focused tests for the publish_examination() -> notifications outbox
    integration (examinations/services.py's _queue_result_published_notifications
    and _resolve_result_notification_recipients). CELERY_TASK_ALWAYS_EAGER=True
    during tests means queue_email()'s on_commit-deferred .delay() runs
    synchronously right after the publish transaction commits - no real
    worker/Redis connection is exercised here.

    self.student (fixture) has a linked portal account (exam_student_user,
    with an email) - eligible for a notification. self.student2 has a
    Profile with NO linked user_id - deliberately NOT eligible, used below
    to prove accounts without a resolvable email are skipped rather than
    guessed at.
    """

    def setUp(self):
        super().setUp()
        self.schedule = self._create_schedule()
        with tenant_context(self.school):
            ExamMark.objects.create(exam_schedule=self.schedule, student=self.student, marks_obtained=80)
            ExamMark.objects.create(exam_schedule=self.schedule, student=self.student2, marks_obtained=30)

        # A parent linked to self.student only - mirrors
        # notifications.tests.NotificationFixtureMixin's parent setup.
        self.parent_user = self._build_user("exam_notif_parent", "parent")
        with tenant_context(self.school):
            from families.models import Parent, StudentParentRelation

            parent_profile = Profile.objects.create(
                user_id=self.parent_user.id, first_name="Par", last_name="Ent"
            )
            self.parent = Parent.objects.create(profile=parent_profile, occupation="Engineer")
            StudentParentRelation.objects.create(
                student=self.student, parent=self.parent, relation_type="mother", is_primary_contact=True
            )

    def _publish(self):
        owner_client = self._client_as(self.owner_user)
        return owner_client.post(
            f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN
        )

    def test_publish_still_creates_results(self):
        """Baseline regression: the notification integration must not
        change what publication itself persists."""
        resp = self._publish()
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            self.assertEqual(ExamResult.objects.filter(examination=self.examination).count(), 2)

    def test_publish_queues_notification_for_student_with_portal_account(self):
        from notifications.models import EmailOutboxEvent

        self._publish()
        with tenant_context(self.school):
            events = EmailOutboxEvent.objects.filter(to_email=self.student_user.email)
            self.assertEqual(events.count(), 1)
            self.assertIn(self.examination.name, events.first().body)

    def test_publish_queues_notification_for_linked_parent(self):
        from notifications.models import EmailOutboxEvent

        self._publish()
        with tenant_context(self.school):
            events = EmailOutboxEvent.objects.filter(to_email=self.parent_user.email)
            self.assertEqual(events.count(), 1)
            self.assertIn(self.student.profile.first_name, events.first().body)

    def test_student_without_portal_account_gets_no_notification(self):
        """student2's Profile has no linked user_id - there is no email to
        send to, and none must be invented."""
        from notifications.models import EmailOutboxEvent

        self._publish()
        with tenant_context(self.school):
            # Only student (1) + parent (1) are eligible - student2 contributes none.
            self.assertEqual(EmailOutboxEvent.objects.count(), 2)

    def test_unrelated_student_does_not_receive_a_notification(self):
        """self.other_student has no ExamMark at all for this examination -
        it must never receive a result notification for it."""
        from notifications.models import EmailOutboxEvent

        self._publish()
        with tenant_context(self.school):
            self.assertFalse(
                EmailOutboxEvent.objects.filter(to_email=self.other_student_user.email).exists()
            )

    def test_notification_body_omits_marks_and_grades(self):
        """Privacy requirement: the email must direct the recipient to the
        portal, never carry the actual marks/percentage/grade."""
        from notifications.models import EmailOutboxEvent

        self._publish()
        with tenant_context(self.school):
            for event in EmailOutboxEvent.objects.all():
                self.assertNotIn("80", event.body)
                self.assertNotIn("30", event.body)
                self.assertNotIn("percentage", event.body.lower())
                self.assertNotIn("grade", event.body.lower())
                self.assertIn("log in", event.body.lower())

    def test_notification_delivery_failure_does_not_roll_back_publication(self):
        """The core transactional requirement: an email SEND failure (as
        opposed to a failure queuing it) must never affect the already-
        committed publication - EmailOutboxEvent's own retry/failure state
        machine owns that failure from here."""
        resp = self._publish_with_failing_smtp()
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            exam = Examination.objects.get(id=self.examination.id)
            self.assertTrue(exam.is_published)
            self.assertEqual(ExamResult.objects.filter(examination=self.examination).count(), 2)

    def _publish_with_failing_smtp(self):
        from unittest import mock

        with mock.patch("notifications.tasks.send_mail", side_effect=Exception("smtp down")):
            return self._publish()

    def test_failed_publication_creates_no_notification_events(self):
        """If result generation itself fails, nothing - not ExamResult,
        not is_published, not any EmailOutboxEvent - may survive; proves
        the notification queuing is genuinely inside the same atomic unit,
        not a separate side-channel write.

        Patches calculate_examination_results_bulk() (Phase 9G's bulk
        calculation entry point used by publish_examination()), not
        calculate_student_examination_result() - the latter is no longer
        on publish_examination()'s call path (it remains, untouched, as
        the standalone per-student calculation seed_demo_school.py calls
        directly). The assertion being proven - a calculation failure
        anywhere rolls back the whole publish - is unchanged."""
        from unittest import mock

        from notifications.models import EmailOutboxEvent

        with mock.patch(
            "examinations.services.calculate_examination_results_bulk",
            side_effect=RuntimeError("boom"),
        ):
            resp = self._publish()
        self.assertEqual(resp.status_code, 400)
        with tenant_context(self.school):
            self.assertFalse(Examination.objects.get(id=self.examination.id).is_published)
            self.assertEqual(ExamResult.objects.filter(examination=self.examination).count(), 0)
            self.assertEqual(EmailOutboxEvent.objects.count(), 0)

    def test_republish_does_not_create_duplicate_notifications(self):
        """The existing is_published guard is this feature's idempotency
        mechanism - a second publish attempt must be rejected exactly as
        before, and must not queue a second round of notifications."""
        from notifications.models import EmailOutboxEvent

        first = self._publish()
        self.assertEqual(first.status_code, 200, first.data)
        with tenant_context(self.school):
            count_after_first = EmailOutboxEvent.objects.count()

        second = self._publish()
        self.assertEqual(second.status_code, 400)
        with tenant_context(self.school):
            self.assertEqual(EmailOutboxEvent.objects.count(), count_after_first)

    def test_results_published_audit_entry_unchanged(self):
        """The existing results_published audit event remains the
        source-of-truth publication audit entry - no second,
        notification-specific audit event is introduced."""
        from core.models import AuditLog

        self._publish()
        with tenant_context(self.school):
            actions = list(AuditLog.objects.values_list("action", flat=True))
            self.assertIn("results_published", actions)
            self.assertEqual(actions.count("results_published"), 1)
            self.assertNotIn("notification_queued", actions)
            self.assertNotIn("results_notification_sent", actions)

    def test_publish_permission_still_enforced(self):
        """Existing authorization is untouched by this feature."""
        limited_user = self._build_user("exam_notif_limited", "staff")
        self._give_role_only(limited_user, ["view_examinations", "manage_examinations"])
        client = self._client_as(limited_user)
        resp = client.post(
            f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)


class ExamResultNotificationTenantIsolationTest(ExamFixtureMixin, TransactionTestCase):
    def test_publishing_in_tenant_b_does_not_leak_notification_into_tenant_a(self):
        from academics.models import AcademicLevel, Program, Section, Subject
        from notifications.models import EmailOutboxEvent

        from .services import publish_examination

        school_b = self._build_school(schema_name="exam_notif_school_b", domain="examnotifb.localhost")
        try:
            with tenant_context(school_b):
                program = Program.objects.create(name="HS2", code="HS2EX")
                level = AcademicLevel.objects.create(program=program, name="Grade 10", order=1)
                section = Section.objects.create(level=level, name="A", capacity=40)
                subject = Subject.objects.create(level=level, name="Math", code="MTH2")
                exam_type_b = ExamType.objects.create(name="Final", order=1)
                examination_b = Examination.objects.create(
                    academic_year="2026", name="Final B", exam_type=exam_type_b,
                    start_date=datetime.date(2026, 6, 1), end_date=datetime.date(2026, 6, 10),
                )
                schedule_b = ExamSchedule.objects.create(
                    examination=examination_b, academic_year="2026", subject=subject, section=section,
                    date=datetime.date(2026, 6, 2), start_time=datetime.time(9, 0), end_time=datetime.time(11, 0),
                    max_marks=Decimal("100"), pass_marks=Decimal("40"),
                )
                student_user_b = User.objects.create_user(
                    username="examnotifb_student", email="b_student@examnotifb.com", password="Pass1234!"
                )
                profile_b = Profile.objects.create(
                    user_id=student_user_b.id, first_name="B", last_name="Student"
                )
                student_b = Student.objects.create(
                    profile=profile_b, enrollment_id="ENR-NB-1", status="active"
                )
                ExamMark.objects.create(exam_schedule=schedule_b, student=student_b, marks_obtained=80)

                publish_examination(examination_b)

                self.assertEqual(
                    EmailOutboxEvent.objects.filter(to_email="b_student@examnotifb.com").count(), 1
                )

            with tenant_context(self.school):
                self.assertEqual(
                    EmailOutboxEvent.objects.filter(to_email="b_student@examnotifb.com").count(),
                    0,
                    "TENANT ISOLATION FAILURE: tenant B's notification leaked into tenant A's schema",
                )
        finally:
            connection.set_schema_to_public()
            school_b.delete(force_drop=True)


class ExamPublicationBulkOptimizationTests(ExamFixtureMixin, TransactionTestCase):
    """
    Phase 9G: regression tests for publish_examination()'s bulk result
    calculation (calculate_examination_results_bulk() in services.py),
    which replaces the previous per-student loop that re-queried
    ExamSchedule, ExamMark and GradeBoundary for every single student.
    """

    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.schedule1 = self._create_schedule(subject=self.subject, date=datetime.date(2026, 6, 2))
            self.schedule2 = self._create_schedule(subject=self.second_subject, date=datetime.date(2026, 6, 3))

    def _mark(self, schedule, student, **kwargs):
        with tenant_context(self.school):
            return ExamMark.objects.create(exam_schedule=schedule, student=student, **kwargs)

    # --- A. Result correctness + C. Multiple subjects ----------------------

    def test_result_correct_across_multiple_subjects(self):
        self._mark(self.schedule1, self.student, marks_obtained=Decimal("80"))
        self._mark(self.schedule2, self.student, marks_obtained=Decimal("60"))

        from .services import publish_examination

        with tenant_context(self.school):
            publish_examination(Examination.objects.get(id=self.examination.id))
            result = ExamResult.objects.get(examination=self.examination, student=self.student)
            self.assertEqual(result.total_marks_obtained, Decimal("140"))
            self.assertEqual(result.total_max_marks, Decimal("200"))
            self.assertEqual(result.percentage, Decimal("70.00"))
            self.assertEqual(result.overall_grade, "B")
            self.assertTrue(result.is_pass)
            self.assertEqual(len(result.subject_breakdown), 2)

    # --- B. Multiple students, correctly associated ------------------------

    def test_multiple_students_each_get_their_own_correct_result(self):
        self._mark(self.schedule1, self.student, marks_obtained=Decimal("80"))
        self._mark(self.schedule2, self.student, marks_obtained=Decimal("60"))
        self._mark(self.schedule1, self.student2, marks_obtained=Decimal("30"))
        # student2 has no mark at all on schedule2 - "not applicable", not a zero.

        from .services import publish_examination

        with tenant_context(self.school):
            publish_examination(Examination.objects.get(id=self.examination.id))

            r1 = ExamResult.objects.get(examination=self.examination, student=self.student)
            self.assertEqual(r1.percentage, Decimal("70.00"))
            self.assertTrue(r1.is_pass)

            r2 = ExamResult.objects.get(examination=self.examination, student=self.student2)
            self.assertEqual(r2.total_max_marks, Decimal("100"))  # only schedule1 counted
            self.assertEqual(r2.percentage, Decimal("30.00"))
            self.assertFalse(r2.is_pass)
            self.assertEqual(len(r2.subject_breakdown), 1)

            self.assertEqual(ExamResult.objects.filter(examination=self.examination).count(), 2)

    # --- D. Grade boundaries: below / exactly at / above --------------------

    def test_grade_boundaries_exact_edges(self):
        """Fixture boundaries: F [0, 39.99], B [40, 89.99], A+ [90, 100].
        Using a single 100-mark schedule makes percentage == marks_obtained,
        so these are exact-edge values, not approximations."""
        edge_students = []
        for i, marks in enumerate(["39.99", "40.00", "89.99", "90.00"]):
            with tenant_context(self.school):
                profile = Profile.objects.create(first_name=f"Edge{i}", last_name="Student")
                student = Student.objects.create(profile=profile, enrollment_id=f"ENR-EDGE-{i}", status="active")
                StudentLevel.objects.create(
                    student=student, level=self.section_a.level, section=self.section_a,
                    academic_year="2026", is_current=True,
                )
            self._mark(self.schedule1, student, marks_obtained=Decimal(marks))
            edge_students.append((student, marks))

        from .services import publish_examination

        with tenant_context(self.school):
            publish_examination(Examination.objects.get(id=self.examination.id))

            expected_grades = {"39.99": "F", "40.00": "B", "89.99": "B", "90.00": "A+"}
            for student, marks in edge_students:
                result = ExamResult.objects.get(examination=self.examination, student=student)
                self.assertEqual(result.overall_grade, expected_grades[marks], f"marks={marks}")

    # --- E. Missing/edge marks: absent, zero, missing subject ---------------

    def test_absent_and_zero_marks_handled_correctly(self):
        self._mark(self.schedule1, self.student, is_absent=True)
        self._mark(self.schedule2, self.student, marks_obtained=Decimal("0"))

        from .services import publish_examination

        with tenant_context(self.school):
            publish_examination(Examination.objects.get(id=self.examination.id))
            result = ExamResult.objects.get(examination=self.examination, student=self.student)

            self.assertFalse(result.is_pass)
            self.assertEqual(result.total_marks_obtained, Decimal("0"))
            self.assertEqual(result.total_max_marks, Decimal("200"))  # both subjects count toward max

            breakdown_by_subject = {b["subject"]: b for b in result.subject_breakdown}
            self.assertTrue(breakdown_by_subject[str(self.subject.id)]["is_absent"])
            self.assertIsNone(breakdown_by_subject[str(self.subject.id)]["marks_obtained"])
            self.assertEqual(breakdown_by_subject[str(self.second_subject.id)]["marks_obtained"], 0.0)
            self.assertFalse(breakdown_by_subject[str(self.second_subject.id)]["is_pass"])

    def test_student_with_no_marks_at_all_is_not_published(self):
        """other_student has no ExamMark for this examination at all -
        publication must produce no ExamResult for them."""
        self._mark(self.schedule1, self.student, marks_obtained=Decimal("80"))

        from .services import publish_examination

        with tenant_context(self.school):
            publish_examination(Examination.objects.get(id=self.examination.id))
            self.assertFalse(
                ExamResult.objects.filter(examination=self.examination, student=self.other_student).exists()
            )

    # --- F. Existing-result / write behavior --------------------------------

    def test_publish_only_ever_creates_never_updates(self):
        """publish_examination() has no update/upsert path - is_published
        guards against ever re-entering the write loop. Confirms the bulk
        rewrite preserves this create-only, single-pass write behavior."""
        self._mark(self.schedule1, self.student, marks_obtained=Decimal("80"))

        from .services import publish_examination

        with tenant_context(self.school):
            publish_examination(Examination.objects.get(id=self.examination.id))
            self.assertEqual(ExamResult.objects.filter(examination=self.examination).count(), 1)

    # --- G. Re-publication / idempotency -------------------------------------

    def test_republish_rejected_and_results_unchanged(self):
        self._mark(self.schedule1, self.student, marks_obtained=Decimal("80"))

        from rest_framework import serializers as drf_serializers

        from .services import publish_examination

        with tenant_context(self.school):
            exam = Examination.objects.get(id=self.examination.id)
            publish_examination(exam)
            first_result_id = ExamResult.objects.get(examination=self.examination, student=self.student).id

            exam.refresh_from_db()
            with self.assertRaises(drf_serializers.ValidationError):
                publish_examination(exam)

            self.assertEqual(ExamResult.objects.filter(examination=self.examination).count(), 1)
            self.assertEqual(
                ExamResult.objects.get(examination=self.examination, student=self.student).id, first_result_id,
            )

    # --- Query-scaling regression -------------------------------------------

    def test_publish_calculation_query_count_does_not_scale_with_student_count(self):
        """
        The in-scope target of Phase 9G: the result-calculation-and-write
        portion of publish_examination() must not re-query ExamSchedule/
        ExamMark/GradeBoundary per student.

        _queue_result_published_notifications() is mocked to a no-op here
        deliberately: its own recipient resolution (student.profile.user,
        families.StudentParentRelation) is a SEPARATE, pre-existing N+1
        that touches the explicitly out-of-scope email/outbox subsystem
        (see Phase 9G's strict-scope rules) - documented under "Out of
        Scope / Follow-up" in the Phase 9G report, not fixed here. Mocking
        it isolates exactly the calculation/write path this phase targets.
        """
        from unittest import mock

        from .services import publish_examination

        def _make_exam_with_students(n, label):
            with tenant_context(self.school):
                exam_type = ExamType.objects.create(name=f"Scale{label}", order=1)
                exam = Examination.objects.create(
                    academic_year="2026", name=f"Scale {label}", exam_type=exam_type,
                    start_date=datetime.date(2026, 6, 1), end_date=datetime.date(2026, 6, 10),
                )
                sched1 = ExamSchedule.objects.create(
                    examination=exam, academic_year="2026", subject=self.subject, section=self.section_a,
                    date=datetime.date(2026, 6, 2), start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
                    max_marks=Decimal("100"), pass_marks=Decimal("40"),
                )
                sched2 = ExamSchedule.objects.create(
                    examination=exam, academic_year="2026", subject=self.second_subject, section=self.section_a,
                    date=datetime.date(2026, 6, 3), start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
                    max_marks=Decimal("100"), pass_marks=Decimal("40"),
                )
                students = []
                for i in range(n):
                    profile = Profile.objects.create(first_name=f"{label}{i}", last_name="Student")
                    student = Student.objects.create(profile=profile, enrollment_id=f"ENR-SCALE{label}-{i}", status="active")
                    StudentLevel.objects.create(
                        student=student, level=self.section_a.level, section=self.section_a,
                        academic_year="2026", is_current=True,
                    )
                    ExamMark.objects.create(exam_schedule=sched1, student=student, marks_obtained=Decimal("75"))
                    ExamMark.objects.create(exam_schedule=sched2, student=student, marks_obtained=Decimal("65"))
                    students.append(student)
                return exam

        small_exam = _make_exam_with_students(10, "SM")
        large_exam = _make_exam_with_students(40, "LG")

        with mock.patch("examinations.services._queue_result_published_notifications"):
            with tenant_context(self.school):
                with CaptureQueriesContext(connection) as small_ctx:
                    publish_examination(small_exam)

            with tenant_context(self.school):
                with CaptureQueriesContext(connection) as large_ctx:
                    publish_examination(large_exam)

        small_count = len(small_ctx.captured_queries)
        large_count = len(large_ctx.captured_queries)

        with tenant_context(self.school):
            self.assertEqual(ExamResult.objects.filter(examination=small_exam).count(), 10)
            self.assertEqual(ExamResult.objects.filter(examination=large_exam).count(), 40)

        # A small constant difference is acceptable; there must be no
        # per-student query growth. The old code cost roughly 7-8 extra
        # queries PER additional student (30 extra students would have
        # added 200+ queries - see Phase 9G report's measured before/after).
        self.assertLessEqual(large_count, small_count + 3, f"small={small_count} large={large_count}")


class ReportCardAndTranscriptTests(ExamFixtureMixin, TransactionTestCase):
    """
    Test suite for Phase 2: Printable Student Report Cards and Academic Transcripts.
    Verifies:
    - Object-level authorization for students, parents, instructors, staff, and owner
    - Weighted GPA calculations according to configured grade points and subject credits
    - Handling of unconfigured grade points (returns None, never silent zero)
    - Chronological multi-year transcript ordering and cumulative totals
    - Integration with attendance percentage and non-reversed promotion records
    - Immutability of published ExamResult snapshots
    """

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        with tenant_context(self.school):
            # Give second subject 2.0 credits, first subject 1.0 credit
            self.subject.credits = Decimal("1.0")
            self.subject.save()
            self.second_subject.credits = Decimal("2.0")
            self.second_subject.save()

            # Create schedules for student
            self.sched1 = ExamSchedule.objects.create(
                examination=self.examination, academic_year="2026", subject=self.subject, section=self.section_a,
                date=datetime.date(2026, 6, 2), start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
                max_marks=Decimal("100"), pass_marks=Decimal("40"),
            )
            self.sched2 = ExamSchedule.objects.create(
                examination=self.examination, academic_year="2026", subject=self.second_subject, section=self.section_a,
                date=datetime.date(2026, 6, 3), start_time=datetime.time(9, 0), end_time=datetime.time(10, 0),
                max_marks=Decimal("100"), pass_marks=Decimal("40"),
            )

            # Enter marks: Subject 1: 95% (A+, gp 4.0, cr 1.0), Subject 2: 70% (B, gp 3.0, cr 2.0)
            ExamMark.objects.create(exam_schedule=self.sched1, student=self.student, marks_obtained=Decimal("95"))
            ExamMark.objects.create(exam_schedule=self.sched2, student=self.student, marks_obtained=Decimal("70"))

            from .services import publish_examination
            from unittest import mock
            with mock.patch("examinations.services._queue_result_published_notifications"):
                publish_examination(self.examination)

    def test_gpa_calculation_weighted(self):
        """GPA = (4.0 * 1.0 + 3.0 * 2.0) / (1.0 + 2.0) = 10.0 / 3.0 = 3.33"""
        from .services import calculate_gpa
        with tenant_context(self.school):
            result = ExamResult.objects.get(examination=self.examination, student=self.student)
            gpa = calculate_gpa(result.subject_breakdown, "2026")
            self.assertIsNotNone(gpa)
            self.assertEqual(gpa, 3.33)

    def test_gpa_calculation_unconfigured_grade_points_returns_none(self):
        """If any GradeBoundary for that year has grade_point=None, GPA must return None."""
        from .services import calculate_gpa
        with tenant_context(self.school):
            b = GradeBoundary.objects.filter(academic_year="2026", grade_label="A+").first()
            b.grade_point = None
            b.save()

            result = ExamResult.objects.get(examination=self.examination, student=self.student)
            gpa = calculate_gpa(result.subject_breakdown, "2026")
            self.assertIsNone(gpa)

    def test_gpa_calculation_absent_subject_returns_none(self):
        """If a student was absent or mark is incomplete, GPA must return None (incomplete)."""
        from .services import calculate_gpa
        breakdown = [
            {"subject": str(self.subject.id), "subject_name": "Math", "marks_obtained": None, "max_marks": 100.0,
             "percentage": None, "grade": None, "is_absent": True, "is_pass": False}
        ]
        with tenant_context(self.school):
            gpa = calculate_gpa(breakdown, "2026")
            self.assertIsNone(gpa)

    def test_student_can_view_own_report_card(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(
            f"/api/examinations/students/{self.student.id}/report-card/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["student"]["id"], str(self.student.id))
        self.assertEqual(data["academic_year"], "2026")
        self.assertIn("institution", data)
        self.assertIn("summary", data)
        self.assertIn("attendance", data)
        self.assertEqual(len(data["examinations"]), 1)
        self.assertEqual(data["examinations"][0]["gpa"], 3.33)

    def test_student_cannot_view_other_student_report_card(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(
            f"/api/examinations/students/{self.student2.id}/report-card/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_without_permission_cannot_view_report_card(self):
        user = self._build_user("exam_no_perm_staff", "staff")
        self.client.force_authenticate(user=user)
        response = self.client.get(
            f"/api/examinations/students/{self.student.id}/report-card/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_with_view_results_can_view_report_card(self):
        user = self._build_user("exam_results_staff", "staff")
        self._give_role_only(user, ["view_results"])
        self.client.force_authenticate(user=user)
        response = self.client.get(
            f"/api/examinations/students/{self.student.id}/report-card/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["student"]["id"], str(self.student.id))

    def test_owner_can_view_student_report_card(self):
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.get(
            f"/api/examinations/students/{self.student.id}/report-card/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(response.status_code, 200)

    def test_student_can_view_own_transcript(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(
            f"/api/examinations/students/{self.student.id}/transcript/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["student"]["id"], str(self.student.id))
        self.assertIn("years", data)
        self.assertIn("cumulative_summary", data)
        self.assertIn("issuance", data)
        self.assertEqual(len(data["years"]), 1)
        self.assertEqual(data["years"][0]["academic_year"], "2026")
        self.assertEqual(data["cumulative_summary"]["cgpa"], 3.33)

    def test_student_cannot_view_other_student_transcript(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(
            f"/api/examinations/students/{self.student2.id}/transcript/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(response.status_code, 403)

    def test_published_results_are_immutable_during_report_card_generation(self):
        """
        Verify that generating a report card does not mutate or recalculate
        the stored ExamResult record or its subject_breakdown.
        """
        with tenant_context(self.school):
            before = ExamResult.objects.get(examination=self.examination, student=self.student)
            before_obtained = before.total_marks_obtained
            before_percentage = before.percentage
            before_breakdown = list(before.subject_breakdown)

        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(
            f"/api/examinations/students/{self.student.id}/report-card/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(response.status_code, 200)

        with tenant_context(self.school):
            after = ExamResult.objects.get(examination=self.examination, student=self.student)
            self.assertEqual(after.total_marks_obtained, before_obtained)
            self.assertEqual(after.percentage, before_percentage)
            self.assertEqual(after.subject_breakdown, before_breakdown)

