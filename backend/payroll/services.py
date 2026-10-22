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
