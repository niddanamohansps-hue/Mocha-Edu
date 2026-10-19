"""Authorization and integrity tests for assignment submissions and subject enrollments.

Two tiers, on purpose:
- ``force_authenticate`` skips the cookie authentication class, so it exercises the *explicit*
  permission classes and the object/queryset scoping (a non-member is authenticated but forbidden: 403);
- a real ``access_token`` cookie runs the membership gate (a non-member is anonymous: 401).

These tests create tenant schemas and therefore need a disposable PostgreSQL database. They are
written to be run only in an explicitly authorized isolated test stage.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from academics.models import AcademicLevel, Program, Section, Subject
from accounts.models import User
from course_content.models import Assignment, AssignmentSubmission, CourseContent, SubjectEnrollment
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from staff.models import StaffMember
from students.models import Student, StudentLevel

PASSWORD = "Pass1234!"
SUBMISSIONS = "/api/course-content/submissions/"
ENROLLMENTS = "/api/course-content/subject-enrollments/"


class CourseContentAuthorizationFixture(TransactionTestCase):
    SCHEMA = "cc_authz_school"
    DOMAIN = "ccauthz.localhost"

    # ------------------------------------------------------------------ helpers
    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name=self.SCHEMA):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="ccaz_").delete()

    def _user(self, username, superuser=False):
        connection.set_schema_to_public()
        if superuser:
            return User.objects.create_superuser(
                username=username, email=f"{username}@ccaz.test", password=PASSWORD
            )
        return User.objects.create_user(
            username=username, email=f"{username}@ccaz.test", password=PASSWORD
        )

    def _role(self, user, codenames=(), slug=None):
        with tenant_context(self.school):
            slug = slug or f"ccaz-{uuid.uuid4().hex[:10]}"
            role, _ = Role.objects.get_or_create(
                slug=slug, defaults={"name": slug, "is_system_role": slug == "owner"}
            )
            if codenames:
                role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.create(user=user, role=role)

    def _as(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _cookie(self, user):
        connection.set_schema_to_public()
        client = APIClient()
        client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        return client

    def _get(self, client, path, **extra):
        return client.get(path, HTTP_HOST=self.DOMAIN, **extra)

    def _reload(self, submission):
        with tenant_context(self.school):
            return AssignmentSubmission.objects.get(pk=submission.pk)

    @staticmethod
    def _ids(response):
        data = response.data["results"] if isinstance(response.data, dict) and "results" in response.data else response.data
        return {str(item["id"]) for item in data}

    # ------------------------------------------------------------------ fixture
    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="CC Authz School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)

        self.student_a_user = self._user("ccaz_student_a")
        self.student_b_user = self._user("ccaz_student_b")
        self.grader_user = self._user("ccaz_grader")
        self.manager_user = self._user("ccaz_manager")
        self.parent_user = self._user("ccaz_parent")
        self.plain_staff_user = self._user("ccaz_plain_staff")
        self.owner_user = self._user("ccaz_owner")
        self.superuser = self._user("ccaz_superuser", superuser=True)
        self.outsider = self._user("ccaz_outsider")  # a global user with no membership in this tenant

        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code=f"HS-{uuid.uuid4().hex[:4]}")
            level = AcademicLevel.objects.create(program=program, name="Grade 10", order=1)
            section = Section.objects.create(level=level, name="A", capacity=40)
            self.subject = Subject.objects.create(level=level, name="Mathematics", code="MTH101")

            def student(user, enrollment_id, first):
                profile = Profile.objects.create(user_id=user.id, first_name=first, last_name="Student")
                record = Student.objects.create(profile=profile, enrollment_id=enrollment_id)
                StudentLevel.objects.create(
                    student=record, level=level, section=section, academic_year="2026", is_current=True
                )
                return record

            self.student_a = student(self.student_a_user, "AZ-A", "Ada")
            self.student_b = student(self.student_b_user, "AZ-B", "Bob")

            grader_profile = Profile.objects.create(user_id=self.grader_user.id, first_name="Gina", last_name="Grader")
            self.grader_staff = StaffMember.objects.create(
                profile=grader_profile, employee_id="EMP-AZ-1", designation="Teacher"
            )

            parent_profile = Profile.objects.create(user_id=self.parent_user.id, first_name="Pat", last_name="Parent")
            self.parent = Parent.objects.create(profile=parent_profile)
            StudentParentRelation.objects.create(
                student=self.student_a, parent=self.parent, relation_type="guardian"
            )

        # Roles. Students may submit; the grader may grade; the manager manages enrollments.
        self._role(self.student_a_user, ["submit_assignment"])
        self._role(self.student_b_user, ["submit_assignment"])
        self._role(self.grader_user, ["grade_assignment"])
        self._role(self.manager_user, ["manage_subject_enrollment"])
        self._role(self.parent_user)  # a member with no course-content permission at all
        self._role(self.plain_staff_user)  # ordinary member, no relevant permission
        self._role(self.owner_user, slug="owner")

        with tenant_context(self.school):
            owner_profile = Profile.objects.get(user_id=self.owner_user.id)
            StaffMember.objects.get_or_create(
                profile=owner_profile, defaults={"employee_id": "EMP-AZ-OWN", "designation": "Owner"}
            )

            def assignment(title):
                content = CourseContent.objects.create(
                    title=title, description="d", content_type="assignment",
                    created_by=self.grader_staff, is_published=True,
                )
                return Assignment.objects.create(
                    content=content, due_date=timezone.now() + timedelta(days=7),
                    total_points=Decimal("100"), instructions="Do it",
                )

            self.assignment_1, self.assignment_2, self.assignment_3 = (
                assignment("HW1"), assignment("HW2"), assignment("HW3"),
            )
            self.sub_a = AssignmentSubmission.objects.create(
                assignment=self.assignment_1, student=self.student_a, status="submitted",
                submitted_at=timezone.now(), submission_text="first answer",
                submission_file=SimpleUploadedFile("answer.pdf", b"Ada confidential answers", content_type="application/pdf"),
            )
            self.sub_b = AssignmentSubmission.objects.create(
                assignment=self.assignment_1, student=self.student_b, status="submitted",
                submitted_at=timezone.now(), submission_text="bob answer",
            )
            self.sub_pending_a = AssignmentSubmission.objects.create(
                assignment=self.assignment_2, student=self.student_a, status="pending",
            )
            self.sub_graded_a = AssignmentSubmission.objects.create(
                assignment=self.assignment_3, student=self.student_a, status="graded",
                submitted_at=timezone.now(), submission_text="final", score=Decimal("80"),
                feedback="ok", graded_by=self.grader_staff, graded_at=timezone.now(),
            )
            self.enrollment_a = SubjectEnrollment.objects.create(
                student=self.student_a, subject=self.subject, academic_year="2026"
            )
            self.enrollment_b = SubjectEnrollment.objects.create(
                student=self.student_b, subject=self.subject, academic_year="2026"
            )


class SubmissionReadScopeTests(CourseContentAuthorizationFixture):
    def test_read_scope_and_unsupported_methods(self):
        all_ids = {str(s.id) for s in (self.sub_a, self.sub_b, self.sub_pending_a, self.sub_graded_a)}
        own_a = {str(s.id) for s in (self.sub_a, self.sub_pending_a, self.sub_graded_a)}

        # Student: only their own rows; another student's row does not exist for them.
        resp = self._get(self._as(self.student_a_user), SUBMISSIONS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._ids(resp), own_a)
        self.assertEqual(self._get(self._as(self.student_a_user), f"{SUBMISSIONS}{self.sub_b.id}/").status_code, 404)
        resp = self._get(self._as(self.student_b_user), SUBMISSIONS)
        self.assertEqual(self._ids(resp), {str(self.sub_b.id)})

        # Graders, owner and superuser see everything.
        for user in (self.grader_user, self.owner_user, self.superuser):
            resp = self._get(self._as(user), SUBMISSIONS)
            self.assertEqual(resp.status_code, 200, user.username)
            self.assertEqual(self._ids(resp), all_ids, user.username)
        self.assertEqual(self._get(self._as(self.grader_user), f"{SUBMISSIONS}{self.sub_b.id}/").status_code, 200)

        # Parents, ordinary staff and non-members get no submission list at all.
        for user in (self.parent_user, self.plain_staff_user, self.outsider):
            self.assertEqual(self._get(self._as(user), SUBMISSIONS).status_code, 403, user.username)
            self.assertEqual(self._get(self._as(user), f"{SUBMISSIONS}{self.sub_a.id}/").status_code, 403, user.username)

        # No create / replace / edit / delete route exists for anyone who is a member.
        detail = f"{SUBMISSIONS}{self.sub_a.id}/"
        for user in (self.student_a_user, self.grader_user, self.owner_user, self.superuser):
            client = self._as(user)
            payload = {"score": "100", "status": "graded", "feedback": "x"}
            self.assertEqual(client.post(SUBMISSIONS, payload, HTTP_HOST=self.DOMAIN).status_code, 405, user.username)
            self.assertEqual(client.put(detail, payload, HTTP_HOST=self.DOMAIN).status_code, 405, user.username)
            self.assertEqual(client.patch(detail, payload, HTTP_HOST=self.DOMAIN).status_code, 405, user.username)
            self.assertEqual(client.delete(detail, HTTP_HOST=self.DOMAIN).status_code, 405, user.username)
        stored = self._reload(self.sub_a)
        self.assertIsNone(stored.score)
        self.assertEqual(stored.status, "submitted")


class SubmissionSubmitTests(CourseContentAuthorizationFixture):
    def test_submit_changes_only_submission_fields(self):
        client = self._as(self.student_a_user)
        resp = client.post(
            f"{SUBMISSIONS}{self.sub_a.id}/submit/",
            {
                "submission_text": "revised answer",
                # Everything below must be ignored, never written:
                "score": "100", "status": "graded", "feedback": "I deserve full marks",
                "graded_by": "1", "graded_at": timezone.now().isoformat(),
            },
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        stored = self._reload(self.sub_a)
        self.assertEqual(stored.submission_text, "revised answer")
        self.assertEqual(stored.status, "submitted")
        self.assertIsNone(stored.score)
        self.assertEqual(stored.feedback, "")
        self.assertIsNone(stored.graded_by_id)
        self.assertIsNone(stored.graded_at)

    def test_submit_rules(self):
        client = self._as(self.student_a_user)

        # Pending work can be submitted.
        resp = client.post(f"{SUBMISSIONS}{self.sub_pending_a.id}/submit/", {"submission_text": "done"}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._reload(self.sub_pending_a).status, "submitted")

        # Graded work is final: 409, and nothing changes.
        resp = client.post(f"{SUBMISSIONS}{self.sub_graded_a.id}/submit/", {"submission_text": "tamper"}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 409)
        graded = self._reload(self.sub_graded_a)
        self.assertEqual((graded.status, graded.score, graded.feedback, graded.submission_text), ("graded", Decimal("80"), "ok", "final"))

        # At least one submission field is required.
        resp = client.post(f"{SUBMISSIONS}{self.sub_a.id}/submit/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._reload(self.sub_a).submission_text, "first answer")

        # The 10MB limit is enforced on this real upload path.
        too_big = SimpleUploadedFile("big.pdf", b"x" * (10 * 1024 * 1024 + 1), content_type="application/pdf")
        resp = client.post(f"{SUBMISSIONS}{self.sub_a.id}/submit/", {"submission_file": too_big}, format="multipart", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._reload(self.sub_a).submission_text, "first answer")

        # Another student's submission does not exist for this caller.
        resp = self._as(self.student_b_user).post(f"{SUBMISSIONS}{self.sub_a.id}/submit/", {"submission_text": "x"}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)

        # Only the owning student with submit_assignment may submit.
        for user in (self.grader_user, self.parent_user, self.plain_staff_user, self.owner_user, self.outsider):
            resp = self._as(user).post(f"{SUBMISSIONS}{self.sub_a.id}/submit/", {"submission_text": "x"}, HTTP_HOST=self.DOMAIN)
            self.assertEqual(resp.status_code, 403, user.username)
        self.assertEqual(self._reload(self.sub_a).submission_text, "first answer")


class SubmissionGradeTests(CourseContentAuthorizationFixture):
    def _grade(self, user, submission, payload):
        return self._as(user).post(f"{SUBMISSIONS}{submission.id}/grade/", payload, HTTP_HOST=self.DOMAIN)

    def test_grading_rules(self):
        # A grader grades submitted work; grader metadata is set from the caller, never the request.
        resp = self._grade(self.grader_user, self.sub_a, {"score": "85.50", "feedback": "Good", "graded_by": "999"})
        self.assertEqual(resp.status_code, 200, resp.data)
        graded = self._reload(self.sub_a)
        self.assertEqual((graded.status, graded.score, graded.feedback), ("graded", Decimal("85.50"), "Good"))
        self.assertEqual(graded.graded_by_id, self.grader_staff.pk)
        self.assertIsNotNone(graded.graded_at)

        # Boundaries: 0 and total_points are valid; outside the range or non-numeric is not.
        self.assertEqual(self._grade(self.grader_user, self.sub_b, {"score": "0"}).status_code, 200)
        self.assertEqual(self._grade(self.grader_user, self.sub_b, {"score": "100"}).status_code, 200)
        for bad in ("100.01", "-1", "abc", ""):
            resp = self._grade(self.grader_user, self.sub_b, {"score": bad})
            self.assertEqual(resp.status_code, 400, f"score={bad!r}")
        self.assertEqual(self._grade(self.grader_user, self.sub_b, {}).status_code, 400)
        self.assertEqual(self._reload(self.sub_b).score, Decimal("100"))  # the last valid grade stands

        # Unsubmitted work cannot be graded.
        resp = self._grade(self.grader_user, self.sub_pending_a, {"score": "50"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._reload(self.sub_pending_a).status, "pending")

        # Already graded work may be re-graded by a grader.
        self.assertEqual(self._grade(self.grader_user, self.sub_graded_a, {"score": "90"}).status_code, 200)

        # Students, parents, ordinary staff and non-members cannot grade.
        for user in (self.student_a_user, self.parent_user, self.plain_staff_user, self.outsider):
            self.assertEqual(self._grade(user, self.sub_a, {"score": "1"}).status_code, 403, user.username)

        # The owner can grade (permission bypass + staff record); a superuser without a staff record cannot.
        self.assertEqual(self._grade(self.owner_user, self.sub_a, {"score": "70"}).status_code, 200)
        self.assertEqual(self._grade(self.superuser, self.sub_a, {"score": "70"}).status_code, 403)


class SubmissionDownloadTests(CourseContentAuthorizationFixture):
    def _download(self, user):
        resp = self._get(self._as(user), f"{SUBMISSIONS}{self.sub_a.id}/download/")
        if getattr(resp, "streaming", False):
            body = b"".join(resp.streaming_content)
            return resp.status_code, body
        return resp.status_code, None

    def test_download_access_rules(self):
        for user in (self.student_a_user, self.grader_user, self.owner_user, self.superuser, self.parent_user):
            status_code, body = self._download(user)
            self.assertEqual(status_code, 200, user.username)
            self.assertEqual(body, b"Ada confidential answers", user.username)

        status_code, _ = self._download(self.student_b_user)
        self.assertIn(status_code, (403, 404))  # not their submission
        for user in (self.plain_staff_user, self.outsider):
            status_code, _ = self._download(user)
            self.assertEqual(status_code, 403, user.username)

        # A parent is linked to student A only, never to student B.
        with tenant_context(self.school):
            AssignmentSubmission.objects.filter(pk=self.sub_b.pk).update(
                submission_file="submissions/2026/01/b.pdf"
            )
        resp = self._get(self._as(self.parent_user), f"{SUBMISSIONS}{self.sub_b.id}/download/")
        self.assertIn(resp.status_code, (403, 404))


class SubjectEnrollmentAuthorizationTests(CourseContentAuthorizationFixture):
    def test_read_scope_and_mutations(self):
        both = {str(self.enrollment_a.id), str(self.enrollment_b.id)}

        # Student: own rows only.
        resp = self._get(self._as(self.student_a_user), ENROLLMENTS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._ids(resp), {str(self.enrollment_a.id)})
        self.assertEqual(self._get(self._as(self.student_a_user), f"{ENROLLMENTS}{self.enrollment_b.id}/").status_code, 404)
        # Asking for someone else's rows through a filter still yields nothing for a student.
        resp = self._get(self._as(self.student_a_user), ENROLLMENTS, data={"student": str(self.student_b.id)})
        self.assertEqual(self._ids(resp), set())

        # Managers, owner and superuser read all rows.
        for user in (self.manager_user, self.owner_user, self.superuser):
            resp = self._get(self._as(user), ENROLLMENTS)
            self.assertEqual(resp.status_code, 200, user.username)
            self.assertEqual(self._ids(resp), both, user.username)

        # Instructors with only grading rights, parents, ordinary staff and non-members: no access.
        for user in (self.grader_user, self.parent_user, self.plain_staff_user, self.outsider):
            self.assertEqual(self._get(self._as(user), ENROLLMENTS).status_code, 403, user.username)

        # Mutations: students and non-managers are refused.
        new_row = {"student": str(self.student_b.id), "subject": str(self.subject.id), "academic_year": "2025"}
        for user in (self.student_a_user, self.grader_user, self.parent_user, self.outsider):
            resp = self._as(user).post(ENROLLMENTS, new_row, format="json", HTTP_HOST=self.DOMAIN)
            self.assertEqual(resp.status_code, 403, user.username)
            resp = self._as(user).delete(f"{ENROLLMENTS}{self.enrollment_b.id}/", HTTP_HOST=self.DOMAIN)
            self.assertEqual(resp.status_code, 403, user.username)

        # Enrollment rows are immutable: PUT / PATCH do not exist, even for a manager.
        manager = self._as(self.manager_user)
        detail = f"{ENROLLMENTS}{self.enrollment_b.id}/"
        self.assertEqual(manager.put(detail, new_row, format="json", HTTP_HOST=self.DOMAIN).status_code, 405)
        self.assertEqual(manager.patch(detail, {"academic_year": "2025"}, format="json", HTTP_HOST=self.DOMAIN).status_code, 405)

        # A manager can still create and delete.
        resp = manager.post(ENROLLMENTS, new_row, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(manager.delete(f"{ENROLLMENTS}{resp.data['id']}/", HTTP_HOST=self.DOMAIN).status_code, 204)


class CookieGateOnViewsetsTests(CourseContentAuthorizationFixture):
    def test_non_member_cookie_is_unauthenticated_and_members_still_work(self):
        outsider = self._cookie(self.outsider)
        for path in (SUBMISSIONS, f"{SUBMISSIONS}{self.sub_a.id}/", f"{SUBMISSIONS}{self.sub_a.id}/download/", ENROLLMENTS):
            self.assertEqual(self._get(outsider, path).status_code, 401, path)

        self.assertEqual(self._get(self._cookie(self.student_a_user), SUBMISSIONS).status_code, 200)
        self.assertEqual(self._get(self._cookie(self.manager_user), ENROLLMENTS).status_code, 200)
        self.assertEqual(self._get(self._cookie(self.superuser), SUBMISSIONS).status_code, 200)
