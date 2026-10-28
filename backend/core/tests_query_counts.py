"""
List endpoints must cost a fixed number of queries however many rows they return (no N+1).
Each test measures a request with a few rows, adds more rows, and expects the same count.
"""
import datetime
import uuid

from django.db import connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, Program, Section, Subject, SubjectAssignment
from accounts.models import User
from attendance.models import AttendanceSession, StudentAttendance
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from staff.models import Instructor, StaffMember
from students.models import Student
from timetable.models import Period, TimetableEntry

YEAR = "2026-2027"


class QueryCountTests(TransactionTestCase):
    SCHEMA = "query_count_school"
    DOMAIN = "query-count.localhost"

    def setUp(self):
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Query Count School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        owner = User.objects.create_user(username="qc_owner", email="qc_owner@qc.test", password="Pass1234!")
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            UserRole.objects.create(user=owner, role=role)
            program = Program.objects.create(name="Primary", code="QC")
            self.level = AcademicLevel.objects.create(program=program, name="Class 1", order=1)
            self.section = Section.objects.create(level=self.level, name="A", capacity=40)
        self.client = APIClient()
        response = self.client.post(
            "/api/auth/login/", {"username": "qc_owner", "password": "Pass1234!"}, HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(response.status_code, 200)
        self.n = 0

    def tearDown(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name=self.SCHEMA):
            school.delete(force_drop=True)
        User.objects.filter(username="qc_owner").delete()

    # --- builders (run inside the school's schema) ---

    def _profile(self, first="Row"):
        self.n += 1
        return Profile.objects.create(first_name=f"{first}{self.n}", last_name="Test", gender="male")

    def _student(self):
        return Student.objects.create(profile=self._profile("Student"), enrollment_id=f"QC-{uuid.uuid4().hex[:8]}")

    def _instructor(self):
        staff = StaffMember.objects.create(
            profile=self._profile("Teacher"), employee_id=f"E-{uuid.uuid4().hex[:8]}", designation="Teacher"
        )
        return Instructor.objects.create(staff_member=staff, specialization="Maths")

    def _subject(self):
        self.n += 1
        return Subject.objects.create(level=self.level, name=f"Subject {self.n}", code=f"S{self.n}")

    def _period(self):
        self.n += 1
        return Period.objects.create(
            academic_year=YEAR, name=f"P{self.n}", order=self.n,
            start_time=datetime.time(8, 0), end_time=datetime.time(8, 40),
        )

    def _count(self, url):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url, HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        return len(ctx.captured_queries)

    def _assert_flat(self, url, add_rows):
        with tenant_context(self.school):
            add_rows(2)
        self._count(url)  # warm-up: first calls create one-off rows (e.g. attendance settings)
        few = self._count(url)
        with tenant_context(self.school):
            add_rows(4)
        many = self._count(url)
        self.assertEqual(few, many, f"{url}: {few} queries for a few rows but {many} for more")

    # --- endpoints ---

    def test_parents_list(self):
        def add(k):
            for _ in range(k):
                parent = Parent.objects.create(profile=self._profile("Parent"))
                for _ in range(2):
                    StudentParentRelation.objects.create(student=self._student(), parent=parent, relation_type="father")
        self._assert_flat("/api/families/parents/", add)

    def test_staff_list(self):
        def add(k):
            for _ in range(k):
                self._instructor()
        self._assert_flat("/api/staff/members/", add)

    def test_subject_assignments(self):
        def add(k):
            for _ in range(k):
                SubjectAssignment.objects.create(section=self.section, subject=self._subject(), instructor=self._instructor())
        self._assert_flat("/api/academics/assignments/", add)

    def _entries(self, k, instructor=None):
        for _ in range(k):
            TimetableEntry.objects.create(
                academic_year=YEAR, section=self.section, subject=self._subject(),
                instructor=instructor or self._instructor(), day_of_week=0, period=self._period(),
            )

    def test_section_timetable(self):
        self._assert_flat(f"/api/timetable/sections/{self.section.id}/timetable/", self._entries)

    def test_instructor_timetable(self):
        with tenant_context(self.school):
            teacher = self._instructor()
        self._assert_flat(
            f"/api/timetable/instructors/{teacher.id}/timetable/", lambda k: self._entries(k, instructor=teacher)
        )

    def test_below_threshold_report(self):
        def add(k):
            for _ in range(k):
                student = self._student()
                for day in range(3):
                    session, _ = AttendanceSession.objects.get_or_create(
                        section=self.section, date=datetime.date(2026, 7, 1) + datetime.timedelta(days=day),
                        defaults={"academic_year": YEAR},
                    )
                    StudentAttendance.objects.create(session=session, student=student, status="absent")
        self._assert_flat("/api/attendance/reports/below-threshold/", add)

    def test_below_threshold_report_lists_only_students_under_the_threshold(self):
        with tenant_context(self.school):
            low, high = self._student(), self._student()
            for day in range(4):
                session = AttendanceSession.objects.create(
                    section=self.section, date=datetime.date(2026, 7, 1) + datetime.timedelta(days=day), academic_year=YEAR
                )
                StudentAttendance.objects.create(session=session, student=low, status="absent" if day else "present")
                StudentAttendance.objects.create(session=session, student=high, status="present")
        response = self.client.get(
            "/api/attendance/reports/below-threshold/", {"section": str(self.section.id)}, HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(response.status_code, 200)
        rows = response.data["students"]
        self.assertEqual([r["student"] for r in rows], [str(low.id)])
        self.assertEqual(rows[0]["percentage"], 25.0)
        self.assertEqual(rows[0]["enrollment_id"], low.enrollment_id)
