"""Stage B, marks integrity: history with reasons, exam attendance, grace marks, rechecks and CSV import."""
import datetime
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context

from .models import ExamMark, ExamMarkChange, ExamResult, RecheckRequest
from .tests import ExamFixtureMixin


class StageBBase(ExamFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.schedule = self._create_schedule()
        self.owner = self._client_as(self.owner_user)
        self.teacher = self._client_as(self.instructor_user)

    def marks_url(self, schedule=None):
        return f"/api/examinations/schedules/{(schedule or self.schedule).id}/marks/"

    def post_marks(self, client, records, reason=None, schedule=None):
        body = {"records": records}
        if reason is not None:
            body["reason"] = reason
        return client.post(self.marks_url(schedule), body, HTTP_HOST=self.DOMAIN, format="json")

    def rec(self, student, marks=None, **extra):
        return {"student": str(student.id), "marks_obtained": marks, **extra}

    def publish(self):
        resp = self.owner.post(f"/api/examinations/examinations/{self.examination.id}/publish/", HTTP_HOST=self.DOMAIN)
        assert resp.status_code == 200, resp.data

    def mark_of(self, student, schedule=None):
        with tenant_context(self.school):
            return ExamMark.objects.get(exam_schedule=schedule or self.schedule, student=student)

    def result_of(self, student):
        with tenant_context(self.school):
            return ExamResult.objects.get(examination=self.examination, student=student)


class MarksHistoryTests(StageBBase):
    def test_first_entry_and_changes_are_recorded_and_unchanged_resubmission_is_not(self):
        self.assertEqual(self.post_marks(self.teacher, [self.rec(self.student, 70), self.rec(self.student2, 55)]).status_code, 200)
        with tenant_context(self.school):
            self.assertEqual(ExamMarkChange.objects.filter(kind="entry").count(), 2)
        self.post_marks(self.teacher, [self.rec(self.student, 70), self.rec(self.student2, 55)])
        with tenant_context(self.school):
            self.assertEqual(ExamMarkChange.objects.count(), 2, "an unchanged resubmission writes no history")
        self.post_marks(self.teacher, [self.rec(self.student, 72)], reason="Totalling error")
        with tenant_context(self.school):
            change = ExamMarkChange.objects.get(kind="correction")
            self.assertEqual((change.old_marks, change.new_marks), (Decimal("70"), Decimal("72")))
            self.assertEqual(change.reason, "Totalling error")
            self.assertEqual(change.changed_by_user_id, self.instructor_user.id)

    def test_saved_marks_can_be_read_back(self):
        self.post_marks(self.teacher, [self.rec(self.student, 64, remarks="Neat")])
        resp = self.teacher.get(self.marks_url(), HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        row = resp.data["marks"][0]
        self.assertEqual((row["student"], row["marks_obtained"], row["attendance"], row["remarks"]),
                         (self.student.id, "64.00", "present", "Neat"))
        self.assertFalse(resp.data["is_published"])

    def test_other_teacher_cannot_read_marks(self):
        resp = self._client_as(self.other_instructor_user).get(self.marks_url(), HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_locked_schedule_change_needs_a_reason(self):
        self.post_marks(self.teacher, [self.rec(self.student, 70)])
        self.owner.post(f"/api/examinations/schedules/{self.schedule.id}/lock/", {"is_locked": True}, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(self.post_marks(self.teacher, [self.rec(self.student, 75)]).status_code, 423, "teacher stays locked out")
        resp = self.post_marks(self.owner, [self.rec(self.student, 75)])
        self.assertEqual(resp.status_code, 400)
        self.assertIn("reason", resp.data)
        self.assertEqual(self.mark_of(self.student).marks_obtained, Decimal("70"), "nothing saved without a reason")
        self.assertEqual(self.post_marks(self.owner, [self.rec(self.student, 75)], reason="Re-totalled").status_code, 200)
        self.assertEqual(self.mark_of(self.student).marks_obtained, Decimal("75"))

    def test_locked_schedule_first_entry_needs_no_reason(self):
        self.owner.post(f"/api/examinations/schedules/{self.schedule.id}/lock/", {"is_locked": True}, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(self.post_marks(self.owner, [self.rec(self.student, 50)]).status_code, 200)

    def test_published_examination_marks_cannot_be_edited_directly(self):
        self.post_marks(self.teacher, [self.rec(self.student, 70)])
        self.publish()
        resp = self.post_marks(self.owner, [self.rec(self.student, 99)], reason="anything")
        self.assertEqual(resp.status_code, 423)
        self.assertEqual(self.mark_of(self.student).marks_obtained, Decimal("70"))


class AttendanceTests(StageBBase):
    def test_medical_counts_as_absent_and_clears_marks(self):
        self.post_marks(self.teacher, [self.rec(self.student, 60, attendance="medical")])
        mark = self.mark_of(self.student)
        self.assertEqual((mark.attendance, mark.is_absent, mark.marks_obtained), ("medical", True, None))

    def test_older_clients_sending_only_is_absent_still_work(self):
        self.post_marks(self.teacher, [self.rec(self.student, None, is_absent=True), self.rec(self.student2, 40, is_absent=False)])
        self.assertEqual(self.mark_of(self.student).attendance, "absent")
        self.assertEqual(self.mark_of(self.student2).attendance, "present")

    def test_exempt_subject_is_left_out_of_the_result(self):
        science = self._create_schedule(subject=self.second_subject, date=datetime.date(2026, 6, 3))
        self.post_marks(self.teacher, [self.rec(self.student, 80)])
        self.post_marks(self.owner, [self.rec(self.student, None, attendance="exempt")], schedule=science)
        self.publish()
        result = self.result_of(self.student)
        self.assertEqual(result.total_max_marks, Decimal("100"), "only the subject the student sat counts")
        self.assertTrue(result.is_pass)
        self.assertEqual(len(result.subject_breakdown), 1)

    def test_malpractice_fails_the_subject(self):
        self.post_marks(self.teacher, [self.rec(self.student, None, attendance="malpractice")])
        self.publish()
        result = self.result_of(self.student)
        self.assertFalse(result.is_pass)
        self.assertEqual(result.subject_breakdown[0]["attendance"], "malpractice")


class GraceTests(StageBBase):
    def grace(self, client, mark, grace, reason="Board moderation"):
        return client.post(f"/api/examinations/marks/{mark.id}/grace/", {"grace_marks": grace, "reason": reason},
                           HTTP_HOST=self.DOMAIN, format="json")

    def test_grace_marks_lift_a_borderline_fail_to_a_pass(self):
        self.post_marks(self.teacher, [self.rec(self.student, 37)])
        self.assertEqual(self.grace(self.owner, self.mark_of(self.student), "3").status_code, 200)
        self.publish()
        result = self.result_of(self.student)
        self.assertTrue(result.is_pass)
        self.assertEqual(result.total_marks_obtained, Decimal("40"))
        self.assertEqual(result.subject_breakdown[0]["grace_marks"], 3.0)
        with tenant_context(self.school):
            change = ExamMarkChange.objects.get(kind="grace")
            self.assertEqual((change.old_grace, change.new_grace, change.reason), (Decimal("0"), Decimal("3"), "Board moderation"))

    def test_grace_needs_a_reason_and_stays_under_the_maximum(self):
        self.post_marks(self.teacher, [self.rec(self.student, 98)])
        mark = self.mark_of(self.student)
        self.assertEqual(self.grace(self.owner, mark, "1", reason="  ").status_code, 400)
        self.assertEqual(self.grace(self.owner, mark, "3").status_code, 400)
        self.assertEqual(self.grace(self.owner, mark, "-1").status_code, 400)
        self.assertEqual(self.grace(self.owner, mark, "abc").status_code, 400)
        self.assertEqual(self.grace(self.owner, mark, "2").status_code, 200)

    def test_grace_needs_manage_marks(self):
        self.post_marks(self.teacher, [self.rec(self.student, 37)])
        self.assertEqual(self.grace(self.teacher, self.mark_of(self.student), "3").status_code, 403)

    def test_grace_not_for_an_absent_student(self):
        self.post_marks(self.teacher, [self.rec(self.student, None, attendance="absent")])
        self.assertEqual(self.grace(self.owner, self.mark_of(self.student), "3").status_code, 400)

    def test_grace_after_publication_updates_the_published_result(self):
        self.post_marks(self.teacher, [self.rec(self.student, 38)])
        self.publish()
        self.assertFalse(self.result_of(self.student).is_pass)
        self.assertEqual(self.grace(self.owner, self.mark_of(self.student), "2").status_code, 200)
        self.assertTrue(self.result_of(self.student).is_pass)


class RecheckTests(StageBBase):
    URL = "/api/examinations/rechecks/"

    def setUp(self):
        super().setUp()
        self.post_marks(self.teacher, [self.rec(self.student, 35), self.rec(self.student2, 60)])
        self.pupil = self._client_as(self.student_user)

    def ask(self, client, body):
        return client.post(self.URL, body, HTTP_HOST=self.DOMAIN, format="json")

    def own_request(self, reason="Question 4 was not counted"):
        return self.ask(self.pupil, {"examination": str(self.examination.id), "subject": str(self.subject.id), "reason": reason})

    def decide(self, client, recheck_id, body):
        return client.post(f"{self.URL}{recheck_id}/decide/", body, HTTP_HOST=self.DOMAIN, format="json")

    def test_no_recheck_before_publication(self):
        self.assertEqual(self.own_request().status_code, 400)

    def test_student_asks_about_own_mark_and_accepted_recheck_updates_result(self):
        self.publish()
        self.assertFalse(self.result_of(self.student).is_pass)
        resp = self.own_request()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["original_marks"], "35.00")
        self.assertEqual(self.own_request().status_code, 400, "one waiting recheck per mark")

        self.assertEqual(self.decide(self.teacher, resp.data["id"], {"decision": "accept", "revised_marks": "41"}).status_code, 403)
        done = self.decide(self.owner, resp.data["id"], {"decision": "accept", "revised_marks": "41", "decision_comment": "Q4 added"})
        self.assertEqual(done.status_code, 200, done.data)
        self.assertEqual(done.data["status"], "accepted")
        self.assertEqual(self.mark_of(self.student).marks_obtained, Decimal("41"))
        self.assertTrue(self.result_of(self.student).is_pass)
        with tenant_context(self.school):
            self.assertTrue(ExamMarkChange.objects.filter(kind="recheck", old_marks=35, new_marks=41).exists())
        self.assertEqual(self.decide(self.owner, resp.data["id"], {"decision": "reject", "decision_comment": "x"}).status_code, 400)

    def set_fee(self, amount):
        from .models import ExaminationSettings

        with tenant_context(self.school):
            ExaminationSettings.objects.update_or_create(singleton=True, defaults={"recheck_fee": Decimal(amount)})

    def collect(self, client, recheck_id, body=None):
        return client.post(f"{self.URL}{recheck_id}/collect-fee/", body or {}, HTTP_HOST=self.DOMAIN, format="json")

    def test_a_recheck_is_free_until_the_school_sets_a_fee(self):
        self.publish()
        resp = self.own_request()
        self.assertEqual((resp.status_code, resp.data["fee_amount"], resp.data["fee_paid_at"]), (201, "0.00", None))
        self.assertEqual(self.collect(self.owner, resp.data["id"]).status_code, 400)  # nothing to collect
        self.assertEqual(self.decide(self.owner, resp.data["id"], {"decision": "reject", "decision_comment": "ok"}).status_code, 200)

    def test_with_a_fee_the_recheck_cannot_be_decided_until_the_fee_is_collected(self):
        self.publish()
        self.set_fee("100")
        resp = self.own_request()
        self.assertEqual(resp.data["fee_amount"], "100.00")
        rid = resp.data["id"]
        blocked = self.decide(self.owner, rid, {"decision": "accept", "revised_marks": "41"})
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("fee", str(blocked.data))
        self.assertEqual(self.collect(self.pupil, rid).status_code, 403)  # a student cannot mark their own fee paid
        self.assertEqual(self.collect(self.teacher, rid).status_code, 403)
        paid = self.collect(self.owner, rid, {"reference": "Receipt 77"})
        self.assertEqual(paid.status_code, 200, paid.data)
        self.assertEqual((paid.data["fee_reference"], bool(paid.data["fee_paid_at"])), ("Receipt 77", True))
        self.assertEqual(self.collect(self.owner, rid).status_code, 400)  # only once
        self.assertEqual(self.decide(self.owner, rid, {"decision": "accept", "revised_marks": "41"}).status_code, 200)

    def test_changing_the_fee_does_not_change_requests_already_made(self):
        self.publish()
        self.set_fee("100")
        rid = self.own_request().data["id"]
        self.set_fee("250")
        listed = self.owner.get(self.URL, HTTP_HOST=self.DOMAIN)
        self.assertEqual(next(r for r in listed.data["results"] if r["id"] == rid)["fee_amount"], "100.00")

    def test_the_fee_setting_takes_a_sensible_amount_only(self):
        url = "/api/examinations/settings/"
        for bad in ("-5", "abc", "999999999", True):
            self.assertEqual(self.owner.patch(url, {"recheck_fee": bad}, HTTP_HOST=self.DOMAIN, format="json").status_code, 400, bad)
        ok = self.owner.patch(url, {"recheck_fee": "75.5"}, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual((ok.status_code, ok.data["recheck_fee"]), (200, "75.50"))

    def test_student_cannot_ask_about_another_students_mark(self):
        self.publish()
        other = self.mark_of(self.student2)
        self.assertEqual(self.ask(self.pupil, {"mark": str(other.id), "reason": "please"}).status_code, 403)

    def test_rejection_needs_a_comment_and_leaves_marks_alone(self):
        self.publish()
        rid = self.own_request().data["id"]
        self.assertEqual(self.decide(self.owner, rid, {"decision": "reject"}).status_code, 400)
        self.assertEqual(self.decide(self.owner, rid, {"decision": "reject", "decision_comment": "Marked correctly"}).status_code, 200)
        self.assertEqual(self.mark_of(self.student).marks_obtained, Decimal("35"))

    def test_accept_rejects_marks_outside_the_range(self):
        self.publish()
        rid = self.own_request().data["id"]
        self.assertEqual(self.decide(self.owner, rid, {"decision": "accept", "revised_marks": "101"}).status_code, 400)
        self.assertEqual(self.decide(self.owner, rid, {"decision": "accept"}).status_code, 400)
        with tenant_context(self.school):
            self.assertEqual(RecheckRequest.objects.get(pk=rid).status, "pending")

    def test_lists_show_own_requests_to_students_and_all_to_managers(self):
        self.publish()
        self.own_request()
        self.ask(self.owner, {"mark": str(self.mark_of(self.student2).id), "reason": "Parent asked"})
        self.assertEqual(self.pupil.get(self.URL, HTTP_HOST=self.DOMAIN).data["count"], 1)
        self.assertEqual(self.owner.get(self.URL, HTTP_HOST=self.DOMAIN).data["count"], 2)
        self.assertEqual(self.owner.get(self.URL + "?status=pending", HTTP_HOST=self.DOMAIN).data["count"], 2)

    def test_staff_without_results_permission_cannot_ask(self):
        self.publish()
        user = self._build_user("exam_plain_staff", "staff")
        self._give_role_only(user, ["view_examinations"])
        resp = self.ask(self._client_as(user), {"mark": str(self.mark_of(self.student).id), "reason": "x"})
        self.assertEqual(resp.status_code, 403)


class CsvImportTests(StageBBase):
    def upload(self, client, text, dry_run=False, reason=""):
        f = SimpleUploadedFile("marks.csv", text.encode("utf-8"), content_type="text/csv")
        return client.post(f"/api/examinations/schedules/{self.schedule.id}/marks-import/",
                           {"file": f, "dry_run": "true" if dry_run else "false", "reason": reason},
                           HTTP_HOST=self.DOMAIN, format="multipart")

    def test_preview_saves_nothing_then_import_saves_all(self):
        text = "enrollment_id,marks,attendance,remarks\nENR-EX-1,72.5,,Good\nenr-ex-2,,absent,\n"
        preview = self.upload(self.teacher, text, dry_run=True)
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data["total"], 2)
        with tenant_context(self.school):
            self.assertFalse(ExamMark.objects.exists())
        done = self.upload(self.teacher, text)
        self.assertEqual(done.status_code, 200, done.data)
        self.assertEqual(done.data["created"], 2)
        self.assertEqual(self.mark_of(self.student).marks_obtained, Decimal("72.5"))
        self.assertEqual(self.mark_of(self.student2).attendance, "absent")
        with tenant_context(self.school):
            self.assertEqual(ExamMarkChange.objects.filter(kind="import").count(), 2)

    def test_one_bad_row_saves_nothing_and_names_every_problem(self):
        text = "enrollment_id,marks\nENR-EX-1,72\nENR-EX-3,50\nENR-EX-2,150\nENR-EX-1,10\n"
        resp = self.upload(self.teacher, text)
        self.assertEqual(resp.status_code, 400)
        joined = " ".join(resp.data["errors"])
        self.assertIn("Line 3", joined)  # another section's student
        self.assertIn("Line 4", joined)  # above the maximum
        self.assertIn("Line 5", joined)  # duplicate
        with tenant_context(self.school):
            self.assertFalse(ExamMark.objects.exists())

    def test_missing_columns_and_bad_words(self):
        self.assertEqual(self.upload(self.teacher, "student,score\nENR-EX-1,5\n").status_code, 400)
        resp = self.upload(self.teacher, "enrollment_id,marks,attendance\nENR-EX-1,5,sleeping\n")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("attendance", resp.data["errors"][0])
        self.assertEqual(self.upload(self.teacher, "enrollment_id,marks\nENR-EX-1,abc\n").status_code, 400)
        self.assertEqual(self.upload(self.teacher, "enrollment_id,marks\nENR-EX-1,5.555\n").status_code, 400)

    def test_import_follows_the_same_access_rules(self):
        other = self._client_as(self.other_instructor_user)
        self.assertEqual(self.upload(other, "enrollment_id,marks\nENR-EX-1,5\n").status_code, 403)
        self.upload(self.teacher, "enrollment_id,marks\nENR-EX-1,5\n")
        self.publish()
        self.assertEqual(self.upload(self.owner, "enrollment_id,marks\nENR-EX-1,9\n").status_code, 423)
