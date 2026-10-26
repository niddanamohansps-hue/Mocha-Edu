"""Question papers (Stages Q3 and Q4): blueprint, assembly, auto-fill, checks, approval by someone else, freezing,
release, withdrawal, access logging and who can open what.

Creates tenant schemas and uses a real thread for the race case, so it needs a disposable PostgreSQL database.
"""
import threading
from datetime import date, time, timedelta
from decimal import Decimal

from django.db import connections
from django.utils import timezone
from django_tenants.utils import tenant_context

from core.models import AuditLog
from examinations.models import Examination, ExamSchedule, ExamType

from .models import Chapter, PaperAccessLog, PaperQuestion, Question, QuestionPaper
from .tests import QuestionBankFixture, mcq, written

D = Decimal
PAPERS = "papers/"


class PaperFixture(QuestionBankFixture):
    def setUp(self):
        super().setUp()
        self.controller = self._user("controller", self.school, codenames=["prepare_papers"])
        self.principal = self._user("principal", self.school, codenames=["approve_papers"])
        with tenant_context(self.school):
            exam_type = ExamType.objects.create(name="Half-Yearly")
            self.exam = Examination.objects.create(
                academic_year="2026-27", name="Half-Yearly 2026", exam_type=exam_type,
                start_date=date(2026, 9, 14), end_date=date(2026, 9, 25),
            )
            self.algebra = Chapter.objects.create(subject=self.maths, name="Algebra", order=2)
        # An approved bank: 6 easy MCQs in Numbers, 4 medium MCQs in Algebra, 3 long answers in Numbers.
        self.mcq_easy = [self.approved(mcq(self.maths, body=f"Easy {i}", chapter=str(self.chapter.id))) for i in range(6)]
        self.mcq_medium = [self.approved({**mcq(self.maths, body=f"Medium {i}", chapter=str(self.algebra.id)), "difficulty": "medium"}) for i in range(4)]
        self.long = [self.approved(written(self.maths, body=f"Long {i}", chapter=str(self.chapter.id))) for i in range(3)]

    def approved(self, data):
        qid = self.create(self.teacher, data)
        self._call(self.teacher, "post", f"questions/{qid}/submit/")
        resp = self._call(self.reviewer, "post", f"questions/{qid}/review/", {"decision": "approved"})
        assert resp.status_code == 200, resp.data
        return qid

    def paper(self, total="10", label="A", user=None, **kw):
        resp = self._call(user or self.controller, "post", PAPERS, {
            "examination": str(self.exam.id), "subject": str(self.maths.id), "set_label": label,
            "title": "Mathematics - Half-Yearly", "total_marks": total, "duration_minutes": 90, **kw,
        })
        assert resp.status_code == 201, resp.data
        return resp.data["id"]

    def detail(self, pid, user=None):
        return self._call(user or self.controller, "get", f"{PAPERS}{pid}/").data

    def section_id(self, pid, index=0):
        return self.detail(pid)["sections"][index]["id"]

    def add(self, pid, qid, section=None, user=None):
        return self._call(user or self.controller, "post", f"{PAPERS}{pid}/questions/", {"section": section or self.section_id(pid), "question": qid})

    def rule(self, section, count, **kw):
        resp = self._call(self.controller, "post", "blueprint-rules/", {"section": section, "count": count, **kw})
        assert resp.status_code == 201, resp.data

    def ready_paper(self):
        """10 marks: five 1-mark easy MCQs and one 5-mark long answer."""
        pid = self.paper(total="10")
        for qid in self.mcq_easy[:5] + self.long[:1]:
            self.assertEqual(self.add(pid, qid).status_code, 200)
        return pid

    def approved_paper(self):
        pid = self.ready_paper()
        self.assertEqual(self._call(self.controller, "post", f"{PAPERS}{pid}/submit/").status_code, 200)
        self.assertEqual(self._call(self.principal, "post", f"{PAPERS}{pid}/approve/").status_code, 200)
        return pid


class CreateTests(PaperFixture):
    def test_a_controller_creates_a_paper_with_a_first_section(self):
        pid = self.paper()
        data = self.detail(pid)
        self.assertEqual((data["status"], data["set_label"], [s["title"] for s in data["sections"]]), ("draft", "A", ["Section A"]))
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="paper_created").exists())

    def test_the_total_must_match_the_exam_schedule(self):
        with tenant_context(self.school):
            ExamSchedule.objects.create(
                examination=self.exam, academic_year="2026-27", subject=self.maths, section=self.section_a,
                date=date(2026, 9, 15), start_time=time(9), end_time=time(11), max_marks=D("80"), pass_marks=D("27"),
            )
        resp = self._call(self.controller, "post", PAPERS, {
            "examination": str(self.exam.id), "subject": str(self.maths.id), "title": "M", "total_marks": "100", "duration_minutes": 120,
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("total_marks", resp.data)
        self.paper(total="80")

    def test_a_set_label_is_used_once_but_a_withdrawn_one_can_be_replaced(self):
        pid = self.approved_paper()
        self.assertEqual(self._call(self.controller, "post", PAPERS, {
            "examination": str(self.exam.id), "subject": str(self.maths.id), "set_label": "a", "title": "M", "total_marks": "10", "duration_minutes": 60,
        }).status_code, 400)
        self._call(self.principal, "post", f"{PAPERS}{pid}/withdraw/", {"reason": "Suspected leak"})
        self.paper(label="A")

    def test_a_published_examination_takes_no_new_paper(self):
        with tenant_context(self.school):
            Examination.objects.filter(pk=self.exam.pk).update(is_published=True)
        resp = self._call(self.controller, "post", PAPERS, {
            "examination": str(self.exam.id), "subject": str(self.maths.id), "title": "M", "total_marks": "10", "duration_minutes": 60,
        })
        self.assertEqual(resp.status_code, 400)


class AssemblyTests(PaperFixture):
    def test_only_approved_questions_of_the_same_subject_can_be_added(self):
        pid = self.paper()
        draft = self.create(self.teacher, mcq(self.maths, body="Still a draft"))
        science = self.create(self.owner, mcq(self.science, body="Science question"))
        self.assertEqual(self.add(pid, draft).status_code, 400)
        self.assertEqual(self.add(pid, science).status_code, 400)
        self.assertEqual(self.add(pid, self.mcq_easy[0]).status_code, 200)
        self.assertEqual(self.add(pid, self.mcq_easy[0]).status_code, 400, "the same question twice")

    def test_sets_do_not_share_questions_unless_allowed(self):
        a = self.paper(label="A")
        b = self.paper(label="B")
        self.add(a, self.mcq_easy[0])
        self.assertEqual(self.add(b, self.mcq_easy[0]).status_code, 400)
        shared = self.paper(label="C", allow_shared_questions=True)
        self.assertEqual(self.add(shared, self.mcq_easy[0]).status_code, 200)

    def test_candidates_list_only_what_may_be_added(self):
        a = self.paper(label="A")
        b = self.paper(label="B")
        self.add(a, self.mcq_easy[0])
        ids = {r["id"] for r in self.rows(self._call(self.controller, "get", f"{PAPERS}{b}/candidates/?difficulty=easy"))}
        self.assertEqual(ids, set(self.mcq_easy[1:]))

    def test_autofill_follows_the_blueprint(self):
        pid = self.paper(total="12")
        section = self.section_id(pid)
        self.rule(section, 4, question_type="mcq", difficulty="easy", chapter=str(self.chapter.id))
        self.rule(section, 3, difficulty="medium")
        resp = self._call(self.controller, "post", f"{PAPERS}{pid}/autofill/", {})
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            items = list(PaperQuestion.objects.filter(paper_id=pid).select_related("question"))
        picked = {str(i.question_id) for i in items}
        self.assertEqual(len(items), 7)
        # The first rule takes 4 easy MCQs from Numbers; the second any 3 medium questions (MCQ or long answer).
        self.assertEqual(len(picked & set(self.mcq_easy)), 4)
        self.assertEqual(sum(1 for i in items if i.question.difficulty == "medium"), 3)
        self.assertTrue(all(i.question.chapter_id == self.chapter.id for i in items if i.question.difficulty == "easy"))

    def test_autofill_changes_nothing_when_the_bank_is_short(self):
        pid = self.paper()
        section = self.section_id(pid)
        self.add(pid, self.long[0])
        self.rule(section, 9, difficulty="hard")
        resp = self._call(self.controller, "post", f"{PAPERS}{pid}/autofill/", {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("blueprint", resp.data)
        with tenant_context(self.school):
            self.assertEqual(PaperQuestion.objects.filter(paper_id=pid).count(), 1, "the earlier question is still there")

    def test_a_blueprint_chapter_must_be_of_the_papers_subject(self):
        pid = self.paper()
        resp = self._call(self.controller, "post", "blueprint-rules/", {"section": self.section_id(pid), "count": 1, "chapter": str(self.other_chapter.id)})
        self.assertEqual(resp.status_code, 400)

    def test_removing_and_sections(self):
        pid = self.paper()
        self.add(pid, self.mcq_easy[0])
        item = self.detail(pid)["sections"][0]["items"][0]["id"]
        self.assertEqual(self._call(self.controller, "delete", f"{PAPERS}{pid}/questions/{item}/").status_code, 200)
        resp = self._call(self.controller, "post", "paper-sections/", {"paper": pid, "order": 2, "title": "Section B"})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self._call(self.controller, "post", "paper-sections/", {"paper": pid, "order": 2, "title": "Again"}).status_code, 400)


class CheckAndApprovalTests(PaperFixture):
    def test_problems_block_submission(self):
        pid = self.paper(total="10")
        resp = self._call(self.controller, "post", f"{PAPERS}{pid}/submit/")
        self.assertEqual(resp.status_code, 400)
        self.add(pid, self.mcq_easy[0])
        problems = self.detail(pid)["problems"]
        self.assertTrue(any("add up to 1" in p for p in problems), problems)

    def test_a_section_must_match_its_blueprint(self):
        pid = self.paper(total="6")
        section = self.section_id(pid)
        self.rule(section, 1, question_type="long")
        self.add(pid, self.mcq_easy[0])  # an MCQ where the blueprint wants a long answer
        problems = self.detail(pid)["problems"]
        self.assertTrue(any("needs 1 more long answer" in p for p in problems), problems)

    def test_submit_approve_and_freeze(self):
        pid = self.ready_paper()
        self.assertEqual(self._call(self.controller, "post", f"{PAPERS}{pid}/submit/").data["status"], "submitted")
        self.assertEqual(self.add(pid, self.mcq_easy[5]).status_code, 400, "no changes after submitting")
        resp = self._call(self.principal, "post", f"{PAPERS}{pid}/approve/")
        self.assertEqual((resp.status_code, resp.data["status"]), (200, "approved"))
        with tenant_context(self.school):
            paper = QuestionPaper.objects.get(pk=pid)
            frozen = paper.frozen_content
            self.assertEqual(sum(len(s["questions"]) for s in frozen["sections"]), 6)
            # Archiving a question afterwards does not change the approved paper.
            Question.objects.filter(pk=self.mcq_easy[0]).update(status="archived", body="Changed afterwards")
            self.assertEqual(QuestionPaper.objects.get(pk=pid).frozen_content, frozen)
        key = self._call(self.principal, "get", f"{PAPERS}{pid}/answer-key/").data
        self.assertEqual(key["sections"][0]["questions"][0]["body"], "Easy 0")

    def test_the_preparer_cannot_approve_their_own_paper(self):
        both = self._user("both", self.school, codenames=["prepare_papers", "approve_papers"])
        pid = self.paper(user=both)
        for qid in self.mcq_easy[:5] + self.long[:1]:
            self.add(pid, qid, user=both)
        self._call(both, "post", f"{PAPERS}{pid}/submit/")
        self.assertEqual(self._call(both, "post", f"{PAPERS}{pid}/approve/").status_code, 400)
        self.assertEqual(self._call(self.owner, "post", f"{PAPERS}{pid}/approve/").status_code, 200)

    def test_sending_back_needs_a_comment_and_reopens_the_draft(self):
        pid = self.ready_paper()
        self._call(self.controller, "post", f"{PAPERS}{pid}/submit/")
        self.assertEqual(self._call(self.principal, "post", f"{PAPERS}{pid}/send-back/", {}).status_code, 400)
        resp = self._call(self.principal, "post", f"{PAPERS}{pid}/send-back/", {"comment": "Too easy"})
        self.assertEqual((resp.data["status"], resp.data["review_comment"]), ("draft", "Too easy"))
        self.assertEqual(self.add(pid, self.mcq_easy[5]).status_code, 200)

    def test_a_controller_cannot_approve_and_an_approver_cannot_edit(self):
        pid = self.ready_paper()
        self._call(self.controller, "post", f"{PAPERS}{pid}/submit/")
        self.assertEqual(self._call(self.controller, "post", f"{PAPERS}{pid}/approve/").status_code, 403)
        self.assertEqual(self._call(self.principal, "patch", f"{PAPERS}{pid}/", {"title": "x"}).status_code, 403)

    def test_two_approvers_at_once_approve_once(self):
        pid = self.ready_paper()
        self._call(self.controller, "post", f"{PAPERS}{pid}/submit/")
        second = self._user("principal2", self.school, codenames=["approve_papers"])
        codes = []

        def approve(user):
            try:
                codes.append(self._call(user, "post", f"{PAPERS}{pid}/approve/").status_code)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=approve, args=(u,)) for u in (self.principal, second)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(codes), [200, 400])


class ReleaseAndAccessTests(PaperFixture):
    def test_a_subject_teacher_sees_the_paper_only_after_release(self):
        pid = self.approved_paper()
        self.assertEqual(self._call(self.teacher_with_exams(), "get", f"{PAPERS}{pid}/printable/").status_code, 404)
        self.assertEqual(self._call(self.principal, "post", f"{PAPERS}{pid}/release/").data["status"], "released")
        paper = self._call(self.teacher_with_exams(), "get", f"{PAPERS}{pid}/printable/")
        self.assertEqual(paper.status_code, 200)
        question = paper.data["sections"][0]["questions"][0]
        self.assertNotIn("answer", question)
        self.assertNotIn("correct", question)
        self.assertEqual(self._call(self.teacher_with_exams(), "get", f"{PAPERS}{pid}/answer-key/").status_code, 200)

    def teacher_with_exams(self):
        if not hasattr(self, "_marker"):
            self._marker = self._user("marker", self.school, codenames=["view_examinations"], teacher=True)
            self.assign(self._marker, self.maths, section=self.section_b)
        return self._marker

    def test_a_scheduled_release_opens_at_its_time(self):
        pid = self.approved_paper()
        soon = timezone.now() + timedelta(hours=2)
        self.assertEqual(self._call(self.principal, "post", f"{PAPERS}{pid}/schedule/", {"release_at": soon.isoformat()}).status_code, 200)
        self.assertEqual(self._call(self.teacher_with_exams(), "get", f"{PAPERS}{pid}/").status_code, 404)
        with tenant_context(self.school):
            QuestionPaper.objects.filter(pk=pid).update(release_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self._call(self.teacher_with_exams(), "get", f"{PAPERS}{pid}/").status_code, 200)
        self.assertEqual(self._call(self.principal, "post", f"{PAPERS}{pid}/schedule/", {"release_at": (timezone.now() - timedelta(hours=1)).isoformat()}).status_code, 400)

    def test_a_teacher_of_another_subject_never_sees_it(self):
        pid = self.approved_paper()
        self._call(self.principal, "post", f"{PAPERS}{pid}/release/")
        other = self._user("sci_teacher", self.school, codenames=["view_examinations"], teacher=True)
        self.assign(other, self.science)
        self.assertEqual(self._call(other, "get", f"{PAPERS}{pid}/printable/").status_code, 404)
        self.assertEqual(self.rows(self._call(other, "get", PAPERS)), [])

    def test_students_and_parents_never_open_papers(self):
        pid = self.approved_paper()
        self._call(self.principal, "post", f"{PAPERS}{pid}/release/")
        for slug in ("student", "parent"):
            user = self._user(f"p_{slug}", self.school, role_slug=slug)
            for path in (PAPERS, f"{PAPERS}{pid}/", f"{PAPERS}{pid}/printable/", f"{PAPERS}{pid}/answer-key/"):
                self.assertEqual(self._call(user, "get", path).status_code, 403, (slug, path))

    def test_every_opening_is_logged_and_the_log_is_for_approvers(self):
        pid = self.approved_paper()
        self._call(self.controller, "get", f"{PAPERS}{pid}/printable/")
        self._call(self.principal, "get", f"{PAPERS}{pid}/answer-key/")
        with tenant_context(self.school):
            kinds = sorted(PaperAccessLog.objects.filter(paper_id=pid).values_list("kind", flat=True))
        self.assertEqual(kinds, ["answer_key", "paper"])
        self.assertEqual(self._call(self.controller, "get", f"{PAPERS}{pid}/access-log/").status_code, 403)
        self.assertEqual(len(self._call(self.principal, "get", f"{PAPERS}{pid}/access-log/").data), 2)

    def test_withdrawal_needs_a_reason_and_hides_the_paper(self):
        pid = self.approved_paper()
        self._call(self.principal, "post", f"{PAPERS}{pid}/release/")
        self.assertEqual(self._call(self.principal, "post", f"{PAPERS}{pid}/withdraw/", {}).status_code, 400)
        self.assertEqual(self._call(self.principal, "post", f"{PAPERS}{pid}/withdraw/", {"reason": "Leaked"}).data["status"], "withdrawn")
        self.assertEqual(self._call(self.teacher_with_exams(), "get", f"{PAPERS}{pid}/").status_code, 404)

    def test_another_school_cannot_reach_the_paper(self):
        pid = self.approved_paper()
        owner_b = self._user("paper_owner_b", self.school_b, role_slug="owner")
        self.assertEqual(self._call(owner_b, "get", f"{PAPERS}{pid}/", host=self.DOMAIN_B).status_code, 404)
        with tenant_context(self.school_b):
            self.assertEqual(QuestionPaper.objects.count(), 0)

    def test_the_two_permissions_exist(self):
        from roles.constants import SYSTEM_PERMISSIONS

        codes = {p["codename"] for p in SYSTEM_PERMISSIONS}
        self.assertTrue({"prepare_papers", "approve_papers"} <= codes)

    def test_withdrawn_papers_free_their_questions_for_another_set(self):
        pid = self.approved_paper()
        self._call(self.principal, "post", f"{PAPERS}{pid}/withdraw/", {"reason": "Replaced"})
        replacement = self.paper(label="A")
        self.assertEqual(self.add(replacement, self.mcq_easy[0]).status_code, 200)


class ChoicesTests(PaperFixture):
    def test_preparers_get_open_examinations_and_subjects(self):
        data = self._call(self.controller, "get", "papers/choices/").data
        self.assertEqual([e["name"] for e in data["examinations"]], ["Half-Yearly 2026"])
        self.assertEqual({s["code"] for s in data["subjects"]}, {"MAT8", "SCI8"})
        self.assertEqual(self._call(self.teacher, "get", "papers/choices/").status_code, 403)
