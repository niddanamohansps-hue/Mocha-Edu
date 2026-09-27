"""
Fees business logic, financial validation, and object-level authorization.
Centralized here so allocation math, immutability rules, and the
race-safe payment path are never re-implemented per view, mirroring the
exact pattern established in attendance/timetable/examinations/services.py.
"""

import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers


# --- Identity resolution -----------------------------------------------
# Duplicated from attendance/timetable/examinations/services.py rather than
# imported cross-app - all these TENANT_APPS are peers and none should
# depend on another.

def get_profile_for_user(user):
    from profiles.models import Profile

    if not user or not getattr(user, "is_authenticated", False):
        return None
    return Profile.objects.filter(user_id=user.id).first()


def get_student_for_user(user):
    profile = get_profile_for_user(user)
    if not profile:
        return None
    return getattr(profile, "student_record", None)


def get_staff_member_for_user(user):
    profile = get_profile_for_user(user)
    if not profile:
        return None
    return getattr(profile, "staff_record", None)


def is_owner(request):
    from roles.models import UserRole

    if getattr(request.user, "is_superuser", False):
        return True
    tenant = getattr(request, "tenant", None)
    if not tenant or tenant.schema_name == "public":
        return False
    return UserRole.objects.filter(user=request.user, role__slug="owner").exists()


# --- Object-level authorization -------------------------------------------

def user_can_view_student_finances(request, student):
    """
    Combined self/staff authorization for the mixed-audience fee/payment
    endpoints. A student needs an explicit view_own_fees grant to see their
    OWN records - unlike Attendance/Examinations' unconditional self-access,
    this is a deliberate product decision: self-access still requires a
    permission grant, never an automatic bypass. Anyone else needs view_fees
    and then gets tenant-wide access - there is no instructor/section-scoping
    concept for finance (a homeroom instructor has no legitimate reason to
    see fee amounts, unlike attendance/results).

    NEVER used for parent access - parents are authorized entirely
    separately via get_child_for_parent()'s relationship check below, which
    has no permission-only fallback of any kind.
    """
    from roles.permissions import HasPermission

    own_student = get_student_for_user(request.user)
    if own_student is not None and own_student.id == student.id:
        return HasPermission("view_own_fees").has_permission(request, None)

    return HasPermission("view_fees").has_permission(request, None)


# --- Parent authorization (relationship-based, no permission fallback) ----
# Deliberately independent of user_can_access_student_fees above - reuses
# families.StudentParentRelation directly via the exact same pattern proven
# in parent_portal/services.py, duplicated here (not imported) since fees
# and parent_portal are peer TENANT_APPS. No owner-bypass, no "everyone
# else" fallback - a parent's access is ALWAYS scoped through the
# relationship table.

def get_parent_for_user(user):
    profile = get_profile_for_user(user)
    if not profile:
        return None
    return getattr(profile, "parent_record", None)


def get_child_for_parent(parent, student_id):
    from families.models import StudentParentRelation

    relation = (
        StudentParentRelation.objects.filter(parent=parent, student_id=student_id)
        .select_related("student__profile")
        .first()
    )
    return relation.student if relation else None


# --- Financial calculation (derived, never stored as authoritative) -------

def get_total_allocated(student_fee):
    """
    Net amount allocated against this StudentFee, across every Payment AND
    every reversal Payment (reversal allocations are negative, so summing
    everything nets out automatically - see PaymentAllocation's docstring).
    """
    total = student_fee.allocations.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")


def get_outstanding_balance(student_fee):
    return student_fee.amount_due - student_fee.discount_amount - get_total_allocated(student_fee)


def get_amount_paid(student_fee):
    """Net paid so far (never negative - a reversal can only bring this
    back toward zero, not below, since a reversal can never exceed the
    original allocation it undoes)."""
    return get_total_allocated(student_fee)


# --- Assignment / cancellation --------------------------------------------

def assign_student_fee(
    *,
    student,
    fee_head,
    academic_year,
    amount_due,
    fee_structure=None,
    due_date=None,
    discount_amount=Decimal("0"),
    discount_reason="",
):
    """
    Creates a StudentFee snapshot. level_name/section_name are captured from
    the student's CURRENT enrollment at assignment time - StudentLevel has
    no history of a student's section across a school year (unique_together
    is (student, academic_year), so a mid-year section change overwrites
    the same row), so this is the only point at which "what section was
    this student in" can be reliably recorded.
    """
    from .models import StudentFee

    current = (
        student.enrollments.filter(is_current=True).select_related("level", "section").first()
    )

    return StudentFee.objects.create(
        student=student,
        fee_structure=fee_structure,
        fee_head=fee_head,
        academic_year=academic_year,
        level_name=current.level.name if current and current.level_id else "",
        section_name=current.section.name if current and current.section_id else "",
        amount_due=amount_due,
        due_date=due_date,
        discount_amount=discount_amount or Decimal("0"),
        discount_reason=discount_reason or "",
    )


def can_edit_student_fee(student_fee):
    """amount_due/due_date (and discount) become immutable once ANY
    allocation exists against this fee - application-level rule, not a DB
    constraint (Postgres has no clean way to express "immutable once
    referenced elsewhere"), mirroring examinations.ExamSchedule.is_locked's
    exact same application-level gate."""
    return student_fee.status == "active" and not student_fee.allocations.exists()


def update_student_fee(student_fee, *, amount_due=None, due_date=None, discount_amount=None, discount_reason=None):
    if not can_edit_student_fee(student_fee):
        raise serializers.ValidationError(
            "This fee cannot be edited - it is cancelled or already has payments allocated against it."
        )

    fields = []
    if amount_due is not None:
        student_fee.amount_due = amount_due
        fields.append("amount_due")
    if due_date is not None:
        student_fee.due_date = due_date
        fields.append("due_date")
    discount_changed = False
    if discount_amount is not None and discount_amount != student_fee.discount_amount:
        student_fee.discount_amount = discount_amount
        fields.append("discount_amount")
        discount_changed = True
    if discount_reason is not None:
        student_fee.discount_reason = discount_reason
        fields.append("discount_reason")

    if fields:
        fields.append("updated_at")
        student_fee.save(update_fields=fields)

    return student_fee, discount_changed


def cancel_student_fee(student_fee, *, reason):
    """
    Soft cancellation only - never a physical delete. Requires a mandatory
    reason. A fee that already has payments allocated against it cannot be
    cancelled outright in V1 (refunds are out of scope - see design report
    S10); it must be handled manually until a refund workflow exists.
    """
    if not reason or not reason.strip():
        raise serializers.ValidationError({"cancellation_reason": "A cancellation reason is required."})

    if student_fee.status == "cancelled":
        raise serializers.ValidationError("This fee is already cancelled.")

    if student_fee.allocations.exists():
        raise serializers.ValidationError(
            "This fee has payments allocated against it and cannot be cancelled in V1 "
            "(refunds are not supported yet)."
        )

    student_fee.status = "cancelled"
    student_fee.cancellation_reason = reason
    student_fee.cancelled_at = timezone.now()
    student_fee.save(update_fields=["status", "cancellation_reason", "cancelled_at", "updated_at"])
    return student_fee


# --- Payment recording (race-safe) ----------------------------------------

def generate_receipt_number():
    return f"RCPT-{uuid.uuid4().hex[:10].upper()}"


@transaction.atomic
def record_payment(*, student, amount, method, allocations, recorded_by, reference_note=""):
    """
    allocations: list of {"student_fee_id": <uuid>, "amount": Decimal}.

    Locks every referenced StudentFee row (select_for_update, in a stable
    id order to avoid deadlocking against a concurrent payment touching an
    overlapping set of fees) before validating, so two simultaneous
    payments against the same StudentFee can never both succeed past its
    outstanding balance - the second request re-reads the now-updated
    outstanding balance only after the first transaction commits and
    releases the lock.
    """
    from .models import Payment, PaymentAllocation, StudentFee

    if amount is None or amount <= 0:
        raise serializers.ValidationError({"amount": "Payment amount must be positive."})
    if not allocations:
        raise serializers.ValidationError({"allocations": "At least one allocation is required."})

    total_allocated = sum((a["amount"] for a in allocations), Decimal("0"))
    if total_allocated != amount:
        raise serializers.ValidationError(
            {"allocations": "The sum of allocations must equal the payment amount."}
        )

    fee_ids = [a["student_fee_id"] for a in allocations]
    if len(set(fee_ids)) != len(fee_ids):
        raise serializers.ValidationError({"allocations": "Duplicate fee record in the same payment."})

    locked_fees = {
        sf.id: sf
        for sf in StudentFee.objects.select_for_update().filter(id__in=fee_ids).order_by("id")
    }
    if len(locked_fees) != len(fee_ids):
        raise serializers.ValidationError({"allocations": "One or more fee records were not found."})

    for entry in allocations:
        student_fee = locked_fees[entry["student_fee_id"]]
        alloc_amount = entry["amount"]

        if alloc_amount <= 0:
            raise serializers.ValidationError({"allocations": "Allocation amounts must be positive."})
        if student_fee.student_id != student.id:
            raise serializers.ValidationError(
                {"allocations": "A fee record does not belong to this student."}
            )
        if student_fee.status != "active":
            raise serializers.ValidationError(
                {"allocations": f"'{student_fee.fee_head.name}' is cancelled and cannot receive payments."}
            )

        outstanding = get_outstanding_balance(student_fee)
        if alloc_amount > outstanding:
            raise serializers.ValidationError(
                {
                    "allocations": (
                        f"Allocation of {alloc_amount} exceeds the outstanding balance of "
                        f"{outstanding} for '{student_fee.fee_head.name}'."
                    )
                }
            )

    payment = Payment.objects.create(
        student=student,
        amount=amount,
        method=method,
        status="completed",
        receipt_number=generate_receipt_number(),
        reference_note=reference_note,
        recorded_by=recorded_by,
    )
    PaymentAllocation.objects.bulk_create(
        [
            PaymentAllocation(
                payment=payment,
                student_fee_id=entry["student_fee_id"],
                amount=entry["amount"],
            )
            for entry in allocations
        ]
    )
    return payment


@transaction.atomic
def reverse_payment(*, payment, recorded_by, reason=""):
    """
    Creates a NEW Payment row representing the reversal - the original
    Payment is never mutated (fully immutable, insert-only). Locks the
    original Payment row to prevent two concurrent reversal requests from
    both succeeding (the OneToOneField on Payment.reverses also enforces
    this at the database level as the final backstop).
    """
    from .models import Payment, PaymentAllocation

    payment = Payment.objects.select_for_update().get(id=payment.id)

    if payment.reverses_id is not None:
        raise serializers.ValidationError("A reversal payment cannot itself be reversed.")
    if Payment.objects.filter(reverses=payment).exists():
        raise serializers.ValidationError("This payment has already been reversed.")

    reversal = Payment.objects.create(
        student=payment.student,
        amount=payment.amount,
        method=payment.method,
        status="reversed",
        receipt_number=generate_receipt_number(),
        reference_note=reason,
        reverses=payment,
        recorded_by=recorded_by,
    )
    PaymentAllocation.objects.bulk_create(
        [
            PaymentAllocation(
                payment=reversal,
                student_fee_id=allocation.student_fee_id,
                amount=-allocation.amount,
            )
            for allocation in payment.allocations.all()
        ]
    )
    return reversal
