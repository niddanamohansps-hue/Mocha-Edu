"""Payroll rules for the salary structure (Stage P1).

Every change locks the staff member's row first, so two people cannot (for example) both give the same
person the same allowance at once. History is never edited: a raise is a new ``StaffSalary`` row and
ending a component sets its end date.

Money is ``Decimal`` all the way. ``compute_structure`` is a pure function of the stored data and is what
the monthly payroll run (Stage P2) will build on.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from rest_framework import serializers

from staff.models import StaffMember

from .models import PayrollSettings, SalaryComponent, StaffSalary, StaffSalaryComponent

Kind = SalaryComponent.Kind
Calc = SalaryComponent.Calculation

MONEY_STEP = Decimal("0.01")
WHOLE = Decimal("1")
MAX_MONEY = Decimal("9999999999.99")


def round_money(amount, *, whole):
    """Round half up: to the whole rupee, or to the paisa."""
    return Decimal(amount).quantize(WHOLE if whole else MONEY_STEP, rounding=ROUND_HALF_UP)


def _locked_staff(staff):
    return StaffMember.objects.select_for_update().get(pk=staff.pk)


def validate_component_value(calculation, value):
    """A fixed amount has at most 2 decimals; a percentage is 0-100 with at most 3."""
    if value is None:
        return
    if value < 0:
        raise serializers.ValidationError({"value": "The value cannot be negative."})
    if calculation == Calc.PERCENT_OF_BASIC:
        if value > 100:
            raise serializers.ValidationError({"value": "A percentage cannot be above 100."})
    else:
        if value != value.quantize(MONEY_STEP):
            raise serializers.ValidationError({"value": "A fixed amount can have at most 2 decimal places."})
        if value > MAX_MONEY:
            raise serializers.ValidationError({"value": "The amount is too large."})


# --- Salary -------------------------------------------------------------------------------------------

def set_salary(*, staff, basic_amount, effective_from, note="", user_id=None):
    """Give ``staff`` a new basic salary from ``effective_from`` (a new row; earlier ones stay)."""
    if basic_amount is None or basic_amount <= 0:
        raise serializers.ValidationError({"basic_amount": "The salary must be above 0."})
    if basic_amount != basic_amount.quantize(MONEY_STEP) or basic_amount > MAX_MONEY:
        raise serializers.ValidationError({"basic_amount": "Use at most 2 decimal places and a realistic amount."})
    with transaction.atomic():
        locked = _locked_staff(staff)
        if not locked.is_active:
            raise serializers.ValidationError({"staff": "This staff member is not active."})
        try:
            with transaction.atomic():
                return StaffSalary.objects.create(
                    staff=locked, basic_amount=basic_amount, effective_from=effective_from,
                    note=(note or "")[:255], created_by_user_id=user_id,
                )
        except IntegrityError:
            raise serializers.ValidationError(
                {"effective_from": "A salary is already set from this date. Choose a later date."}
            )


def salary_on(staff, on_date):
    """The salary row in force for ``staff`` on ``on_date``, or None."""
    return StaffSalary.objects.filter(staff=staff, effective_from__lte=on_date).order_by("-effective_from").first()


# --- Components ---------------------------------------------------------------------------------------

def assign_component(*, staff, component, effective_from, value=None, user_id=None):
    """Give ``staff`` a component from ``effective_from``. ``value`` overrides the component's default."""
    if not component.is_active:
        raise serializers.ValidationError({"component": "This component is inactive."})
    validate_component_value(component.calculation, value)
    with transaction.atomic():
        locked = _locked_staff(staff)
        if not locked.is_active:
            raise serializers.ValidationError({"staff": "This staff member is not active."})
        if StaffSalaryComponent.objects.filter(staff=locked, component=component, effective_to__isnull=True).exists():
            raise serializers.ValidationError({"component": "This staff member already has this component. End it first."})
        try:
            with transaction.atomic():
                return StaffSalaryComponent.objects.create(
                    staff=locked, component=component, value=value, effective_from=effective_from, created_by_user_id=user_id
                )
        except IntegrityError:
            raise serializers.ValidationError({"component": "This staff member already has this component. End it first."})


def end_component(assignment, *, effective_to, user_id=None):
    """Stop a component after ``effective_to`` (the record stays, so past pay is explainable)."""
    with transaction.atomic():
        _locked_staff(assignment.staff)
        current = StaffSalaryComponent.objects.select_for_update().get(pk=assignment.pk)
        if current.effective_to is not None:
            raise serializers.ValidationError({"component": "This component has already ended."})
        if effective_to < current.effective_from:
            raise serializers.ValidationError({"effective_to": "The end date cannot be before the start date."})
        current.effective_to = effective_to
        current.save(update_fields=["effective_to"])
    return current


# --- The structure -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Line:
    code: str
    name: str
    kind: str  # "basic", "earning" or "deduction"
    amount: Decimal
    detail: str = ""


@dataclass
class Structure:
    staff_id: object
    on_date: date
    basic: Decimal
    lines: list = field(default_factory=list)
    gross: Decimal = Decimal("0")
    deductions: Decimal = Decimal("0")
    net: Decimal = Decimal("0")
    rounded_to_whole_rupee: bool = True

    @property
    def net_is_negative(self):
        return self.net < 0


def compute_structure(staff, on_date, *, settings=None):
    """What ``staff`` is paid for one full month in force on ``on_date``: basic, earnings, deductions, net.

    Percentages apply to the basic salary. Each line is rounded as the school's settings say (whole rupee
    by default), then the totals are the sums of the rounded lines, so the lines always add up exactly.
    Components that are inactive are left out. Returns None when no salary is set yet.
    """
    salary = salary_on(staff, on_date)
    if salary is None:
        return None
    settings = settings or PayrollSettings.load()
    whole = settings.round_to_whole_rupee
    basic = round_money(salary.basic_amount, whole=whole)
    lines = [Line("BASIC", "Basic salary", "basic", basic)]
    assignments = (
        StaffSalaryComponent.objects.filter(staff=staff, effective_from__lte=on_date, component__is_active=True)
        .exclude(effective_to__lt=on_date)
        .select_related("component")
        .order_by("component__kind", "component__sort_order", "component__name")
    )
    for assignment in assignments:
        component = assignment.component
        value = assignment.value if assignment.value is not None else component.default_value
        if component.calculation == Calc.PERCENT_OF_BASIC:
            amount = round_money(salary.basic_amount * value / Decimal("100"), whole=whole)
            detail = f"{value.normalize():f}% of basic"
        else:
            amount = round_money(value, whole=whole)
            detail = "fixed"
        lines.append(Line(component.code, component.name, component.kind, amount, detail))
    gross = sum((l.amount for l in lines if l.kind in ("basic", Kind.EARNING)), Decimal("0"))
    deductions = sum((l.amount for l in lines if l.kind == Kind.DEDUCTION), Decimal("0"))
    return Structure(
        staff_id=staff.pk, on_date=on_date, basic=basic, lines=lines, gross=gross, deductions=deductions,
        net=gross - deductions, rounded_to_whole_rupee=whole,
    )


# =============================================================================================
# Monthly payroll runs (Stage P2)
# =============================================================================================
#
# What a run does, in plain words:
#   * pay for a month = the salary structure in force on the LAST day of the month;
#   * unpaid days = approved unpaid leave + days marked absent (half day counts half) + working days
#     before the person's joining date; a day is never counted twice;
#   * deduction for unpaid days = basic salary / working days in the month x unpaid days (basic only);
#   * working days = days that are not the school's weekly off days and not published holidays;
#   * working days with no attendance record are paid, and counted as "unmarked" so they can be reviewed.

import calendar
import logging
from datetime import timedelta

from django.utils import timezone

from .models import Payslip, PayslipLine, PayrollAdjustment, PayrollRun

logger = logging.getLogger(__name__)

RunStatus = PayrollRun.Status
LineKind = PayslipLine.Kind
HALF = Decimal("0.5")
ONE = Decimal("1")
MIN_YEAR, MAX_YEAR = 2000, 2200


def month_bounds(year, month):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def working_dates(start, end):
    """The school's working days between two dates: not a weekly off day and not a published holiday."""
    from academics.models import CalendarEvent
    from attendance.models import AttendanceSettings

    weekly_off = AttendanceSettings.weekly_off()
    holidays = set()
    for event in CalendarEvent.objects.filter(
        is_holiday=True, status="PUBLISHED", start_date__lte=end, end_date__gte=start
    ):
        day, last = max(start, event.start_date), min(end, event.end_date)
        while day <= last:
            holidays.add(day)
            day += timedelta(days=1)
    result, day = [], start
    while day <= end:
        if day.weekday() not in weekly_off and day not in holidays:
            result.append(day)
        day += timedelta(days=1)
    return result


def _locked_run(run):
    return PayrollRun.objects.select_for_update().get(pk=run.pk)


def _require_status(run, allowed, action):
    if run.status not in allowed:
        raise serializers.ValidationError({"status": f"A {run.get_status_display().lower()} payroll run cannot be {action}."})


def create_run(*, year, month, notes="", user_id=None):
    if not (MIN_YEAR <= year <= MAX_YEAR) or not 1 <= month <= 12:
        raise serializers.ValidationError({"month": "Choose a real year and month."})
    start, end = month_bounds(year, month)
    if start > timezone.localdate():
        raise serializers.ValidationError({"month": "Payroll cannot be run for a month that has not started."})
    try:
        with transaction.atomic():
            return PayrollRun.objects.create(
                year=year, month=month, period_start=start, period_end=end, notes=(notes or "")[:255],
                created_by_user_id=user_id, prepared_by_user_id=user_id,
            )
    except IntegrityError:
        raise serializers.ValidationError({"month": "There is already a payroll run for this month. Cancel it first to start again."})


def _unpaid_days(staff, period_start, work_set, leaves, attendance):
    """Return ``(unpaid_days, unmarked_days)`` for one person. ``work_set`` is the month's working dates."""
    unpaid = {}

    def mark(day, fraction):
        if day in work_set and unpaid.get(day, Decimal("0")) < fraction:
            unpaid[day] = fraction

    if staff.joining_date and staff.joining_date > period_start:
        for day in work_set:
            if day < staff.joining_date:
                mark(day, ONE)
    if work_set:
        first, last = min(work_set), max(work_set)
        for application in leaves:
            day = max(application.start_date, first)
            while day <= min(application.end_date, last):
                mark(day, HALF if application.is_half_day else ONE)
                day += timedelta(days=1)
    records = attendance.get(staff.pk, {})
    for day, status_value in records.items():
        if status_value == "absent":
            mark(day, ONE)
        elif status_value == "half_day":
            mark(day, HALF)
    unmarked = sum(1 for day in work_set if day not in records and day not in unpaid)
    return sum(unpaid.values(), Decimal("0")), Decimal(unmarked)


def _gather_month(run, work_set):
    """One query each for the month's unpaid leave and attendance, grouped by person."""
    from attendance.models import StaffAttendance
    from staff.models import LeaveApplication

    leaves = {}
    for application in LeaveApplication.objects.filter(
        status="approved", leave_type__is_paid=False, start_date__lte=run.period_end, end_date__gte=run.period_start
    ):
        leaves.setdefault(application.staff_id, []).append(application)
    attendance = {}
    for record in StaffAttendance.objects.filter(date__gte=run.period_start, date__lte=run.period_end):
        attendance.setdefault(record.staff_id, {})[record.date] = record.status
    return leaves, attendance


class _Rounding:
    def __init__(self, whole):
        self.round_to_whole_rupee = whole


def _build_payslip(run, staff, work_set, leaves, attendance, adjustments):
    """Create the payslip and its lines for one person, or return None when they have no salary."""
    whole = run.round_to_whole_rupee
    structure = compute_structure(staff, run.period_end, settings=_Rounding(whole))
    if structure is None:
        return None
    salary = salary_on(staff, run.period_end)
    working = len(work_set)
    unpaid_days, unmarked = _unpaid_days(staff, run.period_start, work_set, leaves, attendance)
    lines = [
        (l.code, l.name, l.kind, l.amount, l.detail, "structure") for l in structure.lines
    ]
    if unpaid_days > 0 and working > 0:
        # basic / working days x unpaid days, from the unrounded basic, never more than the basic itself
        raw = salary.basic_amount / Decimal(working) * unpaid_days
        amount = min(round_money(raw, whole=whole), structure.basic)
        lines.append(("UNPAID", "Unpaid days", Kind.DEDUCTION, amount, f"{unpaid_days.normalize():f} of {working} working days", "unpaid"))
    for adjustment in adjustments:
        lines.append((
            "ADJ", adjustment.name, adjustment.kind, round_money(adjustment.amount, whole=whole),
            adjustment.reason, "adjustment",
        ))
    earnings = sum((l[3] for l in lines if l[2] in ("basic", Kind.EARNING)), Decimal("0"))
    deductions = sum((l[3] for l in lines if l[2] == Kind.DEDUCTION), Decimal("0"))
    profile = staff.profile
    payslip = Payslip.objects.create(
        run=run, staff=staff, employee_id=staff.employee_id,
        staff_name=f"{profile.first_name} {profile.last_name}".strip(), designation=staff.designation,
        department=staff.department, basic_amount=structure.basic, gross_amount=earnings,
        deductions_amount=deductions, net_amount=earnings - deductions, working_days=working,
        unpaid_days=unpaid_days, unmarked_days=unmarked,
    )
    PayslipLine.objects.bulk_create([
        PayslipLine(payslip=payslip, code=code, name=name, kind=kind, amount=amount, detail=detail[:255], sort_order=index)
        for index, (code, name, kind, amount, detail, _source) in enumerate(lines)
    ])
    return payslip


def calculate_run(run, *, user_id=None):
    """(Re)build every payslip of the run from the current salaries, attendance, leave and adjustments.

    Allowed until the run is approved; each call replaces the payslips of the previous one. Returns the
    run with ``calculation_notes`` saying who was left out and why.
    """
    with transaction.atomic():
        run = _locked_run(run)
        _require_status(run, (RunStatus.DRAFT, RunStatus.CALCULATED), "calculated")
        pay_settings = PayrollSettings.load()
        from attendance.models import AttendanceSettings

        work = working_dates(run.period_start, run.period_end)
        if not work:
            raise serializers.ValidationError(
                {"month": "This month has no working days (every day is a weekly off day or a holiday)."}
            )
        work_set = set(work)
        run.working_days = len(work)
        run.weekly_off_days = sorted(AttendanceSettings.weekly_off())
        run.round_to_whole_rupee = pay_settings.round_to_whole_rupee
        leaves, attendance = _gather_month(run, work_set)

        run.payslips.all().delete()  # allowed: the run is not locked
        adjustments = {}
        for adjustment in run.adjustments.all():
            adjustments.setdefault(adjustment.staff_id, []).append(adjustment)

        no_salary, inactive, made = [], 0, 0
        for staff in StaffMember.objects.select_related("profile").order_by("employee_id"):
            if not staff.is_active:
                inactive += 1
                continue
            payslip = _build_payslip(run, staff, work_set, leaves.get(staff.pk, []), attendance, adjustments.get(staff.pk, []))
            if payslip is None:
                no_salary.append(staff.employee_id)
            else:
                made += 1
        negative = run.payslips.filter(net_amount__lt=0).count()
        run.calculation_notes = {
            "payslips": made, "skipped_no_salary": no_salary, "skipped_inactive": inactive, "negative_net": negative,
            "unmarked_staff": run.payslips.filter(unmarked_days__gt=0).count(),
        }
        run.status = RunStatus.CALCULATED
        run.calculated_at = timezone.now()
        run.prepared_by_user_id = user_id
        run.save()
    return run


def add_adjustment(run, *, staff, kind, name, amount, reason, user_id=None):
    """Add a one-off line for one person and refresh their payslip if the run is already calculated."""
    name, reason = (name or "").strip(), (reason or "").strip()
    if not name or not reason:
        raise serializers.ValidationError({"reason": "Give the adjustment a name and a reason."})
    if kind not in (Kind.EARNING, Kind.DEDUCTION):
        raise serializers.ValidationError({"kind": "Choose earning or deduction."})
    if amount is None or amount <= 0 or amount != amount.quantize(MONEY_STEP) or amount > MAX_MONEY:
        raise serializers.ValidationError({"amount": "Use an amount above 0 with at most 2 decimal places."})
    with transaction.atomic():
        run = _locked_run(run)
        _require_status(run, (RunStatus.DRAFT, RunStatus.CALCULATED), "adjusted")
        if not staff.is_active:
            raise serializers.ValidationError({"staff": "This staff member is not active."})
        adjustment = PayrollAdjustment.objects.create(
            run=run, staff=staff, kind=kind, name=name[:100], amount=amount, reason=reason[:255], created_by_user_id=user_id
        )
        if run.status == RunStatus.CALCULATED:
            _refresh_payslip(run, staff)
    return adjustment


def remove_adjustment(adjustment, *, user_id=None):
    with transaction.atomic():
        run = _locked_run(adjustment.run)
        _require_status(run, (RunStatus.DRAFT, RunStatus.CALCULATED), "adjusted")
        staff = adjustment.staff
        PayrollAdjustment.objects.get(pk=adjustment.pk).delete()
        if run.status == RunStatus.CALCULATED:
            _refresh_payslip(run, staff)


def _refresh_payslip(run, staff):
    """Rebuild one person's payslip after an adjustment (the rest of the run is left as it is)."""
    work_set = set(working_dates(run.period_start, run.period_end))
    leaves, attendance = _gather_month(run, work_set)
    Payslip.objects.filter(run=run, staff=staff).delete()
    adjustments = list(run.adjustments.filter(staff=staff))
    _build_payslip(run, staff, work_set, [a for a in leaves.get(staff.pk, [])], attendance, adjustments)
    negative = run.payslips.filter(net_amount__lt=0).count()
    run.calculation_notes = {**run.calculation_notes, "negative_net": negative}
    run.save(update_fields=["calculation_notes", "updated_at"])


def approve_run(run, *, user_id):
    """Lock a calculated run. Needs at least one payslip, no negative pay, a finished month and (by
    default) someone other than whoever prepared it."""
    with transaction.atomic():
        run = _locked_run(run)
        _require_status(run, (RunStatus.CALCULATED,), "approved")
        if run.period_end >= timezone.localdate():
            raise serializers.ValidationError({"month": "The month has not finished yet. Approve after its last day."})
        if not run.payslips.exists():
            raise serializers.ValidationError({"payslips": "There are no payslips to approve."})
        if run.payslips.filter(net_amount__lt=0).exists():
            raise serializers.ValidationError({"payslips": "Some pay is below zero. Fix it with adjustments or salary changes and calculate again."})
        if PayrollSettings.load().require_separate_approver and user_id is not None and user_id == run.prepared_by_user_id:
            raise serializers.ValidationError({"approver": "A different person must approve this run: you prepared it."})
        run.status = RunStatus.APPROVED
        run.approved_by_user_id = user_id
        run.approved_at = timezone.now()
        run.save(update_fields=["status", "approved_by_user_id", "approved_at", "updated_at"])
        # Tell the staff once the approval is really saved; a failure to notify never undoes it.
        transaction.on_commit(lambda: notify_payslips_ready(run))
    return run


def record_payment(run, *, user_id, paid_on, method, reference=""):
    with transaction.atomic():
        run = _locked_run(run)
        _require_status(run, (RunStatus.APPROVED,), "marked paid")
        if method not in PayrollRun.Method.values:
            raise serializers.ValidationError({"method": "Choose a payment method."})
        if paid_on > timezone.localdate():
            raise serializers.ValidationError({"paid_on": "The payment date cannot be in the future."})
        if paid_on < run.period_end:
            raise serializers.ValidationError({"paid_on": "The payment date cannot be before the month ended."})
        run.status = RunStatus.PAID
        run.paid_on = paid_on
        run.paid_by_user_id = user_id
        run.payment_method = method
        run.payment_reference = (reference or "")[:100]
        run.save(update_fields=["status", "paid_on", "paid_by_user_id", "payment_method", "payment_reference", "updated_at"])
    return run


def cancel_run(run, *, reason, user_id=None):
    """Cancel a run that has not been paid. Its payslips stay as a record; a new run can then be made."""
    reason = (reason or "").strip()
    if not reason:
        raise serializers.ValidationError({"reason": "A reason is required."})
    with transaction.atomic():
        run = _locked_run(run)
        _require_status(run, (RunStatus.DRAFT, RunStatus.CALCULATED, RunStatus.APPROVED), "cancelled")
        run.status = RunStatus.CANCELLED
        run.cancelled_at = timezone.now()
        run.cancelled_by_user_id = user_id
        run.cancellation_reason = reason[:255]
        run.save(update_fields=["status", "cancelled_at", "cancelled_by_user_id", "cancellation_reason", "updated_at"])
    return run


def notify_payslips_ready(run):
    """Tell each staff member in an approved run, in the app, that their payslip is ready. Best effort:
    a failure here is logged and never undoes the approval."""
    try:
        from notifications.services import notify_many
        from profiles.models import Profile

        staff_ids = list(run.payslips.values_list("staff_id", flat=True))
        user_ids = list(
            Profile.objects.filter(staff_record__in=staff_ids, user_id__isnull=False).values_list("user_id", flat=True).distinct()
        )
        if user_ids:
            from .run_serializers import MONTH_NAMES

            notify_many(
                recipient_user_ids=user_ids, title=f"Your payslip for {MONTH_NAMES[run.month]} {run.year} is ready",
                body="Open My payslips to see it or download it as a PDF.", category="payroll",
                link="/dashboard/payroll/my-payslips",
            )
    except Exception:
        logger.exception("Could not send the payslip-ready notices for payroll run %s.", run.pk)

