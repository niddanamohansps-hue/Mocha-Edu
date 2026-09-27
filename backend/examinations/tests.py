import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
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
