"""Payroll Stage P3: my payslips (privacy), the payslip PDF, the month summary, the CSV export and the
payslip-ready notices. Uses February 2026 as in tests_runs.

Creates tenant schemas, so it needs a disposable PostgreSQL database.
"""
import csv
import io
from datetime import date
from unittest import mock

from django.db import connection
from django_tenants.utils import tenant_context
from reportlab.pdfgen import canvas
from rest_framework.test import APIClient

from accounts.models import User
from core.models import AuditLog
from notifications.models import Notification
from profiles.models import Profile
from roles.models import Role, UserRole
from staff.models import StaffMember

from . import services
from .models import PayrollRun, Payslip
from .pdf import render_payslip_pdf
from .tests import D, Deduction, Earning
from .tests_runs import AFTER_FEB, RunFixture


class PayslipFixture(RunFixture):
    """Sita has a login linked to her staff record; Ram has none."""

    def setUp(self):
        super().setUp()
        connection.set_schema_to_public()
        self.sita_user = User.objects.create_user(username="pay_sita", email="pay_sita@pay.test", password="Pass1234!")
        self.other_user = User.objects.create_user(username="pay_other", email="pay_other@pay.test", password="Pass1234!")
        with tenant_context(self.school):
            Profile.objects.filter(pk=self.sita.profile_id).update(user_id=self.sita_user.id)
            UserRole.objects.create(user=self.sita_user, role=Role.objects.get(slug="staff"))
            # a login that is not a staff member at all (a parent, say)
            Profile.objects.create(user_id=self.other_user.id, first_name="Pat", last_name="Parent")
            UserRole.objects.create(user=self.other_user, role=Role.objects.get(slug="parent"))
        self.staff_with_salary(self.sita, "24000")
        self.staff_with_salary(self.ram, "20000")
        self.give(self.pf, self.sita)
        self.mark(self.sita, 3, "absent")

    def finished_run(self, pay=False):
        run = self.calculated()
        run = self.approve(run)
        if pay:
            with tenant_context(self.school), mock.patch("payroll.services.timezone.localdate", return_value=AFTER_FEB):
                run = services.record_payment(run, user_id=self.approver.id, paid_on=date(2026, 3, 3), method="bank_transfer", reference="B1")
        return run

    def my(self, user, path="", host=None):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.get(f"/api/payroll/my-payslips/{path}", HTTP_HOST=host or self.DOMAIN_A)

    def get(self, user, path, host=None):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.get(f"/api/payroll/{path}", HTTP_HOST=host or self.DOMAIN_A)


class MyPayslipTests(PayslipFixture):
    def test_a_staff_member_sees_only_their_own_approved_payslips(self):
        run = self.finished_run()
        rows = self.my(self.sita_user).data["results"]
        self.assertEqual([(r["employee_id"], r["month_label"], r["net_amount"]) for r in rows], [("E-P-1", "February 2026", "20600.00")])
        detail = self.my(self.sita_user, f"{rows[0]['id']}/").data
        self.assertEqual([(l["code"], l["amount"]) for l in detail["lines"]], [("BASIC", "24000.00"), ("PF", "2400.00"), ("UNPAID", "1000.00")])
        self.assertEqual(detail["net_amount"], "20600.00")

    def test_nothing_is_visible_before_approval_or_after_cancellation(self):
        run = self.calculated()
        self.assertEqual(self.my(self.sita_user).data["results"], [])         # calculated, not approved
        run = self.approve(run)
        self.assertEqual(len(self.my(self.sita_user).data["results"]), 1)
        with tenant_context(self.school):
            services.cancel_run(PayrollRun.objects.get(pk=run.pk), reason="Wrong")
        self.assertEqual(self.my(self.sita_user).data["results"], [])         # cancelled: gone again

    def test_a_staff_member_cannot_open_someone_elses_payslip(self):
        self.finished_run()
        with tenant_context(self.school):
            rams = Payslip.objects.get(staff=self.ram).pk
        for path in (f"{rams}/", f"{rams}/pdf/"):
            self.assertEqual(self.my(self.sita_user, path).status_code, 404, path)

    def test_people_without_a_staff_record_get_nothing(self):
        self.finished_run()
        self.assertEqual(self.my(self.other_user).status_code, 403)
        client = APIClient()
        self.assertIn(client.get("/api/payroll/my-payslips/", HTTP_HOST=self.DOMAIN_A).status_code, (401, 403))

    def test_the_owner_with_a_staff_stub_sees_only_their_own_which_is_none(self):
        self.finished_run()
        self.assertEqual(self.my(self.owner).data["results"], [])

    def test_the_payslip_is_final_when_the_salary_changes_later(self):
        self.finished_run()
        self.salary(self.sita, "99999", date(2026, 6, 1))
        self.assertEqual(self.my(self.sita_user).data["results"][0]["net_amount"], "20600.00")

    def test_read_only(self):
        self.finished_run()
        client = APIClient()
        client.force_authenticate(user=self.sita_user)
        for method in ("post", "put", "patch", "delete"):
            self.assertEqual(getattr(client, method)("/api/payroll/my-payslips/", {}, format="json", HTTP_HOST=self.DOMAIN_A).status_code, 405, method)

    def test_other_schools_cannot_see_it(self):
        self.finished_run()
        user_b = self._user("owner_p3b", self.school_b, role_slug="owner")
        resp = self.my(user_b, host=self.DOMAIN_B)
        self.assertEqual((resp.status_code, resp.data["results"]), (200, []))     # school B's owner: nothing of school A
        self.assertEqual(self.my(user_b, host=self.DOMAIN_A).status_code, 403)    # and no standing in school A


class PdfTests(PayslipFixture):
    def pdf_of(self, user, path):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.get(path, HTTP_HOST=self.DOMAIN_A)

    def test_my_payslip_pdf_is_a_real_pdf_with_the_right_numbers(self):
        self.finished_run()
        slip_id = self.my(self.sita_user).data["results"][0]["id"]
        resp = self.pdf_of(self.sita_user, f"/api/payroll/my-payslips/{slip_id}/pdf/")
        self.assertEqual((resp.status_code, resp["Content-Type"]), (200, "application/pdf"))
        self.assertTrue(resp.content.startswith(b"%PDF-") and resp.content.rstrip().endswith(b"%%EOF"))
        self.assertIn("payslip-E-P-1-2026-02.pdf", resp["Content-Disposition"])
        self.assertEqual(resp["Cache-Control"], "private, no-store")

    def test_the_pdf_shows_the_right_amounts_and_names(self):
        self.finished_run(pay=True)
        drawn = []
        originals = {name: getattr(canvas.Canvas, name) for name in ("drawString", "drawRightString")}

        def spy(name):
            def wrapper(self, x, y, text, *args, **kwargs):
                drawn.append(text)
                return originals[name](self, x, y, text, *args, **kwargs)
            return wrapper

        with tenant_context(self.school), mock.patch.object(canvas.Canvas, "drawString", spy("drawString")),                 mock.patch.object(canvas.Canvas, "drawRightString", spy("drawRightString")):
            slip = Payslip.objects.get(staff=self.sita)
            data = render_payslip_pdf(slip, list(slip.lines.all()), school_name="Green Valley School")
        self.assertTrue(data.startswith(b"%PDF-"))
        for needle in ("Green Valley School", "Payslip for February 2026", "Sita Karki", "E-P-1", "24,000.00", "2,400.00",
                       "1,000.00", "3,400.00", "20,600.00", "Net pay (NPR)"):
            self.assertIn(needle, drawn, needle)
        self.assertTrue(any("Paid on 3 March 2026" in t for t in drawn))
        self.assertFalse(any("?" in t for t in drawn))     # nothing had to be replaced

    def test_managers_can_open_any_payslip_pdf_and_it_is_audited(self):
        self.finished_run()
        with tenant_context(self.school):
            rams = Payslip.objects.get(staff=self.ram).pk
        resp = self.pdf_of(self.viewer_user(), f"/api/payroll/payslips/{rams}/pdf/")
        self.assertEqual((resp.status_code, resp["Content-Type"]), (200, "application/pdf"))
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="payslip_pdf_viewed", object_id=str(rams)).exists())
        self.assertEqual(self.pdf_of(self.sita_user, f"/api/payroll/payslips/{rams}/pdf/").status_code, 403)

    def viewer_user(self):
        return self._user("viewer3", self.school, codenames=["view_payroll"])

    def test_text_the_font_cannot_draw_is_replaced_and_the_pdf_still_renders(self):
        with tenant_context(self.school):
            StaffMember.objects.filter(pk=self.ram.pk).update(designation="शिक्षक")
            Profile.objects.filter(pk=self.ram.profile_id).update(first_name="राम")
        self.finished_run()
        with tenant_context(self.school):
            slip = Payslip.objects.get(staff=self.ram)
            data = render_payslip_pdf(slip, list(slip.lines.all()), school_name="School")
        self.assertTrue(data.startswith(b"%PDF-"))


class SummaryAndExportTests(PayslipFixture):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            StaffMember.objects.filter(pk=self.sita.pk).update(department="Science")
            StaffMember.objects.filter(pk=self.ram.pk).update(department="Admin")
        self.viewer = self._user("viewer4", self.school, codenames=["view_payroll"])

    def test_the_summary_adds_up(self):
        run = self.finished_run()
        data = self.get(self.viewer, f"runs/{run.pk}/summary/").data
        self.assertEqual((data["people"], data["gross"], data["deductions"], data["net"]), (2, "44000.00", "3400.00", "40600.00"))
        self.assertEqual({d["department"]: d["net"] for d in data["by_department"]}, {"Admin": "20000.00", "Science": "20600.00"})
        by_code = {c["code"]: (c["kind"], c["people"], c["total"]) for c in data["by_component"]}
        self.assertEqual(by_code["BASIC"], ("basic", 2, "44000.00"))
        self.assertEqual(by_code["PF"], ("deduction", 1, "2400.00"))
        self.assertEqual(by_code["UNPAID"], ("deduction", 1, "1000.00"))
        self.assertEqual((data["negative_net"], data["unpaid_days_total"]), (0, "1.0"))
        self.assertEqual(sum(D(c["total"]) for c in data["by_component"] if c["kind"] in ("basic", "earning")), D(data["gross"]))

    def test_the_summary_needs_view_payroll(self):
        run = self.finished_run()
        self.assertEqual(self.get(self.sita_user, f"runs/{run.pk}/summary/").status_code, 403)
        self.assertEqual(self.get(self.viewer, f"runs/{run.pk}/summary/").status_code, 200)

    def test_the_export_is_a_clean_csv_of_net_pay(self):
        run = self.finished_run()
        resp = self.get(self.viewer, f"runs/{run.pk}/export/")
        self.assertEqual((resp.status_code, resp["Content-Type"]), (200, "text/csv; charset=utf-8"))
        self.assertIn('attachment; filename="payroll-2026-02.csv"', resp["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(resp.content.decode())))
        self.assertEqual(rows[0], ["Employee ID", "Name", "Designation", "Department", "Gross", "Deductions", "Net pay"])
        self.assertEqual(sorted(r[0] for r in rows[1:]), ["E-P-1", "E-P-2"])
        sita = [r for r in rows if r[0] == "E-P-1"][0]
        self.assertEqual((sita[4], sita[5], sita[6]), ("24000.00", "3400.00", "20600.00"))
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="payroll_run_exported").exists())

    def test_names_that_look_like_spreadsheet_formulas_are_made_harmless(self):
        with tenant_context(self.school):
            Profile.objects.filter(pk=self.ram.profile_id).update(first_name="=HYPERLINK(\"http://evil\")", last_name="x")
            StaffMember.objects.filter(pk=self.ram.pk).update(designation="@SUM(A1)")
        run = self.finished_run()
        text = self.get(self.viewer, f"runs/{run.pk}/export/").content.decode()
        self.assertNotIn(",=HYPERLINK", text)
        self.assertNotIn(",@SUM", text)
        self.assertIn("'=HYPERLINK", text)

    def test_only_approved_or_paid_runs_can_be_exported(self):
        run = self.calculated()
        self.assertEqual(self.get(self.viewer, f"runs/{run.pk}/export/").status_code, 403)
        self.assertEqual(self.get(self.sita_user, f"runs/{run.pk}/export/").status_code, 403)

    def test_all_payslips_can_be_listed_and_filtered_by_person(self):
        self.finished_run()
        everyone = self.get(self.viewer, "payslips/").data
        self.assertEqual(everyone["count"], 2)
        only_sita = self.get(self.viewer, f"payslips/?staff={self.sita.pk}").data
        self.assertEqual([r["employee_id"] for r in only_sita["results"]], ["E-P-1"])
        self.assertEqual(self.get(self.sita_user, "payslips/").status_code, 403)


class NoticeTests(PayslipFixture):
    def notices(self):
        with tenant_context(self.school):
            return list(Notification.objects.filter(category="payroll"))

    def test_staff_with_a_login_are_told_when_their_payslip_is_ready(self):
        self.finished_run()
        notes = self.notices()
        self.assertEqual({n.recipient_user_id for n in notes}, {self.sita_user.id})     # Ram has no login
        self.assertEqual(notes[0].title, "Your payslip for February 2026 is ready")
        self.assertNotIn("20600", notes[0].title + notes[0].body)                        # no amounts in a notice

    def test_a_failing_notice_never_undoes_the_approval(self):
        run = self.calculated()
        with mock.patch("notifications.services.notify_many", side_effect=RuntimeError("inbox down")), \
                self.assertLogs("payroll.services", level="ERROR"):
            client = APIClient()
            client.force_authenticate(user=self.approver)
            with mock.patch("payroll.services.timezone.localdate", return_value=AFTER_FEB):
                resp = client.post(f"/api/payroll/runs/{run.pk}/approve/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual((resp.status_code, resp.data["status"]), (200, "approved"))
