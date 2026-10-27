"""Stage A of the examination review: marks-aware blueprints, due releases, workflow notices, question usage, the
profile's permission list, and two-person result publishing.

Creates tenant schemas, so it needs a disposable PostgreSQL database.
"""
from datetime import timedelta

from django.utils import timezone
from django_tenants.utils import tenant_context

from examinations.models import Examination, ExaminationSettings
from notifications.models import Notification
from roles.models import Permission, Role, UserRole

from .models import PaperQuestion, QuestionPaper
from .tests_papers import PaperFixture

PAPERS = "papers/"


class MarksBlueprintTests(PaperFixture):
    def test_a_rule_with_marks_picks_only_questions_of_those_marks(self):
        pid = self.paper(total="10")
        section = self.section_id(pid)
        self.rule(section, 1, question_type="", marks="5")
        self.assertEqual(self._call(self.controller, "post", f"{PAPERS}{pid}/autofill/", {}).status_code, 200)
        with tenant_context(self.school):
            marks = [str(i.question.marks) for i in PaperQuestion.objects.filter(paper_id=pid).select_related("question")]
        self.assertEqual(marks, ["5.00"], "only a 5-mark question (a long answer) fits")

    def test_the_planned_marks_must_equal_the_paper_total(self):
        pid = self.paper(total="10")
        section = self.section_id(pid)
        self.rule(section, 5, question_type="mcq", marks="1")
        self.rule(section, 1, question_type="long", marks="5")
        detail = self.detail(pid)
        self.assertEqual(detail["blueprint"]["planned_marks"], "10.00")
        self.assertFalse(any("blueprint plans" in p for p in detail["problems"]))
        self.rule(section, 1, question_type="mcq", marks="1")
        problems = self.detail(pid)["problems"]
        self.assertTrue(any("The blueprint plans 11 marks; the paper is for 10." in p for p in problems), problems)

    def test_planned_marks_stay_open_while_a_rule_has_no_marks(self):
        pid = self.paper(total="10")
        self.rule(self.section_id(pid), 5, question_type="mcq")
        self.assertIsNone(self.detail(pid)["blueprint"]["planned_marks"])

    def test_the_summary_shows_availability_before_filling(self):
        pid = self.paper(total="10")
        section = self.section_id(pid)
        self.rule(section, 9, question_type="long", marks="5")
        row = self.detail(pid)["blueprint"]["rules"][0]
        self.assertEqual((row["needed"], row["available"]), (9, 3))

    def test_a_rule_with_bad_marks_is_refused(self):
        pid = self.paper()
        resp = self._call(self.controller, "post", "blueprint-rules/", {"section": self.section_id(pid), "count": 1, "marks": "0"})
        self.assertEqual(resp.status_code, 400)


class ReleaseAndUsageTests(PaperFixture):
    def test_a_paper_past_its_release_time_becomes_released(self):
        pid = self.approved_paper()
        self._call(self.principal, "post", f"{PAPERS}{pid}/schedule/", {"release_at": (timezone.now() + timedelta(hours=1)).isoformat()})
        with tenant_context(self.school):
            when = timezone.now() - timedelta(minutes=5)
            QuestionPaper.objects.filter(pk=pid).update(release_at=when)
        data = self.detail(pid, user=self.principal)
        self.assertEqual(data["status"], "released")
        self.assertEqual(self.rows(self._call(self.principal, "get", f"{PAPERS}?status=released"))[0]["id"], pid)

    def test_usage_is_shown_and_unused_questions_can_be_filtered(self):
        pid = self.approved_paper()
        used = self._call(self.teacher, "get", f"questions/{self.mcq_easy[0]}/").data
        self.assertEqual(used["times_used"], 1)
        self.assertIn("Half-Yearly 2026 (Set A)", used["last_used_in"])
        other = self.paper(label="B", allow_shared_questions=True)
        unused = {r["id"] for r in self.rows(self._call(self.controller, "get", f"{PAPERS}{other}/candidates/?unused=true"))}
        self.assertNotIn(self.mcq_easy[0], unused, f"used in paper {pid}")
        self.assertIn(self.mcq_easy[5], unused)


class NotificationTests(PaperFixture):
    def notices(self, user, category="question_bank"):
        with tenant_context(self.school):
            return list(Notification.objects.filter(recipient_user_id=user.id, category=category).values_list("title", flat=True))

    def test_submitting_a_question_tells_the_reviewer_not_the_author(self):
        qid = self.create(self.teacher, {"subject": str(self.maths.id), "question_type": "long", "marks": "5",
                                         "body": "Prove that root 2 is irrational.", "answer": "By contradiction."})
        self._call(self.teacher, "post", f"questions/{qid}/submit/")
        self.assertTrue(any("waiting for review" in t for t in self.notices(self.reviewer)))
        self.assertFalse(any("waiting for review" in t for t in self.notices(self.teacher)))

    def test_paper_hand_overs_are_announced(self):
        pid = self.ready_paper()
        self._call(self.controller, "post", f"{PAPERS}{pid}/submit/")
        self.assertTrue(any("waiting for approval" in t for t in self.notices(self.principal)))
        self.assertFalse(any("waiting for approval" in t for t in self.notices(self.controller)))
        self._call(self.principal, "post", f"{PAPERS}{pid}/approve/")
        self.assertTrue(any("Paper approved" in t for t in self.notices(self.controller)))
        self._call(self.principal, "post", f"{PAPERS}{pid}/release/")
        self.assertTrue(any("released" in t for t in self.notices(self.teacher)), "the subject teacher is told")


class ProfilePermissionTests(PaperFixture):
    def test_the_profile_lists_what_every_role_grants(self):
        with tenant_context(self.school):
            extra = Role.objects.create(name="Exam desk", slug="exam-desk", is_system_role=False)
            extra.permissions.set(Permission.objects.filter(codename="approve_papers"))
            UserRole.objects.create(user=self.controller, role=extra)
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.controller)
        me = client.get("/api/auth/me/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(me.status_code, 200, me.data)
        self.assertTrue({"prepare_papers", "approve_papers"} <= set(me.data["permissions"]), me.data["permissions"])

    def test_the_owner_still_gets_everything(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.owner)
        self.assertEqual(client.get("/api/auth/me/", HTTP_HOST=self.DOMAIN_A).data["permissions"], ["*"])


class TwoPersonPublishingTests(PaperFixture):
    """Results publishing, with the school setting off (the default) and on."""

    def setUp(self):
        super().setUp()
        self.office = self._user("office", self.school, codenames=["manage_examinations", "publish_results", "view_examinations"])
        self.head = self._user("head", self.school, codenames=["publish_results", "view_examinations"])
        from datetime import date, time

        from examinations.models import ExamMark, ExamSchedule
        from profiles.models import Profile
        from students.models import Student, StudentLevel

        with tenant_context(self.school):
            student = Student.objects.create(profile=Profile.objects.create(first_name="Pupil", last_name="One"), enrollment_id="QB-P-1", status="active")
            StudentLevel.objects.create(student=student, level=self.level, section=self.section_a, academic_year="2026-27", is_current=True)
            schedule = ExamSchedule.objects.create(examination=self.exam, academic_year="2026-27", subject=self.maths, section=self.section_a,
                                                   date=date(2026, 9, 15), start_time=time(9), end_time=time(11), max_marks=100, pass_marks=33)
            ExamMark.objects.create(exam_schedule=schedule, student=student, marks_obtained=70)

    def exams(self, user, method, path, data=None):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user)
        return getattr(client, method)(f"/api/examinations/{path}", data, format="json", HTTP_HOST=self.DOMAIN_A)

    def test_with_the_setting_off_one_person_publishes_as_before(self):
        self.assertEqual(self.exams(self.office, "get", "settings/").data["require_separate_publisher"], False)
        resp = self.exams(self.office, "post", f"examinations/{self.exam.id}/publish/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["published_by_user_id"], str(self.office.id))

    def test_with_the_setting_on_a_request_and_a_second_person_are_needed(self):
        self.assertEqual(self.exams(self.office, "patch", "settings/", {"require_separate_publisher": True}).status_code, 200)
        self.assertEqual(self.exams(self.office, "post", f"examinations/{self.exam.id}/publish/").status_code, 400, "no request yet")
        self.assertEqual(self.exams(self.office, "post", f"examinations/{self.exam.id}/request-publication/").status_code, 200)
        with tenant_context(self.school):
            self.assertTrue(Notification.objects.filter(recipient_user_id=self.head.id, category="examinations").exists())
        self.assertEqual(self.exams(self.office, "post", f"examinations/{self.exam.id}/publish/").status_code, 400, "not the requester")
        resp = self.exams(self.head, "post", f"examinations/{self.exam.id}/publish/")
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            exam = Examination.objects.get(pk=self.exam.pk)
            self.assertTrue(exam.is_published)
            self.assertEqual((exam.publication_requested_by_user_id, exam.published_by_user_id), (self.office.id, self.head.id))

    def test_settings_need_the_right_permission_and_a_boolean(self):
        self.assertEqual(self.exams(self.head, "patch", "settings/", {"require_separate_publisher": True}).status_code, 403)
        self.assertEqual(self.exams(self.office, "patch", "settings/", {"require_separate_publisher": "yes"}).status_code, 400)
        self.assertEqual(self.exams(self.office, "patch", "settings/", {"nonsense": True}).status_code, 400)
        with tenant_context(self.school):
            self.assertEqual(ExaminationSettings.objects.count(), 0)

    def test_request_fields_cannot_be_set_directly(self):
        resp = self.exams(self.office, "patch", f"examinations/{self.exam.id}/", {"publication_requested_by_user_id": str(self.head.id)})
        self.assertIn(resp.status_code, (200, 400))
        with tenant_context(self.school):
            self.assertIsNone(Examination.objects.get(pk=self.exam.pk).publication_requested_by_user_id)
