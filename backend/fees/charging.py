"""
Charging a fee structure to every student in its class, split into instalments,
with each student's concessions applied as a discount.

Each instalment becomes an ordinary StudentFee, so dues, reminders, online
payment and receipts need no changes. Running a charge again is safe: a student
who already has a given instalment (or the whole structure, when it has no
instalments) is skipped.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from rest_framework import serializers

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def _money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def validate_installment_plan(installments):
    """installments: iterable of dicts with name, percent, due_date."""
    rows = list(installments)
    if not rows:
        return rows
    names = [r["name"].strip().lower() for r in rows]
    if len(set(names)) != len(names):
        raise serializers.ValidationError("Each instalment needs a different name.")
    total = sum((Decimal(r["percent"]) for r in rows), Decimal("0"))
    if total != HUNDRED:
        raise serializers.ValidationError(f"The instalments must add up to 100%; they add up to {total.quantize(CENT).normalize():f}%.")
    dates = [r["due_date"] for r in rows]
    if dates != sorted(dates):
        raise serializers.ValidationError("Put the instalments in order of due date.")
    return rows


def split(amount, percents):
    """Split amount by percents to the paisa; the rounding remainder goes on the last part,
    so the parts always add up to the amount exactly."""
    amount = _money(amount)
    parts = [_money(amount * Decimal(p) / HUNDRED) for p in percents[:-1]]
    parts.append(amount - sum(parts, Decimal("0")))
    return parts


@dataclass
class Line:
    installment: object  # FeeInstallment or None for a structure without instalments
    name: str
    amount: Decimal
    due_date: object


def structure_lines(structure):
    installments = list(structure.installments.all())
    if not installments:
        return [Line(None, structure.fee_head.name, _money(structure.amount), structure.due_date)]
    amounts = split(structure.amount, [i.percent for i in installments])
    return [Line(i, i.name, a, i.due_date) for i, a in zip(installments, amounts)]


def concession_discounts(concessions, lines):
    """Discount for each line. A percentage applies to every line; a fixed amount is spread
    over the lines in proportion to their size. The discount never exceeds a line's amount."""
    discounts = [Decimal("0")] * len(lines)
    total = sum((line.amount for line in lines), Decimal("0"))
    for concession in concessions:
        ctype = concession.concession_type
        if ctype.kind == "percent":
            extra = [_money(line.amount * ctype.value / HUNDRED) for line in lines]
        else:
            fixed = min(_money(ctype.value), total)
            extra = split(fixed, [line.amount * HUNDRED / total for line in lines]) if total else [Decimal("0")] * len(lines)
        discounts = [d + e for d, e in zip(discounts, extra)]
    return [min(d, line.amount) for d, line in zip(discounts, lines)]


def target_enrollments(structure):
    from students.models import StudentLevel

    qs = StudentLevel.objects.filter(
        is_current=True, academic_year=structure.academic_year, student__status="active"
    ).select_related("student__profile", "level", "section")
    if structure.level_id:
        qs = qs.filter(level_id=structure.level_id)
    if structure.section_id:
        qs = qs.filter(section_id=structure.section_id)
    return qs.order_by("student__profile__first_name", "student__profile__last_name")


@dataclass
class ChargePlan:
    lines: list
    students: list = field(default_factory=list)  # dicts for preview
    to_create: list = field(default_factory=list)  # (enrollment, line, discount, reason)

    def summary(self):
        charged = [s for s in self.students if s["new_fees"]]
        return {
            "installments": [
                {"name": line.name, "amount": str(line.amount), "due_date": line.due_date} for line in self.lines
            ],
            "students_total": len(self.students),
            "students_to_charge": len(charged),
            "students_already_charged": len(self.students) - len(charged),
            "fees_to_create": len(self.to_create),
            "amount_to_charge": str(sum((line.amount - d for _, line, d, _ in self.to_create), Decimal("0"))),
            "concession_total": str(sum((d for _, _, d, _ in self.to_create), Decimal("0"))),
            "students": self.students,
        }


def plan_charge(structure, enrollments=None):
    """enrollments: who to charge (StudentLevel rows); default = the structure's class."""
    from .models import StudentConcession, StudentFee

    if not structure.is_active:
        raise serializers.ValidationError("This fee structure is switched off.")
    lines = structure_lines(structure)
    if lines[0].amount <= 0 and len(lines) == 1:
        raise serializers.ValidationError("This fee structure has no amount.")

    enrollments = list(target_enrollments(structure) if enrollments is None else enrollments)
    student_ids = [e.student_id for e in enrollments]
    existing = set(
        StudentFee.objects.filter(
            fee_structure=structure, student_id__in=student_ids, status="active"
        ).values_list("student_id", "installment_id")
    )
    concessions = {}
    for c in StudentConcession.objects.filter(
        student_id__in=student_ids, academic_year=structure.academic_year, is_active=True,
        concession_type__is_active=True,
    ).select_related("concession_type"):
        if c.concession_type.fee_head_id in (None, structure.fee_head_id):
            concessions.setdefault(c.student_id, []).append(c)

    plan = ChargePlan(lines=lines)
    for enrollment in enrollments:
        mine = concessions.get(enrollment.student_id, [])
        discounts = concession_discounts(mine, lines)
        reason = ", ".join(c.concession_type.name for c in mine)
        new = 0
        for line, discount in zip(lines, discounts):
            key = (enrollment.student_id, line.installment.id if line.installment else None)
            if key in existing:
                continue
            plan.to_create.append((enrollment, line, discount, reason))
            new += 1
        profile = enrollment.student.profile
        plan.students.append({
            "student": str(enrollment.student_id),
            "name": f"{profile.first_name} {profile.last_name}".strip(),
            "section": enrollment.section.name if enrollment.section_id else "",
            "concessions": reason,
            "discount": str(sum(discounts, Decimal("0"))),
            "new_fees": new,
        })
    return plan


@transaction.atomic
def charge_structure(structure, enrollments_for=None):
    """enrollments_for(structure) -> who to charge; default = the structure's class."""
    from .models import FeeStructure, StudentFee

    # One charge at a time per structure, so two clicks cannot double-charge.
    structure = FeeStructure.objects.select_for_update().get(id=structure.id)
    plan = plan_charge(structure, enrollments_for(structure) if enrollments_for else None)
    StudentFee.objects.bulk_create([
        StudentFee(
            student=enrollment.student,
            fee_structure=structure,
            fee_head=structure.fee_head,
            installment=line.installment,
            academic_year=structure.academic_year,
            academic_year_ref_id=structure.academic_year_ref_id,
            level_name=enrollment.level.name if enrollment.level_id else "",
            section_name=enrollment.section.name if enrollment.section_id else "",
            amount_due=line.amount,
            discount_amount=discount,
            discount_reason=reason[:255],
            due_date=line.due_date,
        )
        for enrollment, line, discount, reason in plan.to_create
    ])
    return plan


@transaction.atomic
def replace_installments(structure, rows):
    """Replace a structure's instalment plan. Refused once any student has been charged
    from it, because their fees already carry the old due dates and amounts."""
    from .models import FeeInstallment, StudentFee

    rows = validate_installment_plan(rows)
    if StudentFee.objects.filter(fee_structure=structure).exists():
        raise serializers.ValidationError(
            "Students have already been charged from this structure, so its instalments can no longer change."
        )
    structure.installments.all().delete()
    FeeInstallment.objects.bulk_create([
        FeeInstallment(
            fee_structure=structure, name=r["name"].strip(), percent=r["percent"], due_date=r["due_date"], position=i
        )
        for i, r in enumerate(rows)
    ])
    return list(structure.installments.all())
