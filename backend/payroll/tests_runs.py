"""Payroll Stage P2: monthly runs, payslips, unpaid days, adjustments, approval, locking and payment.

The month used throughout is February 2026: 28 days, Sundays on the 1st, 8th, 15th and 22nd, so with the
default weekly off (Sunday) it has 24 working days and a salary of 24,000 means exactly 1,000 a day.

Creates tenant schemas and uses real threads for the race cases, so it needs a disposable PostgreSQL
database and is meant to be run only in an isolated test stage.
"""
import threading
from datetime import date
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, connections, transaction
from django.utils import timezone
from django_tenants.utils import schema_context, tenant_context
from rest_framework import serializers

from academics.models import CalendarEvent
from attendance.models import AttendanceSettings, StaffAttendance
from core.models import AuditLog
from staff.models import LeaveApplication, LeaveType

from . import services
from .models import PayrollAdjustment, PayrollRun, PayrollSettings, Payslip, PayslipLine
from .tests import D, Deduction, Earning, JAN, PayrollFixture

FEB, MARCH = (2026, 2), (2026, 3)
FEB_FIRST, FEB_LAST = date(2026, 2, 1), date(2026, 2, 28)
AFTER_FEB = date(2026, 3, 5)   # "today" for the tests that approve or pay February


def day(n):
    return date(2026, 2, n)


class RunFixture(PayrollFixture):
    def setUp(self):
        super().setUp()
        self.manager = self._user("runner", self.school, codenames=["view_payroll", "run_payroll"])
        self.approver = self._user("approver", self.school, codenames=["view_payroll", "approve_payroll"])

    # -- data helpers
    def staff_with_salary(self, staff=None, amount="24000", on=JAN):
        self.salary(staff or self.sita, amount, on)

    def mark(self, staff, n, status):
        with tenant_context(self.school):
            StaffAttendance.objects.update_or_create(staff=staff, date=day(n), defaults={"status": status})

    def leave(self, staff, start, end, *, paid=False, status="approved", half=False, code=None):
        code = code or ("PD" if paid else "UP")
        with tenant_context(self.school):
            kind, _ = LeaveType.objects.get_or_create(code=code, defaults={"name": code, "is_paid": paid})
            return LeaveApplication.objects.create(
                staff=staff, leave_type=kind, academic_year="2025-26", start_date=start, end_date=end,
                is_half_day=half, reason="x", status=status, working_days=D("1"),
            )

    def holiday(self, d):
        with tenant_context(self.school):
            CalendarEvent.objects.create(title="Holiday", event_type="HOLIDAY", is_holiday=True, status="PUBLISHED", start_date=d, end_date=d)

    def weekly_off(self, days):
        with tenant_context(self.school):
            row = AttendanceSettings.get_solo()
            row.weekly_off_days = days
            row.save()

    # -- run helpers
    def new_run(self, ym=FEB, user=None):
        with tenant_context(self.school):
            return services.create_run(year=ym[0], month=ym[1], user_id=(user or self.owner).id)

    def calculate(self, run, user=None):
        with tenant_context(self.school):
            return services.calculate_run(run, user_id=(user or self.owner).id)

    def calculated(self, ym=FEB):
        return self.calculate(self.new_run(ym))

    def slip(self, run, staff=None):
        with tenant_context(self.school):
            return Payslip.objects.get(run=run, staff=staff or self.sita)

    def lines(self, run, staff=None):
        with tenant_context(self.school):
            return {l.code: l for l in self.slip(run, staff).lines.all()}

    def approve(self, run, user=None, today=AFTER_FEB):
        with tenant_context(self.school), mock.patch("payroll.services.timezone.localdate", return_value=today):
            return services.approve_run(run, user_id=(user or self.approver).id)


class CreateRunTests(RunFixture):
    def test_a_run_covers_the_whole_month(self):
        run = self.new_run()
        self.assertEqual((run.status, run.period_start, run.period_end), ("draft", FEB_FIRST, FEB_LAST))
        self.assertEqual((run.created_by_user_id, run.prepared_by_user_id), (self.owner.id, self.owner.id))

    def test_a_month_can_only_have_one_live_run_but_a_cancelled_one_does_not_count(self):
        run = self.new_run()
        with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
            services.create_run(year=2026, month=2)
        with tenant_context(self.school):
            services.cancel_run(run, reason="Started by mistake")
        again = self.new_run()
        self.assertNotEqual(again.pk, run.pk)
        with tenant_context(self.school):
            self.assertEqual(PayrollRun.objects.filter(year=2026, month=2).count(), 2)
            with self.assertRaises(IntegrityError), transaction.atomic():
                PayrollRun.objects.create(year=2026, month=2, period_start=FEB_FIRST, period_end=FEB_LAST)

    def test_bad_months_are_refused(self):
        for year, month in ((1999, 2), (2026, 0), (2026, 13), (2201, 1)):
            with self.subTest(year=year, month=month), tenant_context(self.school), self.assertRaises(serializers.ValidationError):
                services.create_run(year=year, month=month)
        with tenant_context(self.school), mock.patch("payroll.services.timezone.localdate", return_value=date(2026, 2, 10)):
            with self.assertRaises(serializers.ValidationError):
                services.create_run(year=2026, month=3)       # March has not started
            services.create_run(year=2026, month=2)           # the current month may be prepared


class CalculationTests(RunFixture):
    def test_a_full_month_with_no_problems(self):
        self.staff_with_salary()
        self.give(self.transport)
        self.give(self.pf)
        run = self.calculated()
        slip = self.slip(run)
        self.assertEqual((run.status, run.working_days, run.weekly_off_days), ("calculated", 24, [6]))
        self.assertEqual((slip.basic_amount, slip.gross_amount, slip.deductions_amount, slip.net_amount),
                         (D("24000"), D("25500"), D("2400"), D("23100")))
        self.assertEqual((slip.working_days, slip.unpaid_days, slip.unmarked_days), (24, D("0"), D("24")))
        self.assertEqual({code: line.amount for code, line in self.lines(run).items()}, {"BASIC": D("24000"), "TRANSPORT": D("1500"), "PF": D("2400")})
        self.assertEqual(run.calculation_notes["payslips"], 1)

    def test_the_payslip_copies_the_person_and_does_not_follow_later_changes(self):
        self.staff_with_salary()
        run = self.calculated()
        with tenant_context(self.school):
            from staff.models import StaffMember
            StaffMember.objects.filter(pk=self.sita.pk).update(designation="Principal", department="Admin")
        self.salary(self.sita, "99999", date(2026, 6, 1))
        slip = self.slip(run)
        self.assertEqual((slip.staff_name, slip.employee_id, slip.designation, slip.basic_amount), ("Sita Karki", "E-P-1", "Teacher", D("24000")))

    def test_absent_and_half_days_are_deducted_late_and_leave_are_not(self):
        self.staff_with_salary()
        for n, status in ((2, "absent"), (3, "absent"), (4, "half_day"), (5, "late"), (6, "leave"), (9, "present")):
            self.mark(self.sita, n, status)
        run = self.calculated()
        slip = self.slip(run)
        self.assertEqual(slip.unpaid_days, D("2.5"))
        line = self.lines(run)["UNPAID"]
        self.assertEqual((line.amount, line.kind, line.detail), (D("2500"), "deduction", "2.5 of 24 working days"))
        self.assertEqual(slip.net_amount, D("21500"))

    def test_unpaid_leave_is_deducted_paid_leave_and_unapproved_leave_are_not(self):
        self.staff_with_salary()
        self.leave(self.sita, day(9), day(11))                                   # Mon-Wed unpaid, approved: 3 days
        self.leave(self.sita, day(16), day(17), paid=True)                       # paid: nothing
        self.leave(self.sita, day(18), day(19), status="pending", code="UP2")    # not approved
        self.leave(self.sita, day(20), day(20), status="rejected", code="UP3")
        slip = self.slip(self.calculated())
        self.assertEqual((slip.unpaid_days, slip.net_amount), (D("3"), D("21000")))

    def test_half_day_leave_counts_half(self):
        self.staff_with_salary()
        self.leave(self.sita, day(10), day(10), half=True)
        self.assertEqual(self.slip(self.calculated()).unpaid_days, D("0.5"))

    def test_leave_that_spans_months_counts_only_this_months_working_days(self):
        self.staff_with_salary()
        self.leave(self.sita, date(2026, 1, 28), day(3))     # 1st is a Sunday: February 2nd and 3rd count
        self.leave(self.sita, day(26), date(2026, 3, 4))     # 26, 27 (28 is a Saturday: a working day): 26, 27, 28
        self.assertEqual(self.slip(self.calculated()).unpaid_days, D("5"))

    def test_a_day_is_never_counted_twice(self):
        self.staff_with_salary()
        self.leave(self.sita, day(9), day(10))
        self.mark(self.sita, 9, "absent")        # already covered by the unpaid leave
        self.mark(self.sita, 10, "half_day")     # the leave (a full day) wins over the half day
        self.mark(self.sita, 11, "absent")
        self.assertEqual(self.slip(self.calculated()).unpaid_days, D("3"))

    def test_weekly_off_days_and_holidays_are_never_unpaid_and_are_not_working_days(self):
        self.staff_with_salary()
        self.mark(self.sita, 8, "absent")        # a Sunday
        self.mark(self.sita, 12, "absent")       # a published holiday
        self.holiday(day(12))
        run = self.calculated()
        slip = self.slip(run)
        self.assertEqual((run.working_days, slip.unpaid_days, slip.net_amount), (23, D("0"), D("24000")))

    def test_the_schools_weekly_off_days_decide_the_working_days(self):
        self.staff_with_salary()
        self.weekly_off([5, 6])                  # Saturday and Sunday: 20 working days
        self.mark(self.sita, 7, "absent")        # a Saturday: not a working day now
        self.mark(self.sita, 9, "absent")
        run = self.calculated()
        slip = self.slip(run)
        self.assertEqual((run.working_days, run.weekly_off_days, slip.unpaid_days), (20, [5, 6], D("1")))
        self.assertEqual(self.lines(run)["UNPAID"].amount, D("1200"))       # 24000 / 20

    def test_a_month_with_no_working_days_is_refused(self):
        self.staff_with_salary()
        self.weekly_off([0, 1, 2, 3, 4, 5])      # only Sundays are left ...
        for n in (1, 8, 15, 22):                 # ... and every Sunday of February is a holiday
            self.holiday(day(n))
        with tenant_context(self.school):
            self.assertEqual(services.working_dates(FEB_FIRST, FEB_LAST), [])
            with self.assertRaises(serializers.ValidationError):
                services.calculate_run(services.create_run(year=2026, month=2, user_id=self.owner.id), user_id=self.owner.id)

    def test_someone_who_joined_mid_month_is_not_paid_for_the_days_before(self):
        self.staff_with_salary()
        with tenant_context(self.school):
            from staff.models import StaffMember
            StaffMember.objects.filter(pk=self.sita.pk).update(joining_date=day(16))
        slip = self.slip(self.calculated())
        self.assertEqual((slip.unpaid_days, slip.net_amount), (D("12"), D("12000")))     # 2-14 minus Sunday 8

    def test_unpaid_days_can_never_take_more_than_the_basic_salary(self):
        self.staff_with_salary(amount="24000")
        for n in (2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28):
            self.mark(self.sita, n, "absent")
        slip = self.slip(self.calculated())
        self.assertEqual((slip.unpaid_days, slip.net_amount), (D("24"), D("0")))
        self.give(self.pf)
        with tenant_context(self.school):
            slip = self.slip(services.calculate_run(PayrollRun.objects.get(year=2026, month=2), user_id=self.owner.id))
        self.assertTrue(slip.net_is_negative)                  # PF is still taken from nothing: flagged, not hidden
        self.assertEqual(slip.net_amount, D("-2400"))

    def test_rounding_follows_the_schools_setting(self):
        self.staff_with_salary(amount="25000")
        self.mark(self.sita, 2, "absent")
        run = self.calculated()
        self.assertEqual(self.lines(run)["UNPAID"].amount, D("1042"))            # 25000 / 24 = 1041.67 -> 1042
        with tenant_context(self.school):
            PayrollSettings.update_singleton(round_to_whole_rupee=False)
            run = services.calculate_run(run, user_id=self.owner.id)
        self.assertEqual((run.round_to_whole_rupee, self.lines(run)["UNPAID"].amount), (False, D("1041.67")))

    def test_who_is_included_and_who_is_left_out(self):
        self.staff_with_salary(self.sita)
        retired = self._staff(self.school, "E-P-7", "Old", "Timer", active=False)
        self.salary(self.ram, "20000", date(2026, 6, 1))                # salary starts after February
        run = self.calculated()
        self.assertEqual(run.calculation_notes["payslips"], 1)
        # Ram's salary starts later. Logging in as the owner also created a staff record for them
        # (a stub with no salary), so the list holds Ram and that stub, but never Sita.
        skipped = run.calculation_notes["skipped_no_salary"]
        self.assertIn("E-P-2", skipped)
        self.assertNotIn("E-P-1", skipped)
        self.assertEqual(run.calculation_notes["skipped_inactive"], 1)
        with tenant_context(self.school):
            self.assertEqual(Payslip.objects.filter(run=run).count(), 1)
            self.assertFalse(Payslip.objects.filter(run=run, staff=retired).exists())

    def test_the_salary_in_force_on_the_last_day_of_the_month_is_used(self):
        self.salary(self.sita, "20000", JAN)
        self.salary(self.sita, "30000", day(15))
        self.assertEqual(self.slip(self.calculated()).basic_amount, D("30000"))

    def test_calculating_again_replaces_the_payslips_and_picks_up_new_facts(self):
        self.staff_with_salary()
        run = self.calculated()
        old_id = self.slip(run).pk
        self.mark(self.sita, 2, "absent")
        run = self.calculate(run)
        with tenant_context(self.school):
            self.assertEqual(Payslip.objects.filter(run=run).count(), 1)
        slip = self.slip(run)
        self.assertNotEqual(slip.pk, old_id)
        self.assertEqual(slip.unpaid_days, D("1"))

    def test_only_a_draft_or_calculated_run_can_be_calculated(self):
        self.staff_with_salary()
        run = self.calculated()
        self.approve(run)
        with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
            services.calculate_run(PayrollRun.objects.get(pk=run.pk), user_id=self.owner.id)

    def test_lines_always_add_up_to_the_totals(self):
        self.staff_with_salary(amount="25137")
        for component in (self.da, self.transport, self.pf, self.fine):
            self.give(component)
        self.mark(self.sita, 3, "absent")
        run = self.calculated()
        slip = self.slip(run)
        with tenant_context(self.school):
            lines = list(slip.lines.all())
        earnings = sum(l.amount for l in lines if l.kind in ("basic", "earning"))
        taken = sum(l.amount for l in lines if l.kind == "deduction")
        self.assertEqual((slip.gross_amount, slip.deductions_amount, slip.net_amount), (earnings, taken, earnings - taken))


class AdjustmentTests(RunFixture):
    def add(self, run, kind=Earning, name="Bonus", amount="1000", reason="Annual day", staff=None, user=None):
        with tenant_context(self.school):
            return services.add_adjustment(run, staff=staff or self.sita, kind=kind, name=name, amount=D(amount),
                                           reason=reason, user_id=(user or self.owner).id)

    def test_adjustments_before_and_after_calculation_end_up_on_the_payslip(self):
        self.staff_with_salary()
        run = self.new_run()
        self.add(run, Earning, "Festival bonus", "5000", "Dashain")
        run = self.calculate(run)
        self.add(run, Deduction, "Advance recovery", "2000", "March advance")
        slip = self.slip(run)
        with tenant_context(self.school):
            lines = list(slip.lines.filter(code="ADJ").order_by("sort_order"))
        self.assertEqual([(l.name, l.kind, l.amount, l.detail) for l in lines],
                         [("Festival bonus", "earning", D("5000"), "Dashain"), ("Advance recovery", "deduction", D("2000"), "March advance")])
        self.assertEqual((slip.gross_amount, slip.deductions_amount, slip.net_amount), (D("29000"), D("2000"), D("27000")))

    def test_removing_an_adjustment_updates_the_payslip(self):
        self.staff_with_salary()
        run = self.calculated()
        adjustment = self.add(run, Deduction, "Fine", "500", "Late books")
        self.assertEqual(self.slip(run).net_amount, D("23500"))
        with tenant_context(self.school):
            services.remove_adjustment(adjustment)
        self.assertEqual(self.slip(run).net_amount, D("24000"))

    def test_an_adjustment_needs_a_reason_a_real_amount_and_an_active_person(self):
        self.staff_with_salary()
        run = self.calculated()
        for label, kwargs in {
            "no reason": dict(reason="  "), "no name": dict(name=""), "zero": dict(amount="0"), "negative": dict(amount="-5"),
            "three decimals": dict(amount="10.123"), "absurd": dict(amount="99999999999.99"), "bad kind": dict(kind="bonus"),
        }.items():
            with self.subTest(label), self.assertRaises(serializers.ValidationError):
                self.add(run, **kwargs)
        retired = self._staff(self.school, "E-P-6", "Old", "Timer", active=False)
        with self.assertRaises(serializers.ValidationError):
            self.add(run, staff=retired)
        with tenant_context(self.school):
            self.assertEqual(PayrollAdjustment.objects.count(), 0)

    def test_adjustments_cannot_change_after_approval(self):
        self.staff_with_salary()
        run = self.calculated()
        adjustment = self.add(run)
        self.approve(run)
        with self.assertRaises(serializers.ValidationError):
            self.add(run, name="Late")
        with tenant_context(self.school):
            with self.assertRaises(serializers.ValidationError):
                services.remove_adjustment(PayrollAdjustment.objects.get(pk=adjustment.pk))
            with self.assertRaises(RuntimeError):
                PayrollAdjustment.objects.get(pk=adjustment.pk).delete()


class ApprovalTests(RunFixture):
    def test_the_whole_life_of_a_run(self):
        self.staff_with_salary()
        run = self.calculated()
        run = self.approve(run)
        self.assertEqual((run.status, run.approved_by_user_id), ("approved", self.approver.id))
        with tenant_context(self.school), mock.patch("payroll.services.timezone.localdate", return_value=AFTER_FEB):
            run = services.record_payment(run, user_id=self.approver.id, paid_on=date(2026, 3, 3), method="bank_transfer", reference="BATCH-77")
        self.assertEqual((run.status, run.paid_on, run.payment_method, run.payment_reference, run.paid_by_user_id),
                         ("paid", date(2026, 3, 3), "bank_transfer", "BATCH-77", self.approver.id))

    def test_the_person_who_prepared_the_run_cannot_approve_it(self):
        self.staff_with_salary()
        run = self.calculated()
        with self.assertRaises(serializers.ValidationError) as caught:
            self.approve(run, user=self.owner)
        self.assertIn("different person", str(caught.exception.detail))
        # whoever calculated last is the one who prepared it
        run = self.calculate(run, user=self.approver)
        with self.assertRaises(serializers.ValidationError):
            self.approve(run, user=self.approver)
        self.approve(run, user=self.owner)

    def test_the_two_person_rule_can_be_switched_off(self):
        self.staff_with_salary()
        run = self.calculated()
        with tenant_context(self.school):
            PayrollSettings.update_singleton(require_separate_approver=False)
        self.assertEqual(self.approve(run, user=self.owner).status, "approved")

    def test_a_month_that_has_not_finished_cannot_be_approved(self):
        self.staff_with_salary()
        run = self.calculated()
        for today in (FEB_LAST, date(2026, 2, 10)):
            with self.subTest(today=today), self.assertRaises(serializers.ValidationError):
                self.approve(run, today=today)
        self.assertEqual(self.approve(run, today=date(2026, 3, 1)).status, "approved")

    def test_an_empty_or_negative_run_cannot_be_approved(self):
        run = self.calculated()                                   # nobody has a salary: no payslips
        with self.assertRaises(serializers.ValidationError):
            self.approve(run)
        self.staff_with_salary(amount="1000")
        self.give(self.fine, value="1500")
        run = self.calculate(run)
        self.assertTrue(self.slip(run).net_is_negative)
        with self.assertRaises(serializers.ValidationError):
            self.approve(run)
        with tenant_context(self.school):
            from .models import StaffSalaryComponent
            services.end_component(StaffSalaryComponent.objects.get(staff=self.sita, component=self.fine), effective_to=date(2026, 1, 31))
        run = self.calculate(run)
        self.assertEqual(self.approve(run).status, "approved")

    def test_only_a_calculated_run_can_be_approved_and_only_an_approved_one_paid(self):
        self.staff_with_salary()
        draft = self.new_run()
        with self.assertRaises(serializers.ValidationError):
            self.approve(draft)
        calculated = self.calculate(draft)
        with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
            services.record_payment(calculated, user_id=self.approver.id, paid_on=date(2026, 3, 3), method="cash")
        approved = self.approve(calculated)
        with self.assertRaises(serializers.ValidationError):
            self.approve(approved)

    def test_payment_details_are_checked(self):
        self.staff_with_salary()
        run = self.approve(self.calculated())
        cases = {"no method": dict(method="barter"), "future": dict(paid_on=date(2026, 3, 6)),
                 "before the month ended": dict(paid_on=date(2026, 2, 20))}
        for label, patch in cases.items():
            with self.subTest(label), tenant_context(self.school), mock.patch("payroll.services.timezone.localdate", return_value=AFTER_FEB):
                with self.assertRaises(serializers.ValidationError):
                    services.record_payment(run, user_id=self.approver.id, **{"paid_on": date(2026, 3, 3), "method": "cash", **patch})

    def test_a_paid_run_cannot_be_cancelled(self):
        self.staff_with_salary()
        run = self.approve(self.calculated())
        with tenant_context(self.school), mock.patch("payroll.services.timezone.localdate", return_value=AFTER_FEB):
            services.record_payment(run, user_id=self.approver.id, paid_on=date(2026, 3, 3), method="cash")
        with tenant_context(self.school), self.assertRaises(serializers.ValidationError):
            services.cancel_run(PayrollRun.objects.get(pk=run.pk), reason="oops")

    def test_cancelling_needs_a_reason_keeps_the_payslips_and_frees_the_month(self):
        self.staff_with_salary()
        run = self.approve(self.calculated())                     # even an approved run may be cancelled before payment
        with tenant_context(self.school):
            with self.assertRaises(serializers.ValidationError):
                services.cancel_run(PayrollRun.objects.get(pk=run.pk), reason=" ")
            cancelled = services.cancel_run(PayrollRun.objects.get(pk=run.pk), reason="Wrong attendance", user_id=self.owner.id)
            self.assertEqual((cancelled.status, cancelled.cancellation_reason), ("cancelled", "Wrong attendance"))
            self.assertEqual(Payslip.objects.filter(run=run).count(), 1)
        self.assertEqual(self.new_run().status, "draft")


class LockingTests(RunFixture):
    def test_an_approved_runs_payslips_cannot_be_changed_or_deleted(self):
        self.staff_with_salary()
        self.give(self.pf)
        run = self.calculated()
        self.approve(run)
        with tenant_context(self.school):
            slip = Payslip.objects.get(run=run)
            slip.net_amount = D("1")
            with self.assertRaises(RuntimeError):
                slip.save()
            with self.assertRaises(RuntimeError):
                slip.delete()
            line = slip.lines.first()
            line.amount = D("1")
            with self.assertRaises(RuntimeError):
                line.save()
            with self.assertRaises(RuntimeError):
                line.delete()
            self.assertEqual(Payslip.objects.get(pk=slip.pk).net_amount, D("21600"))

    def test_the_database_protects_people_and_runs_with_payslips(self):
        from django.db.models.deletion import ProtectedError
        self.staff_with_salary()
        run = self.calculated()
        with tenant_context(self.school):
            with self.assertRaises(ProtectedError):
                self.sita.delete()
            with self.assertRaises(ProtectedError):
                PayrollRun.objects.get(pk=run.pk).delete()

    def test_two_approvals_at_once_make_one_approval(self):
        self.staff_with_salary()
        run = self.calculated()
        barrier = threading.Barrier(2)
        results, errors = [], []

        def go(user):
            try:
                with schema_context(self.SCHEMA_A):
                    barrier.wait(timeout=30)
                    services.approve_run(PayrollRun.objects.get(pk=run.pk), user_id=user.id)
                    results.append("ok")
            except serializers.ValidationError:
                results.append("refused")
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        # The clock is patched once, here, not inside the threads: patching it from two threads at the
        # same time can leave the patch in place afterwards.
        with mock.patch("payroll.services.timezone.localdate", return_value=AFTER_FEB):
            threads = [threading.Thread(target=go, args=(u,)) for u in (self.approver, self.owner)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=90)
        self.assertEqual(errors, [])
        self.assertEqual((results.count("ok"), results.count("refused")), (1, 1))

    def test_two_calculations_at_once_leave_one_set_of_payslips(self):
        self.staff_with_salary()
        self.staff_with_salary(self.ram, "20000")
        run = self.new_run()
        barrier = threading.Barrier(3)
        errors = []

        def go():
            try:
                with schema_context(self.SCHEMA_A):
                    barrier.wait(timeout=30)
                    services.calculate_run(PayrollRun.objects.get(pk=run.pk), user_id=self.owner.id)
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=go) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)
        self.assertEqual(errors, [])
        with tenant_context(self.school):
            self.assertEqual(Payslip.objects.filter(run=run).count(), 2)
            self.assertEqual(PayslipLine.objects.filter(payslip__run=run, code="BASIC").count(), 2)


class RunApiTests(RunFixture):
    def setUp(self):
        super().setUp()
        self.viewer = self._user("viewer2", self.school, codenames=["view_payroll"])
        self.payer = self._user("payer", self.school, codenames=["view_payroll", "record_payroll_payment"])
        self.staffer = self._user("staffer2", self.school, role_slug="staff")

    def api(self, user, method, path, data=None, today=None, host=None):
        if today is not None:
            with mock.patch("payroll.services.timezone.localdate", return_value=today):
                return self._call(user, method, path, data, host=host)
        return self._call(user, method, path, data, host=host)

    def made(self):
        self.staff_with_salary()
        run_id = self.api(self.manager, "post", "runs/", {"year": 2026, "month": 2}).data["id"]
        self.api(self.manager, "post", f"runs/{run_id}/calculate/")
        return run_id

    def test_the_new_permissions_exist_and_only_the_owner_holds_them(self):
        from roles.constants import SYSTEM_PERMISSIONS
        from roles.models import Role
        names = {"run_payroll", "approve_payroll", "record_payroll_payment"}
        self.assertTrue(names <= {p["codename"] for p in SYSTEM_PERMISSIONS})
        with tenant_context(self.school):
            self.assertTrue(names <= set(Role.objects.get(slug="owner").permissions.values_list("codename", flat=True)))
            for slug in ("staff", "instructor", "student", "parent"):
                self.assertFalse(names & set(Role.objects.get(slug=slug).permissions.values_list("codename", flat=True)), slug)

    def test_permissions_for_every_action(self):
        run_id = self.made()
        slip_id = self.api(self.viewer, "get", f"runs/{run_id}/payslips/").data["results"][0]["id"]
        for method, path, data, allowed, denied in [
            ("get", "runs/", None, self.viewer, self.staffer),
            ("get", f"runs/{run_id}/", None, self.viewer, self.staffer),
            ("get", f"runs/{run_id}/payslips/", None, self.viewer, self.staffer),
            ("get", f"payslips/{slip_id}/", None, self.viewer, self.staffer),
            ("get", f"runs/{run_id}/adjustments/", None, self.viewer, self.staffer),
            ("post", "runs/", {"year": 2026, "month": 1}, self.manager, self.viewer),
            ("post", f"runs/{run_id}/calculate/", None, self.manager, self.viewer),
            ("post", "adjustments/", {"run": run_id, "staff": str(self.sita.id), "kind": "earning", "name": "B", "amount": "10", "reason": "r"}, self.manager, self.viewer),
        ]:
            with self.subTest(path=path, method=method):
                self.assertEqual(self.api(denied, method, path, data).status_code, 403)
                self.assertIn(self.api(None, method, path, data).status_code, (401, 403))
                self.assertIn(self.api(allowed, method, path, data).status_code, (200, 201))
        # approving and paying
        self.assertEqual(self.api(self.manager, "post", f"runs/{run_id}/approve/", today=AFTER_FEB).status_code, 403)
        self.assertEqual(self.api(self.approver, "post", f"runs/{run_id}/approve/", today=AFTER_FEB).status_code, 200)
        pay = {"paid_on": "2026-03-03", "method": "cash"}
        self.assertEqual(self.api(self.approver, "post", f"runs/{run_id}/pay/", pay, today=AFTER_FEB).status_code, 403)
        self.assertEqual(self.api(self.payer, "post", f"runs/{run_id}/pay/", pay, today=AFTER_FEB).status_code, 200)

    def test_run_details_totals_and_payslip_lines(self):
        self.staff_with_salary()
        self.give(self.pf)
        self.staff_with_salary(self.ram, "20000")
        run_id = self.api(self.manager, "post", "runs/", {"year": 2026, "month": 2, "notes": "Feb"}).data["id"]
        run = self.api(self.manager, "post", f"runs/{run_id}/calculate/").data
        self.assertEqual((run["status"], run["month_label"], run["payslip_count"], run["working_days"]), ("calculated", "February 2026", 2, 24))
        self.assertEqual((run["total_gross"], run["total_deductions"], run["total_net"]), ("44000.00", "2400.00", "41600.00"))
        listing = self.api(self.viewer, "get", "runs/").data["results"]
        self.assertEqual((listing[0]["total_net"], listing[0]["payslip_count"]), ("41600.00", 2))
        slips = self.api(self.viewer, "get", f"runs/{run_id}/payslips/").data["results"]
        self.assertEqual([s["employee_id"] for s in slips], ["E-P-2", "E-P-1"])      # by name: Ram, Sita
        detail = self.api(self.viewer, "get", f"payslips/{[s for s in slips if s['employee_id'] == 'E-P-1'][0]['id']}/").data
        self.assertEqual([(l["code"], l["amount"]) for l in detail["lines"]], [("BASIC", "24000.00"), ("PF", "2400.00")])
        self.assertEqual((detail["net_amount"], detail["month_label"]), ("21600.00", "February 2026"))

    def test_filters_and_the_problems_view(self):
        self.staff_with_salary()
        self.staff_with_salary(self.ram, "20000")
        for n in range(2, 8):
            self.mark(self.ram, n, "present")       # Ram has marked days; Sita has none: both have unmarked days
        run_id = self.api(self.manager, "post", "runs/", {"year": 2026, "month": 2}).data["id"]
        self.api(self.manager, "post", f"runs/{run_id}/calculate/")
        self.assertEqual(self.api(self.viewer, "get", f"runs/{run_id}/payslips/?search=sita").data["count"], 1)
        self.assertEqual(self.api(self.viewer, "get", f"runs/{run_id}/payslips/?problems=true").data["count"], 2)
        self.assertEqual(self.api(self.viewer, "get", "runs/?status=draft").data["count"], 0)
        self.assertEqual(self.api(self.viewer, "get", "runs/?status=calculated&year=2026").data["count"], 1)

    def test_bad_input_is_a_clean_400(self):
        for body in ({}, {"year": 2026}, {"year": "x", "month": 2}, {"year": 2026, "month": 13}, {"year": 1900, "month": 1}, []):
            self.assertEqual(self.api(self.manager, "post", "runs/", body).status_code, 400, body)
        run_id = self.made()
        for user, path, body in [(self.manager, "cancel/", {}), (self.manager, "cancel/", {"reason": ""}),
                                 (self.payer, "pay/", {}), (self.payer, "pay/", {"paid_on": "x", "method": "cash"}),
                                 (self.payer, "pay/", {"paid_on": "2026-03-03", "method": "cash"})]:   # not approved yet
            self.assertEqual(self.api(user, "post", f"runs/{run_id}/{path}", body, today=AFTER_FEB).status_code, 400, (path, body))
        adjustment = {"run": run_id, "staff": str(self.sita.id), "kind": "earning", "name": "B", "amount": "10", "reason": "r"}
        for patch in ({"amount": "0"}, {"amount": "-1"}, {"amount": "abc"}, {"kind": "tip"}, {"reason": ""}, {"staff": "nope"}, {"run": "nope"}):
            self.assertEqual(self.api(self.manager, "post", "adjustments/", {**adjustment, **patch}).status_code, 400, patch)
        self.assertEqual(self.api(self.viewer, "get", f"runs/{run_id}/payslips/?search=").status_code, 200)

    def test_runs_and_payslips_cannot_be_edited_or_deleted_through_the_api(self):
        run_id = self.made()
        slip_id = self.api(self.viewer, "get", f"runs/{run_id}/payslips/").data["results"][0]["id"]
        for method in ("put", "patch", "delete"):
            self.assertEqual(self.api(self.owner, method, f"runs/{run_id}/", {}).status_code, 405, method)
            self.assertEqual(self.api(self.owner, method, f"payslips/{slip_id}/", {}).status_code, 405, method)
        self.assertEqual(self.api(self.owner, "post", "payslips/", {}).status_code, 405)   # the list exists, creating is not allowed

    def test_adjustments_end_to_end(self):
        run_id = self.made()
        body = {"run": run_id, "staff": str(self.sita.id), "kind": "deduction", "name": "Advance", "amount": "1500.50", "reason": "Loan"}
        created = self.api(self.manager, "post", "adjustments/", body)
        self.assertEqual((created.status_code, created.data["amount"], created.data["employee_id"]), (201, "1500.50", "E-P-1"))
        self.assertEqual(self.api(self.viewer, "get", f"runs/{run_id}/adjustments/").data["count"], 1)
        self.assertEqual(self.api(self.viewer, "delete", f"adjustments/{created.data['id']}/").status_code, 403)
        self.assertEqual(self.api(self.manager, "delete", f"adjustments/{created.data['id']}/").status_code, 204)
        self.assertEqual(self.api(self.manager, "delete", f"adjustments/{created.data['id']}/").status_code, 404)
        self.api(self.approver, "post", f"runs/{run_id}/approve/", today=AFTER_FEB)
        self.assertEqual(self.api(self.manager, "post", "adjustments/", body).status_code, 400)     # locked

    def test_cancelling_an_approved_run_needs_both_run_and_approve_permissions(self):
        both = self._user("both", self.school, codenames=["view_payroll", "run_payroll", "approve_payroll"])
        run_id = self.made()
        self.api(self.approver, "post", f"runs/{run_id}/approve/", today=AFTER_FEB)
        body = {"reason": "Attendance was wrong"}
        self.assertEqual(self.api(self.manager, "post", f"runs/{run_id}/cancel/", body).status_code, 403)    # run only
        self.assertEqual(self.api(self.approver, "post", f"runs/{run_id}/cancel/", body).status_code, 403)   # approve only
        done = self.api(both, "post", f"runs/{run_id}/cancel/", body)
        self.assertEqual((done.status_code, done.data["status"]), (200, "cancelled"))

    def test_every_step_is_audit_logged(self):
        run_id = self.made()
        self.api(self.approver, "post", f"runs/{run_id}/approve/", today=AFTER_FEB)
        self.api(self.payer, "post", f"runs/{run_id}/pay/", {"paid_on": "2026-03-03", "method": "bank_transfer"}, today=AFTER_FEB)
        with tenant_context(self.school):
            actions = list(AuditLog.objects.filter(model_name="PayrollRun").order_by("created_at").values_list("action", flat=True))
            self.assertEqual(actions, ["payroll_run_created", "payroll_run_calculated", "payroll_run_approved", "payroll_run_paid"])
            self.assertEqual(AuditLog.objects.get(action="payroll_run_approved").actor_id, self.approver.id)

    def test_schools_cannot_see_each_others_payroll(self):
        run_id = self.made()
        user_b = self._user("owner_b2", self.school_b, role_slug="owner")
        self.assertEqual(self.api(user_b, "get", "runs/", host=self.DOMAIN_B).data["results"], [])
        self.assertEqual(self.api(user_b, "get", f"runs/{run_id}/", host=self.DOMAIN_B).status_code, 404)
        self.assertEqual(self.api(user_b, "post", f"runs/{run_id}/calculate/", host=self.DOMAIN_B).status_code, 404)
        self.assertEqual(self.api(user_b, "get", "runs/", host=self.DOMAIN_A).status_code, 403)
