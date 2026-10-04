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
        self.school.delete(force_drop=True)


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
