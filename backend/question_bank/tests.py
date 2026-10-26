"""Question bank (Stages Q1 and Q2): teacher scope, content rules, versions, duplicate detection, the review
workflow, visibility, permissions and tenant isolation.

Creates tenant schemas and uses real threads for the race case, so it needs a disposable PostgreSQL database and
is meant to be run only in an isolated test stage.
"""
import threading
import uuid

from django.db import connection, connections
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, Program, Section, Subject, SubjectAssignment
from accounts.models import User
from core.models import AuditLog
from notifications.models import Notification
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.constants import SYSTEM_PERMISSIONS
from roles.models import Permission, Role, UserRole
from staff.models import Instructor, StaffMember

from .models import Chapter, Question, QuestionReview, QuestionVersion, SubjectReviewer, Topic

PASSWORD = "Pass1234!"
BASE = "/api/question-bank"
WRITER = ["create_questions"]
REVIEWER = ["review_questions"]


def mcq(subject, body="What is 2 + 3?", **kw):
    return {
        "subject": str(subject.id), "question_type": "mcq", "marks": "1", "body": body, "difficulty": "easy",
        "options": [{"text": "4", "is_correct": False}, {"text": "5", "is_correct": True}, {"text": "6", "is_correct": False}],
        **kw,
    }


def written(subject, body="Explain photosynthesis.", **kw):
    return {"subject": str(subject.id), "question_type": "long", "marks": "5", "body": body,
            "answer": "Plants make food from light, water and carbon dioxide.", "marking_scheme": "2 for inputs, 3 for process", **kw}


class QuestionBankFixture(TransactionTestCase):
    SCHEMA_A, DOMAIN_A = "qb_a", "qb-a.localhost"
    SCHEMA_B, DOMAIN_B = "qb_b", "qb-b.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA_A, self.SCHEMA_B]):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="qb_").delete()

    def _school(self, schema, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema, name=schema)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _user(self, name, school, *, role_slug=None, codenames=None, teacher=False):
        """A login in ``school``. With ``teacher`` it also gets a staff and an instructor record."""
        connection.set_schema_to_public()
        user = User.objects.create_user(username=f"qb_{name}", email=f"qb_{name}@qb.test", password=PASSWORD)
        with tenant_context(school):
            profile = Profile.objects.create(user_id=user.id, first_name=name.title(), last_name="User")
            if role_slug:
                role = Role.objects.get(slug=role_slug)
            else:
                slug = f"qb-{uuid.uuid4().hex[:10]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
            staff = StaffMember.objects.update_or_create(profile=profile, defaults={"employee_id": f"E-{name}", "designation": "Teacher"})[0]
            if teacher:
                Instructor.objects.create(staff_member=staff, specialization="General")
        user.staff = staff
        return user

    def _call(self, user, method, path, data=None, host=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return getattr(client, method)(f"{BASE}/{path}", data, format="json", HTTP_HOST=host or self.DOMAIN_A)

    @staticmethod
    def rows(response):
        data = response.data
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def assign(self, user, subject, section=None):
        with tenant_context(self.school):
            # One teacher per section and subject: a second teacher of the subject needs another section.
            SubjectAssignment.objects.update_or_create(
                section=section or self.section_a, subject=subject, defaults={"instructor": user.staff.instructor_record}
            )

    def make_reviewer(self, user, subject):
        with tenant_context(self.school):
            SubjectReviewer.objects.create(subject=subject, staff=user.staff)

    def create(self, user, data):
        resp = self._call(user, "post", "questions/", data)
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data["id"]

    def get(self, qid):
        with tenant_context(self.school):
            return Question.objects.get(pk=qid)

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school = self._school(self.SCHEMA_A, self.DOMAIN_A)
        self.school_b = self._school(self.SCHEMA_B, self.DOMAIN_B)
        with tenant_context(self.school):
            program = Program.objects.create(name="School", code="SCH")
            self.level = AcademicLevel.objects.create(program=program, name="Class 8", order=1)
            self.section_a = Section.objects.create(level=self.level, name="A")
            self.section_b = Section.objects.create(level=self.level, name="B")
            self.maths = Subject.objects.create(level=self.level, name="Mathematics", code="MAT8")
            self.science = Subject.objects.create(level=self.level, name="Science", code="SCI8")
            self.chapter = Chapter.objects.create(subject=self.maths, name="Numbers", order=1)
            self.topic = Topic.objects.create(chapter=self.chapter, name="Addition", order=1)
            self.other_chapter = Chapter.objects.create(subject=self.science, name="Plants", order=1)
        self.owner = self._user("owner", self.school, role_slug="owner")
        self.teacher = self._user("teacher", self.school, codenames=WRITER, teacher=True)
        self.assign(self.teacher, self.maths)
        self.reviewer = self._user("reviewer", self.school, codenames=WRITER + REVIEWER, teacher=True)
        self.make_reviewer(self.reviewer, self.maths)


class AuthoringScopeTests(QuestionBankFixture):
    def test_a_teacher_writes_for_a_subject_they_teach(self):
        qid = self.create(self.teacher, mcq(self.maths, chapter=str(self.chapter.id), topic=str(self.topic.id)))
        question = self.get(qid)
        self.assertEqual((question.status, question.version, question.author_id), ("draft", 1, self.teacher.staff.id))

    def test_a_teacher_cannot_write_for_a_subject_they_do_not_teach(self):
        resp = self._call(self.teacher, "post", "questions/", mcq(self.science))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("subject", resp.data)
        with tenant_context(self.school):
            self.assertEqual(Question.objects.count(), 0)

    def test_a_staff_member_who_is_not_a_teacher_cannot_write(self):
        clerk = self._user("clerk", self.school, codenames=WRITER)
        self.assertEqual(self._call(clerk, "post", "questions/", mcq(self.maths)).status_code, 400)

    def test_the_owner_and_a_manager_write_for_any_subject(self):
        manager = self._user("manager", self.school, codenames=["manage_question_bank"])
        self.create(self.owner, mcq(self.science))
        self.create(manager, written(self.science))

    def test_a_person_with_no_question_permission_is_refused(self):
        plain = self._user("plain", self.school, codenames=[])
        for method, path in (("get", "questions/"), ("post", "questions/"), ("get", "chapters/"), ("get", "my-scope/")):
            self.assertEqual(self._call(plain, method, path, mcq(self.maths) if method == "post" else None).status_code, 403, path)
        self.assertIn(self._call(None, "get", "questions/").status_code, (401, 403))

    def test_status_author_and_version_cannot_be_set_by_the_client(self):
        resp = self._call(self.teacher, "post", "questions/", {**mcq(self.maths), "status": "approved"})
        self.assertEqual(resp.status_code, 400)
        resp = self._call(self.teacher, "post", "questions/", {**mcq(self.maths), "version": 9, "created_by_user_id": str(uuid.uuid4())})
        self.assertEqual(resp.status_code, 400)

    def test_my_scope_lists_what_the_person_may_write_and_review(self):
        scope = self._call(self.reviewer, "get", "my-scope/").data
        self.assertEqual(([s["code"] for s in scope["can_write"]], [s["code"] for s in scope["can_review"]]), ([], ["MAT8"]))
        self.assign(self.reviewer, self.science)
        self.assertEqual([s["code"] for s in self._call(self.reviewer, "get", "my-scope/").data["can_write"]], ["SCI8"])
        self.assertEqual(len(self._call(self.owner, "get", "my-scope/").data["can_write"]), 2)


class ContentRuleTests(QuestionBankFixture):
    def bad(self, data, field):
        resp = self._call(self.teacher, "post", "questions/", data)
        self.assertEqual(resp.status_code, 400, data)
        self.assertIn(field, resp.data, resp.data)

    def test_choice_questions_need_sound_options(self):
        one = [{"text": "Only", "is_correct": True}]
        two_right = [{"text": "A", "is_correct": True}, {"text": "B", "is_correct": True}]
        none_right = [{"text": "A", "is_correct": False}, {"text": "B", "is_correct": False}]
        same = [{"text": "A", "is_correct": True}, {"text": " a ", "is_correct": False}]
        for options in (one, two_right, none_right, same, [{"text": "", "is_correct": True}, {"text": "B", "is_correct": False}],
                        [{"text": "A"}, {"text": "B", "is_correct": True}]):
            self.bad({**mcq(self.maths), "options": options}, "options")
        self.bad({**mcq(self.maths), "question_type": "multi_select", "options": none_right}, "options")
        self.create(self.teacher, {**mcq(self.maths, body="Pick the even numbers."), "question_type": "multi_select", "options": two_right})

    def test_true_false_has_exactly_true_and_false(self):
        tf = {"subject": str(self.maths.id), "question_type": "true_false", "marks": "1", "body": "Zero is even."}
        self.bad({**tf, "options": [{"text": "Yes", "is_correct": True}, {"text": "No", "is_correct": False}]}, "options")
        self.bad({**tf, "options": [{"text": "True", "is_correct": True}, {"text": "False", "is_correct": True}]}, "options")
        self.create(self.teacher, {**tf, "options": [{"text": "True", "is_correct": True}, {"text": "False", "is_correct": False}]})

    def test_written_answers_need_an_expected_answer_and_no_options(self):
        self.bad({**written(self.maths), "answer": ""}, "answer")
        self.bad({**written(self.maths), "options": [{"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}]}, "options")

    def test_marks_body_and_curriculum_links_are_checked(self):
        self.bad({**mcq(self.maths), "marks": "0"}, "marks")
        self.bad({**mcq(self.maths), "marks": "1.3"}, "marks")
        self.bad({**mcq(self.maths), "body": "   "}, "body")
        self.bad({**mcq(self.maths), "chapter": str(self.other_chapter.id)}, "chapter")
        self.bad({**mcq(self.maths), "topic": str(self.topic.id)}, "topic")  # a topic without its chapter

    def test_the_same_question_twice_in_a_subject_is_refused(self):
        self.create(self.teacher, mcq(self.maths, body="What is 2 + 3?"))
        self.bad(mcq(self.maths, body="  what IS 2 +   3?  "), "body")
        # The same words in another subject are a different question.
        self.create(self.owner, mcq(self.science, body="What is 2 + 3?"))


class EditAndVersionTests(QuestionBankFixture):
    def test_each_content_change_is_a_new_version_and_the_history_is_kept(self):
        qid = self.create(self.teacher, written(self.maths))
        self.assertEqual(self._call(self.teacher, "patch", f"questions/{qid}/", {"marks": "6"}).data["version"], 2)
        same = self._call(self.teacher, "patch", f"questions/{qid}/", {"marks": "6"})
        self.assertEqual(same.data["version"], 2, "saving without a change makes no new version")
        history = self._call(self.teacher, "get", f"questions/{qid}/history/").data
        self.assertEqual([(v["number"], v["content"]["marks"]) for v in history["versions"]], [(2, "6.00"), (1, "5.00")])

    def test_only_the_author_or_a_manager_edits(self):
        qid = self.create(self.teacher, written(self.maths))
        colleague = self._user("colleague", self.school, codenames=WRITER, teacher=True)
        self.assertIn(self._call(colleague, "patch", f"questions/{qid}/", {"marks": "2"}).status_code, (400, 404))
        self.assertEqual(self._call(self.owner, "patch", f"questions/{qid}/", {"marks": "2"}).status_code, 200)

    def test_a_question_cannot_move_subject(self):
        qid = self.create(self.owner, written(self.maths))
        self.assertEqual(self._call(self.owner, "patch", f"questions/{qid}/", {"subject": str(self.science.id)}).status_code, 400)

    def test_submitted_and_approved_questions_cannot_be_edited(self):
        qid = self.create(self.teacher, written(self.maths))
        self._call(self.teacher, "post", f"questions/{qid}/submit/")
        self.assertEqual(self._call(self.teacher, "patch", f"questions/{qid}/", {"marks": "2"}).status_code, 400)
        self._call(self.reviewer, "post", f"questions/{qid}/review/", {"decision": "approved"})
        self.assertEqual(self._call(self.teacher, "patch", f"questions/{qid}/", {"marks": "2"}).status_code, 400)
        self.assertEqual(self.get(qid).marks, 5)

    def test_only_a_never_submitted_draft_can_be_deleted(self):
        keep = self.create(self.teacher, written(self.maths))
        gone = self.create(self.teacher, written(self.maths, body="Define a prime number."))
        self.assertEqual(self._call(self.teacher, "delete", f"questions/{gone}/").status_code, 204)
        self._call(self.teacher, "post", f"questions/{keep}/submit/")
        self._call(self.reviewer, "post", f"questions/{keep}/review/", {"decision": "changes_requested", "comment": "Add units"})
        self.assertEqual(self._call(self.teacher, "delete", f"questions/{keep}/").status_code, 400)


class ReviewWorkflowTests(QuestionBankFixture):
    def submitted(self, data=None):
        qid = self.create(self.teacher, data or written(self.maths))
        self.assertEqual(self._call(self.teacher, "post", f"questions/{qid}/submit/").data["status"], "submitted")
        return qid

    def test_a_reviewer_approves_and_the_author_is_told(self):
        qid = self.submitted()
        resp = self._call(self.reviewer, "post", f"questions/{qid}/review/", {"decision": "approved"})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["status"], "approved")
        with tenant_context(self.school):
            review = QuestionReview.objects.get()
            self.assertEqual((review.decision, review.version, review.reviewer_user_id), ("approved", 1, self.reviewer.id))
            self.assertTrue(Notification.objects.filter(recipient_user_id=self.teacher.id, category="question_bank").exists())
            self.assertTrue(AuditLog.objects.filter(action="question_approved").exists())

    def test_changes_requested_then_corrected_then_approved(self):
        qid = self.submitted()
        back = self._call(self.reviewer, "post", f"questions/{qid}/review/", {"decision": "changes_requested", "comment": "Give the formula"})
        self.assertEqual(back.data["status"], "changes_requested")
        self.assertEqual(self._call(self.teacher, "patch", f"questions/{qid}/", {"answer": "6CO2 + 6H2O -> C6H12O6 + 6O2"}).data["version"], 2)
        self.assertEqual(self._call(self.teacher, "post", f"questions/{qid}/submit/").data["status"], "submitted")
        self.assertEqual(self._call(self.reviewer, "post", f"questions/{qid}/review/", {"decision": "approved"}).data["status"], "approved")
        history = self._call(self.teacher, "get", f"questions/{qid}/history/").data["reviews"]
        self.assertEqual([(r["decision"], r["version"]) for r in history], [("approved", 2), ("changes_requested", 1)])

    def test_rejecting_or_sending_back_needs_a_comment(self):
        qid = self.submitted()
        for decision in ("rejected", "changes_requested"):
            self.assertEqual(self._call(self.reviewer, "post", f"questions/{qid}/review/", {"decision": decision}).status_code, 400)
        self.assertEqual(self._call(self.reviewer, "post", f"questions/{qid}/review/", {"decision": "rejected", "comment": "Off syllabus"}).data["status"], "rejected")

    def test_nobody_reviews_their_own_question(self):
        qid = self.create(self.owner, written(self.maths))
        self._call(self.owner, "post", f"questions/{qid}/submit/")
        self.assertEqual(self._call(self.owner, "post", f"questions/{qid}/review/", {"decision": "approved"}).status_code, 400)
        self.assign(self.reviewer, self.maths, section=self.section_b)
        own = self.create(self.reviewer, written(self.maths, body="State Pythagoras' theorem."))
        self._call(self.reviewer, "post", f"questions/{own}/submit/")
        self.assertEqual(self._call(self.reviewer, "post", f"questions/{own}/review/", {"decision": "approved"}).status_code, 400)

    def test_a_reviewer_of_another_subject_cannot_decide(self):
        qid = self.submitted()
        science_reviewer = self._user("sci_reviewer", self.school, codenames=REVIEWER, teacher=True)
        self.make_reviewer(science_reviewer, self.science)
        self.assertIn(self._call(science_reviewer, "post", f"questions/{qid}/review/", {"decision": "approved"}).status_code, (400, 404))
        self.assertEqual(self.get(qid).status, "submitted")

    def test_being_named_reviewer_is_not_enough_without_the_permission(self):
        qid = self.submitted()
        named = self._user("named", self.school, codenames=[], teacher=True)
        self.make_reviewer(named, self.maths)
        self.assertEqual(self._call(named, "post", f"questions/{qid}/review/", {"decision": "approved"}).status_code, 403)

    def test_only_a_submitted_question_can_be_reviewed(self):
        qid = self.create(self.teacher, written(self.maths))
        self.assertIn(self._call(self.reviewer, "post", f"questions/{qid}/review/", {"decision": "approved"}).status_code, (400, 404))

    def test_the_review_queue_shows_only_my_subjects_and_not_my_own(self):
        mine = self.submitted()
        science_q = self.create(self.owner, written(self.science))
        self._call(self.owner, "post", f"questions/{science_q}/submit/")
        queue = [r["id"] for r in self.rows(self._call(self.reviewer, "get", "questions/?to_review=true"))]
        self.assertEqual(queue, [mine])

    def test_archiving(self):
        qid = self.submitted()
        self.assertEqual(self._call(self.teacher, "post", f"questions/{qid}/archive/").status_code, 400, "decide a submitted one first")
        self._call(self.reviewer, "post", f"questions/{qid}/review/", {"decision": "approved"})
        self.assertEqual(self._call(self.reviewer, "post", f"questions/{qid}/archive/").data["status"], "archived")
        self.assertEqual(self._call(self.reviewer, "post", f"questions/{qid}/archive/").status_code, 400)
        # An archived question no longer blocks writing the same question again.
        self.create(self.teacher, written(self.maths))

    def test_two_reviewers_deciding_at_once_record_one_decision(self):
        qid = self.submitted()
        second = self._user("reviewer2", self.school, codenames=REVIEWER, teacher=True)
        self.make_reviewer(second, self.maths)
        codes = []

        def decide(user, decision, comment=""):
            try:
                codes.append(self._call(user, "post", f"questions/{qid}/review/", {"decision": decision, "comment": comment}).status_code)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=decide, args=(self.reviewer, "approved")),
                   threading.Thread(target=decide, args=(second, "rejected", "Duplicate of another"))]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(codes), [200, 400])
        with tenant_context(self.school):
            self.assertEqual(QuestionReview.objects.filter(question_id=qid).count(), 1)


class VisibilityTests(QuestionBankFixture):
    def setUp(self):
        super().setUp()
        self.colleague = self._user("colleague", self.school, codenames=WRITER, teacher=True)
        self.assign(self.colleague, self.maths, section=self.section_b)
        self.draft = self.create(self.teacher, written(self.maths, body="Draft question"))
        self.approved = self.create(self.teacher, written(self.maths, body="Approved question"))
        self._call(self.teacher, "post", f"questions/{self.approved}/submit/")
        self._call(self.reviewer, "post", f"questions/{self.approved}/review/", {"decision": "approved"})

    def ids(self, user, query=""):
        return {r["id"] for r in self.rows(self._call(user, "get", f"questions/{query}"))}

    def test_a_colleague_sees_approved_questions_of_their_subject_but_not_my_draft(self):
        self.assertEqual(self.ids(self.colleague), {self.approved})
        self.assertEqual(self._call(self.colleague, "get", f"questions/{self.draft}/").status_code, 404)

    def test_a_reviewer_never_sees_an_unsubmitted_draft(self):
        self.assertNotIn(self.draft, self.ids(self.reviewer))

    def test_a_teacher_of_another_subject_sees_nothing_here(self):
        other = self._user("other", self.school, codenames=WRITER, teacher=True)
        self.assign(other, self.science)
        self.assertEqual(self.ids(other), set())

    def test_view_question_bank_reads_approved_questions_of_every_subject(self):
        reader = self._user("reader", self.school, codenames=["view_question_bank"])
        self.assertEqual(self.ids(reader), {self.approved})
        self.assertEqual(self._call(reader, "post", "questions/", written(self.maths)).status_code, 400)

    def test_students_and_parents_have_no_access_at_all(self):
        for slug in ("student", "parent"):
            user = self._user(f"x_{slug}", self.school, role_slug=slug)
            self.assertEqual(self._call(user, "get", "questions/").status_code, 403, slug)
            self.assertEqual(self._call(user, "get", f"questions/{self.approved}/").status_code, 403, slug)

    def test_filters_and_search(self):
        mine = self.ids(self.teacher, "?mine=true")
        self.assertEqual(mine, {self.draft, self.approved})
        self.assertEqual(self.ids(self.teacher, "?status=approved"), {self.approved})
        self.assertEqual(self.ids(self.teacher, "?search=Draft"), {self.draft})


class SetupAndTenantTests(QuestionBankFixture):
    def test_only_a_manager_sets_up_chapters_topics_and_reviewers(self):
        payload = {"subject": str(self.maths.id), "name": "Algebra", "order": 2}
        self.assertEqual(self._call(self.teacher, "post", "chapters/", payload).status_code, 403)
        resp = self._call(self.owner, "post", "chapters/", payload)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self._call(self.owner, "post", "chapters/", payload).status_code, 400, "names are unique per subject")
        topic = self._call(self.owner, "post", "topics/", {"chapter": resp.data["id"], "name": "Linear equations"})
        self.assertEqual(topic.status_code, 201)
        self.assertEqual(self._call(self.teacher, "get", f"chapters/?subject={self.maths.id}").status_code, 200)
        listed = self._call(self.teacher, "get", f"chapters/?subject={self.maths.id}").data
        self.assertEqual([c["name"] for c in listed], ["Numbers", "Algebra"])

    def test_a_chapter_used_by_a_question_cannot_be_deleted(self):
        self.create(self.teacher, mcq(self.maths, chapter=str(self.chapter.id)))
        self.assertEqual(self._call(self.owner, "delete", f"chapters/{self.chapter.id}/").status_code, 409)

    def test_naming_a_reviewer(self):
        staff = self._user("new_reviewer", self.school, codenames=REVIEWER, teacher=True).staff
        resp = self._call(self.owner, "post", "reviewers/", {"subject": str(self.science.id), "staff": str(staff.id)})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self._call(self.owner, "post", "reviewers/", {"subject": str(self.science.id), "staff": str(staff.id)}).status_code, 400)
        with tenant_context(self.school):
            gone = StaffMember.objects.create(profile=Profile.objects.create(first_name="Left", last_name="X"), employee_id="E-left", is_active=False)
        self.assertEqual(self._call(self.owner, "post", "reviewers/", {"subject": str(self.science.id), "staff": str(gone.id)}).status_code, 400)

    def test_the_four_permissions_exist(self):
        codes = {p["codename"] for p in SYSTEM_PERMISSIONS}
        self.assertTrue({"view_question_bank", "create_questions", "review_questions", "manage_question_bank"} <= codes)

    def test_another_school_never_sees_or_reuses_these_questions(self):
        qid = self.create(self.teacher, written(self.maths))
        owner_b = self._user("owner_b", self.school_b, role_slug="owner")
        self.assertEqual(self.rows(self._call(owner_b, "get", "questions/", host=self.DOMAIN_B)), [])
        self.assertEqual(self._call(owner_b, "get", f"questions/{qid}/", host=self.DOMAIN_B).status_code, 404)
        self.assertEqual(self._call(owner_b, "get", "questions/").status_code, 403, "a user of school B has no standing in school A")
        with tenant_context(self.school_b):
            self.assertEqual(Question.objects.count(), 0)
            self.assertEqual(QuestionVersion.objects.count(), 0)
