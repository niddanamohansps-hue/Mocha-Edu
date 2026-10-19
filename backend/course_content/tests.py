from accounts.models import User
import uuid as uuid_module

from django.db import connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django_tenants.utils import tenant_context

from academics.models import AcademicLevel, Program, Section, Subject
from organizations.models import Domain, Organization
from profiles.models import Profile
from staff.models import StaffMember
from students.models import Student, StudentLevel

from .models import CourseContent, SubjectEnrollment
from .views import can_student_access_content, filter_content_accessible_to_student


class CourseContentAccessFixtureMixin:
    """
    Minimal tenant + academic structure + students, for testing
    can_student_access_content()/filter_content_accessible_to_student()
    directly against model objects. No API client is needed here - both
    functions are plain authorization/query-shape helpers, not endpoints.
    """

    SCHEMA_NAME = "coursecontent_test_school"
    DOMAIN = "coursecontenttest.localhost"

    def _build_school(self):
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{self.SCHEMA_NAME}" CASCADE')
        Organization.objects.filter(schema_name=self.SCHEMA_NAME).delete()
        school = Organization.objects.create(
            schema_name=self.SCHEMA_NAME, name="Course Content Test School"
        )
        Domain.objects.create(domain=self.DOMAIN, tenant=school, is_primary=True)
        return school

    def _make_student(self, first_name, last_name, *, level=None, section=None):
        profile = Profile.objects.create(first_name=first_name, last_name=last_name)
        student = Student.objects.create(
            profile=profile, enrollment_id=f"{first_name.upper()}-{uuid_module.uuid4().hex[:6]}"
        )
        if level is not None:
            StudentLevel.objects.create(
                student=student, level=level, section=section, academic_year="2026", is_current=True
            )
        return student

    def _make_content(self, title, **targeting):
        content = CourseContent.objects.create(
            title=title,
            description="d",
            content_type="note",
            created_by=self.staff_member,
            is_published=True,
        )
        if "specific_students" in targeting:
            content.specific_students.set(targeting["specific_students"])
        if "target_sections" in targeting:
            content.target_sections.set(targeting["target_sections"])
        if "target_levels" in targeting:
            content.target_levels.set(targeting["target_levels"])
        if "target_programs" in targeting:
            content.target_programs.set(targeting["target_programs"])
        if "target_subjects" in targeting:
            content.target_subjects.set(targeting["target_subjects"])
        return content

    def setUp(self):
        self.school = self._build_school()
        with tenant_context(self.school):
            self.program = Program.objects.create(name="High School", code="HS")
            self.level = AcademicLevel.objects.create(program=self.program, name="Grade 10", order=1)
            self.other_level = AcademicLevel.objects.create(program=self.program, name="Grade 11", order=2)
            self.section_a = Section.objects.create(level=self.level, name="A", capacity=40)
            self.section_b = Section.objects.create(level=self.level, name="B", capacity=40)
            self.subject = Subject.objects.create(level=self.level, name="Math", code="MTH101")

            staff_profile = Profile.objects.create(first_name="Cara", last_name="Teach")
            self.staff_member = StaffMember.objects.create(
                profile=staff_profile, employee_id="EMP-CC-1", designation="Teacher"
            )

            self.student = self._make_student("Ada", "Lovelace", level=self.level, section=self.section_a)
            self.other_student = self._make_student("Bob", "Jones", level=self.level, section=self.section_b)

    def tearDown(self):
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{self.SCHEMA_NAME}" CASCADE')
        Organization.objects.filter(schema_name=self.SCHEMA_NAME).delete()


class CanStudentAccessContentEquivalenceTests(CourseContentAccessFixtureMixin, TransactionTestCase):
    """
    Proves filter_content_accessible_to_student() returns exactly the same
    accessible-id set as calling the original can_student_access_content()
    once per item, across every targeting rule and combination - the
    regression guarantee that the batched optimization changed nothing
    about WHO can access WHAT.
    """

    def test_equivalence_across_targeting_combinations(self):
        with tenant_context(self.school):
            specific = self._make_content("Specific", specific_students=[self.student])
            section_targeted = self._make_content("SectionTargeted", target_sections=[self.section_a])
            level_targeted = self._make_content("LevelTargeted", target_levels=[self.level])
            program_targeted = self._make_content("ProgramTargeted", target_programs=[self.program])
            no_targeting = self._make_content("NoTargeting")
            other_section_targeted = self._make_content("OtherSectionTargeted", target_sections=[self.section_b])
            other_level_targeted = self._make_content("OtherLevelTargeted", target_levels=[self.other_level])
            other_student_targeted = self._make_content(
                "OtherStudentTargeted", specific_students=[self.other_student]
            )
            # Doesn't match on section (targets B, student is in A) but DOES
            # match on level - combination case: must still be accessible.
            multi_rule = self._make_content(
                "MultiRule", target_sections=[self.section_b], target_levels=[self.level]
            )

            all_content = list(CourseContent.objects.all())
            expected = {c.id for c in all_content if can_student_access_content(self.student, c)}
            actual = set(filter_content_accessible_to_student(self.student, CourseContent.objects.all()))

            self.assertEqual(actual, expected)
            self.assertIn(specific.id, expected)
            self.assertIn(section_targeted.id, expected)
            self.assertIn(level_targeted.id, expected)
            self.assertIn(program_targeted.id, expected)
            self.assertIn(multi_rule.id, expected)
            self.assertNotIn(no_targeting.id, expected)
            self.assertNotIn(other_section_targeted.id, expected)
            self.assertNotIn(other_level_targeted.id, expected)
            self.assertNotIn(other_student_targeted.id, expected)

    def test_student_with_no_current_enrollment_still_gets_subject_and_specific_access(self):
        """Case E/F: no StudentLevel row at all. Specific-student and
        subject targeting must still work; section/level/program targeting
        (which require a current enrollment) must not."""
        with tenant_context(self.school):
            lone_student = self._make_student("Lone", "Student")  # no level/section -> no enrollment row
            SubjectEnrollment.objects.create(student=lone_student, subject=self.subject, academic_year="2026")

            specific_targeted = self._make_content("SpecificForLone", specific_students=[lone_student])
            subject_targeted = self._make_content("SubjectTargeted", target_subjects=[self.subject])
            section_targeted = self._make_content("SectionTargeted", target_sections=[self.section_a])
            unrelated = self._make_content("Unrelated")

            for content, expect_true in [
                (specific_targeted, True),
                (subject_targeted, True),
                (section_targeted, False),
                (unrelated, False),
            ]:
                self.assertEqual(
                    can_student_access_content(lone_student, content), expect_true, content.title
                )

            accessible = set(
                filter_content_accessible_to_student(lone_student, CourseContent.objects.all())
            )
            self.assertEqual(
                accessible, {specific_targeted.id, subject_targeted.id}
            )

    def test_unpublished_content_excluded_by_queryset_not_by_the_access_function(self):
        """Case J: can_student_access_content() itself has no is_published
        check - that filtering happens in the ViewSet's queryset (already
        .filter(is_published=True) before this helper runs). An unpublished,
        otherwise-fully-targeted item is still "accessible" by the function
        in isolation; it's excluded only because callers never pass
        unpublished rows into the batched queryset in the first place."""
        with tenant_context(self.school):
            unpublished = self._make_content("Unpublished", specific_students=[self.student])
            unpublished.is_published = False
            unpublished.save(update_fields=["is_published"])

            self.assertTrue(can_student_access_content(self.student, unpublished))

            published_qs = CourseContent.objects.filter(is_published=True)
            accessible = filter_content_accessible_to_student(self.student, published_qs)
            self.assertNotIn(unpublished.id, accessible)


class FilterContentAccessibleQueryCountTests(CourseContentAccessFixtureMixin, TransactionTestCase):
    """
    Proves the confirmed Phase 9A N+1 is fixed: query count no longer
    scales linearly with the number of content items.
    """

    def test_query_count_does_not_scale_with_content_count(self):
        with tenant_context(self.school):
            for i in range(10):
                self._make_content(f"Item {i}", target_sections=[self.section_a])

            with CaptureQueriesContext(connection) as small_batch:
                filter_content_accessible_to_student(self.student, CourseContent.objects.all())

            for i in range(10, 40):
                self._make_content(f"Item {i}", target_sections=[self.section_a])

            with CaptureQueriesContext(connection) as large_batch:
                filter_content_accessible_to_student(self.student, CourseContent.objects.all())

        # 10 items vs 40 items (4x the content) must NOT produce anywhere
        # close to 4x the queries. The original per-item implementation
        # issued roughly 5-7 queries PER content item; the batched
        # implementation issues a small, fixed number of queries
        # (one per prefetched relation, plus the two student-level lookups)
        # regardless of how many content items are being checked.
        self.assertLess(len(large_batch.captured_queries), len(small_batch.captured_queries) + 3)
        self.assertLess(len(large_batch.captured_queries), 25)


class BulkEnrollAcademicYearTests(TransactionTestCase):
    """
    Phase 1.1: bulk-enroll only accepts an academic year that already exists for
    the tenant, writes nothing when it is rejected, and never sees another
    tenant's years.
    """

    SCHEMA_NAME = "p11_bulk_school"
    OTHER_SCHEMA = "p11_bulk_other"
    DOMAIN = "p11bulk.localhost"
    OTHER_DOMAIN = "p11bulk-other.localhost"
    PASSWORD = "Pass1234!"

    def _cleanup(self):
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            for schema in (self.SCHEMA_NAME, self.OTHER_SCHEMA):
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        Organization.objects.filter(schema_name__in=[self.SCHEMA_NAME, self.OTHER_SCHEMA]).delete()
        User.objects.filter(username="p11_enroller").delete()

    def setUp(self):
        from academics.models import AcademicLevel, Program, Subject
        from profiles.models import Profile
        from roles.models import Permission, Role, UserRole
        from students.models import Student, StudentLevel

        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school = Organization.objects.create(schema_name=self.SCHEMA_NAME, name="P11 Bulk School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.other = Organization.objects.create(schema_name=self.OTHER_SCHEMA, name="P11 Other")
        Domain.objects.create(domain=self.OTHER_DOMAIN, tenant=self.other, is_primary=True)

        with tenant_context(self.school):
            program = Program.objects.create(name="P11", code="P11B")
            level = AcademicLevel.objects.create(program=program, name="Class 8", order=8)
            self.subject = Subject.objects.create(level=level, name="Science", code="SCI")
            self.students = []
            for i in range(2):
                s = Student.objects.create(
                    profile=Profile.objects.create(first_name=f"Stu{i}", last_name="P11"),
                    enrollment_id=f"P11-BULK-{i}", status="active",
                )
                StudentLevel.objects.create(
                    student=s, level=level, academic_year="2026-27", is_current=True
                )
                self.students.append(s)
            role = Role.objects.create(name="p11-enroller", slug="p11-enroller", is_system_role=False)
            role.permissions.set(Permission.objects.filter(codename="manage_subject_enrollment"))
            self.user = User.objects.create_user(username="p11_enroller", password=self.PASSWORD)
            UserRole.objects.create(user=self.user, role=role)

        with tenant_context(self.other):
            other_program = Program.objects.create(name="Other", code="OTH")
            other_level = AcademicLevel.objects.create(program=other_program, name="Other 1", order=1)
            other_student = Student.objects.create(
                profile=Profile.objects.create(first_name="Far", last_name="Away"),
                enrollment_id="P11-OTHER-1", status="active",
            )
            StudentLevel.objects.create(
                student=other_student, level=other_level, academic_year="2099-00", is_current=True
            )

    def _client(self):
        from rest_framework.test import APIClient

        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"username": "p11_enroller", "password": self.PASSWORD}, HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        return client

    def _post(self, academic_year, student_ids=None, client=None, host=None):
        client = client or self._client()
        return client.post(
            "/api/course-content/subject-enrollments/bulk_enroll/",
            {
                "subject_id": str(self.subject.id),
                "student_ids": student_ids or [str(s.id) for s in self.students],
                "academic_year": academic_year,
            },
            HTTP_HOST=host or self.DOMAIN,
            format="json",
        )

    def _enrollment_count(self):
        from course_content.models import SubjectEnrollment

        with tenant_context(self.school):
            return SubjectEnrollment.objects.count()

    def test_known_year_is_accepted_and_enrolls_every_student(self):
        resp = self._post("2026-27")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["newly_enrolled"], 2)
        self.assertEqual(self._enrollment_count(), 2)

    def test_unknown_year_is_rejected_with_400(self):
        resp = self._post("2099-00")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unknown academic year", resp.data["error"])

    def test_unknown_year_writes_no_enrollment_rows(self):
        before = self._enrollment_count()
        self._post("2099-00")
        self.assertEqual(self._enrollment_count(), before)

    def test_year_existing_only_in_another_tenant_is_not_valid_here(self):
        resp = self._post("2099-00")
        self.assertEqual(resp.status_code, 400)
        with tenant_context(self.other):
            from course_content.models import SubjectEnrollment

            self.assertEqual(SubjectEnrollment.objects.count(), 0)

    def test_unauthorized_user_cannot_bulk_enroll(self):
        from rest_framework.test import APIClient

        from roles.models import Role, UserRole

        with tenant_context(self.school):
            UserRole.objects.filter(user=self.user).delete()
            UserRole.objects.create(user=self.user, role=Role.objects.get_or_create(
                slug="p11-noperm", defaults={"name": "p11-noperm", "is_system_role": False})[0])
        resp = self._post("2026-27")
        self.assertEqual(resp.status_code, 403)


class ConfidentialFileDownloadTests(TransactionTestCase):
    SCHEMA_NAME = "cc_dl_test_school"
    DOMAIN = "ccdltest.localhost"
    OTHER_SCHEMA = "cc_dl_other_school"
    OTHER_DOMAIN = "ccdlother.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        with connection.cursor() as cursor:
            for schema in (self.SCHEMA_NAME, self.OTHER_SCHEMA):
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        Organization.objects.filter(schema_name__in=[self.SCHEMA_NAME, self.OTHER_SCHEMA]).delete()
        User.objects.filter(username__in=["cc_student_a", "cc_student_b", "cc_teacher", "cc_outsider"]).delete()

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()

        self.school = Organization.objects.create(schema_name=self.SCHEMA_NAME, name="CC Download School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)

        from datetime import timedelta
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.utils import timezone
        from course_content.models import Assignment, AssignmentSubmission, CourseContent
        from rest_framework.test import APIClient
        from roles.models import Permission, Role, UserRole
        from academics.models import AcademicLevel, Program, Section
        from staff.models import StaffMember
        from students.models import Student, StudentLevel

        self.client = APIClient()

        self.user_a = User.objects.create_user(username="cc_student_a", password="Password123!")
        self.user_b = User.objects.create_user(username="cc_student_b", password="Password123!")
        self.user_teacher = User.objects.create_user(username="cc_teacher", password="Password123!")

        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code=f"HS-{uuid_module.uuid4().hex[:4]}")
            level = AcademicLevel.objects.create(program=program, name="Grade 10", order=1)
            section_a = Section.objects.create(level=level, name="A", capacity=40)
            section_b = Section.objects.create(level=level, name="B", capacity=40)

            staff_profile = Profile.objects.create(user_id=self.user_teacher.id, first_name="Cara", last_name="Teach")
            self.staff_member = StaffMember.objects.create(
                profile=staff_profile, employee_id="EMP-CC-1", designation="Teacher"
            )

            profile_a = Profile.objects.create(user_id=self.user_a.id, first_name="Ada", last_name="Lovelace")
            self.student_a = Student.objects.create(profile=profile_a, enrollment_id="ADA-001")
            StudentLevel.objects.create(student=self.student_a, level=level, section=section_a, academic_year="2026", is_current=True)

            profile_b = Profile.objects.create(user_id=self.user_b.id, first_name="Bob", last_name="Jones")
            self.student_b = Student.objects.create(profile=profile_b, enrollment_id="BOB-001")
            StudentLevel.objects.create(student=self.student_b, level=level, section=section_b, academic_year="2026", is_current=True)

            role_student = Role.objects.get_or_create(slug="student", defaults={"name": "Student", "is_system_role": True})[0]
            role_teacher = Role.objects.get_or_create(slug="instructor", defaults={"name": "Instructor", "is_system_role": True})[0]
            perm_grade = Permission.objects.filter(codename="grade_assignment").first()
            if perm_grade:
                role_teacher.permissions.add(perm_grade)
            perm_view_cc = Permission.objects.filter(codename="view_course_content").first()
            if perm_view_cc:
                role_student.permissions.add(perm_view_cc)

            UserRole.objects.create(user=self.user_a, role=role_student)
            UserRole.objects.create(user=self.user_b, role=role_student)
            UserRole.objects.create(user=self.user_teacher, role=role_teacher)

            content = CourseContent.objects.create(
                title="Homework 1", description="d", content_type="assignment", created_by=self.staff_member, is_published=True
            )
            self.assignment = Assignment.objects.create(
                content=content, due_date=timezone.now() + timedelta(days=7), total_points=100, instructions="Instructions"
            )
            dummy_file = SimpleUploadedFile("my_submission.pdf", b"Confidential Student Answers", content_type="application/pdf")
            self.submission_a = AssignmentSubmission.objects.create(
                assignment=self.assignment,
                student=self.student_a,
                submission_file=dummy_file,
                status="submitted",
            )

    def test_student_can_download_own_submission_and_other_student_denied(self):
        # 1. Student A can download their own submission
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get(f"/api/course-content/submissions/{self.submission_a.id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b"".join(resp.streaming_content), b"Confidential Student Answers")

        # 2. Student B cannot download Student A's submission (404/403)
        self.client.force_authenticate(user=self.user_b)
        resp = self.client.get(f"/api/course-content/submissions/{self.submission_a.id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertIn(resp.status_code, (403, 404))

        # 3. Staff with grading permission can download
        self.client.force_authenticate(user=self.user_teacher)
        resp = self.client.get(f"/api/course-content/submissions/{self.submission_a.id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_student_can_download_accessible_course_content_and_denied_when_not_targeted(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from course_content.models import CourseContent

        with tenant_context(self.school):
            dummy_content_file = SimpleUploadedFile("notes.pdf", b"Math Lecture Notes", content_type="application/pdf")
            content = CourseContent.objects.create(
                title="Lecture Notes",
                description="desc",
                content_type="note",
                created_by=self.staff_member,
                is_published=True,
                file=dummy_content_file,
            )
            content.target_sections.set([self.student_a.enrollments.first().section])

        # Student A is in section A, can download
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get(f"/api/course-content/content/{content.id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b"".join(resp.streaming_content), b"Math Lecture Notes")

        # Student B is in section B, not targeted -> 403 or 404
        self.client.force_authenticate(user=self.user_b)
        resp = self.client.get(f"/api/course-content/content/{content.id}/download/", HTTP_HOST=self.DOMAIN)
        self.assertIn(resp.status_code, (403, 404))

    def test_cross_tenant_cannot_download_submission(self):
        connection.set_schema_to_public()
        other_school = Organization.objects.create(schema_name=self.OTHER_SCHEMA, name="Other School")
        Domain.objects.create(domain=self.OTHER_DOMAIN, tenant=other_school, is_primary=True)
        other_user = User.objects.create_user(username="cc_outsider", password="Password123!")
        try:
            self.client.force_authenticate(user=other_user)
            # Against the other tenant's domain the caller is not a member (403 from the explicit
            # membership permission) and the object does not exist in that schema (404).
            resp = self.client.get(
                f"/api/course-content/submissions/{self.submission_a.id}/download/",
                HTTP_HOST=self.OTHER_DOMAIN,
            )
            self.assertIn(resp.status_code, (403, 404))
        finally:
            connection.set_schema_to_public()

    def test_direct_media_submission_access_is_blocked(self):
        # Direct static access to private submissions path returns 403 Forbidden
        resp = self.client.get("/media/submissions/2026/01/secret.pdf", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

        # Public path is not forbidden (returns 404 because file doesn't exist, not 403)
        resp = self.client.get("/media/institution/logos/nonexistent.png", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)
