"""
Fees business logic, financial validation, and object-level authorization.
Centralized here so allocation math, immutability rules, and the
race-safe payment path are never re-implemented per view, mirroring the
exact pattern established in attendance/timetable/examinations/services.py.
"""

import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
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
    Combined authorization for student finance and payment receipt endpoints:
    - Student: caller is the student AND has 'view_own_fees'.
    - Parent: caller is a linked parent to this student AND has 'view_child_fees'.
    - Staff / Admin: caller has 'view_fees' or 'collect_payments'.
    """
    from roles.permissions import HasPermission

    own_student = get_student_for_user(request.user)
    if own_student is not None and own_student.id == student.id:
        return HasPermission("view_own_fees").has_permission(request, None)

    parent = get_parent_for_user(request.user)
    if parent is not None:
        child = get_child_for_parent(parent, student.id)
        if child is not None:
            return HasPermission("view_child_fees").has_permission(request, None)

    return (
        HasPermission("view_fees").has_permission(request, None)
        or HasPermission("collect_payments").has_permission(request, None)
    )


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


def get_linked_children(parent):
    from families.models import StudentParentRelation

    return (
        StudentParentRelation.objects.filter(parent=parent)
        .select_related("student__profile")
    )


def user_can_initiate_student_online_payment(request, student):
    """
    Authorization rule for initiating an online payment order for a student:
    - Staff / Admin: must have 'collect_payments' permission (tenant-wide).
    - Student (self): caller must be this student AND have 'pay_own_fees' permission.
    - Parent: caller must be a registered parent linked to this student AND have 'pay_child_fees' permission.
    """
    from roles.permissions import HasPermission

    # 1. Staff with collect_payments
    if HasPermission("collect_payments").has_permission(request, None):
        return True

    # 2. Student self-payment
    own_student = get_student_for_user(request.user)
    if own_student is not None and own_student.id == student.id:
        return HasPermission("pay_own_fees").has_permission(request, None)

    # 3. Parent linked to this student
    parent = get_parent_for_user(request.user)
    if parent is not None:
        child = get_child_for_parent(parent, student.id)
        if child is not None:
            return HasPermission("pay_child_fees").has_permission(request, None)

    return False


def user_can_view_online_order(request, order):
    """
    Authorization rule for viewing an OnlinePaymentOrder:
    - Staff / Admin: has 'view_fees' or 'collect_payments'.
    - Order creator: if order was created by this user (order.created_by_user_id == request.user.id).
    - Student: caller is the student AND has 'view_own_fees'.
    - Parent: caller is a registered parent linked to order.student AND has 'view_child_fees'.
    """
    from roles.permissions import HasPermission

    if (
        HasPermission("view_fees").has_permission(request, None)
        or HasPermission("collect_payments").has_permission(request, None)
    ):
        return True

    if order.created_by_user_id and str(order.created_by_user_id) == str(request.user.id):
        return True

    own_student = get_student_for_user(request.user)
    if own_student is not None and own_student.id == order.student_id:
        return HasPermission("view_own_fees").has_permission(request, None)

    parent = get_parent_for_user(request.user)
    if parent is not None:
        child = get_child_for_parent(parent, order.student_id)
        if child is not None:
            return HasPermission("view_child_fees").has_permission(request, None)

    return False


# --- Financial calculation (derived, never stored as authoritative) -------

def annotate_with_allocation_total(queryset):
    """
    Attaches the net allocated-amount total to every row of `queryset` in
    ONE grouped query (Sum over the reverse `allocations` relation), so
    get_total_allocated() can read it straight off each object instead of
    issuing a separate aggregate query per StudentFee. Use this on any
    queryset that will have get_total_allocated()/get_amount_paid()/
    get_outstanding_balance() called on more than one of its rows (e.g.
    OutstandingReportView, StudentFeeSerializer(qs, many=True)).

    Coalesces a StudentFee with no allocations to 0 rather than leaving
    SQL NULL - get_total_allocated()'s `or Decimal("0")` already treated
    a NULL/None aggregate as zero, so this changes nothing about any
    existing caller's result; it's required so `_allocations_total` can
    safely be used in further arithmetic (see
    annotate_with_outstanding_balance()) without NULL propagating through
    the whole expression.
    """
    return queryset.annotate(
        _allocations_total=Coalesce(
            Sum("allocations__amount"),
            Value(Decimal("0")),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
    )


def annotate_with_outstanding_balance(queryset):
    """
    Builds on annotate_with_allocation_total() to attach `_outstanding`
    (amount_due - discount_amount - _allocations_total) to every row in
    ONE query, so "outstanding > 0" can be filtered at the database level
    -  the fix for OutstandingReportView materializing and Python-filtering
    every StudentFee before Phase 9C. Matches get_outstanding_balance()'s
    formula exactly.

    NOTE: annotating with an aggregate-derived expression makes Django
    drop the model's default `Meta.ordering` (confirmed empirically - see
    Phase 9C report) - callers that need deterministic order (e.g. for
    pagination) must re-apply `.order_by(...)` explicitly after calling
    this, same as OutstandingReportView now does.
    """
    from django.db.models import ExpressionWrapper, F

    qs = annotate_with_allocation_total(queryset)
    return qs.annotate(
        _outstanding=ExpressionWrapper(
            F("amount_due") - F("discount_amount") - F("_allocations_total"),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
    )


def get_total_allocated(student_fee):
    """
    Net amount allocated against this StudentFee, across every Payment AND
    every reversal Payment (reversal allocations are negative, so summing
    everything nets out automatically - see PaymentAllocation's docstring).

    If `student_fee` came from a queryset already annotated via
    annotate_with_allocation_total(), reuses that value with zero extra
    queries - this is what eliminates the N+1 when many StudentFee rows
    are processed together (OutstandingReportView,
    StudentFeeSerializer(qs, many=True)).

    A plain, un-annotated instance always issues a fresh aggregate query,
    exactly as before this phase. This deliberately does NOT memoize that
    fallback result onto the instance: the same StudentFee object can
    legitimately be rechecked after a write against the same row happens
    through a SEPARATE query (e.g. record_payment() then reverse_payment()
    on the same fee, as in ReversePaymentTests) - caching here would
    silently return a stale balance in that case. Only an explicit,
    query-time annotation is safe to reuse, because it's inherently a
    snapshot as of that one query, not a value that's expected to track
    later writes - the same way any other Django annotation behaves.
    """
    if hasattr(student_fee, "_allocations_total"):
        return student_fee._allocations_total or Decimal("0")
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
def record_payment(*, student, amount, method, allocations, recorded_by, reference_note="", gateway_reference=""):
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
        gateway_reference=gateway_reference or "",
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


# --- Online Payment Workflow -----------------------------------------------

def initiate_online_payment_order(
    *,
    student,
    amount,
    allocations,
    gateway="esewa",
    created_by=None,
    return_url=None,
    failure_url=None,
    ttl_minutes=30,
):
    """
    Initiates an online payment order for a student.

    - Validates amount and fee allocations against current outstanding balances.
    - Creates an OnlinePaymentOrder in status 'initiated'.
    - Calls the gateway adapter to generate signed parameters (e.g. eSewa v2 HMAC).
    - Sets order status to 'pending' and returns (order, gateway_payload).
    """
    import datetime
    from .gateways import get_gateway_adapter
    from .models import OnlinePaymentOrder, StudentFee

    amount = Decimal(str(amount))
    if amount <= Decimal("0"):
        raise serializers.ValidationError({"amount": "Payment amount must be positive."})

    if not allocations:
        raise serializers.ValidationError({"allocations": "At least one allocation is required."})

    normalized_allocations = []
    for a in allocations:
        sf_id = a["student_fee_id"] if isinstance(a["student_fee_id"], uuid.UUID) else uuid.UUID(str(a["student_fee_id"]))
        alloc_amt = Decimal(str(a["amount"]))
        normalized_allocations.append({"student_fee_id": sf_id, "amount": alloc_amt})

    total_allocated = sum((a["amount"] for a in normalized_allocations), Decimal("0"))
    if total_allocated != amount:
        raise serializers.ValidationError(
            {"allocations": "The sum of allocations must equal the payment amount."}
        )

    fee_ids = [a["student_fee_id"] for a in normalized_allocations]
    if len(set(fee_ids)) != len(fee_ids):
        raise serializers.ValidationError({"allocations": "Duplicate fee record in the same payment order."})

    fees = {sf.id: sf for sf in StudentFee.objects.filter(id__in=fee_ids)}
    if len(fees) != len(fee_ids):
        raise serializers.ValidationError({"allocations": "One or more fee records were not found."})

    for a in normalized_allocations:
        fee = fees[a["student_fee_id"]]
        alloc_amt = a["amount"]
        if alloc_amt <= Decimal("0"):
            raise serializers.ValidationError({"allocations": "Allocation amounts must be positive."})
        if fee.student_id != student.id:
            raise serializers.ValidationError({"allocations": "A fee record does not belong to this student."})
        if fee.status != "active":
            raise serializers.ValidationError(
                {"allocations": f"'{fee.fee_head.name}' is cancelled and cannot receive payments."}
            )
        outstanding = get_outstanding_balance(fee)
        if alloc_amt > outstanding:
            raise serializers.ValidationError(
                {
                    "allocations": (
                        f"Allocation of {alloc_amt} exceeds the outstanding balance of "
                        f"{outstanding} for '{fee.fee_head.name}'."
                    )
                }
            )

    adapter = get_gateway_adapter(gateway)
    gateway_order_id = uuid.uuid4().hex
    expires_at = timezone.now() + datetime.timedelta(minutes=ttl_minutes)

    allocations_snapshot = [
        {"student_fee_id": str(a["student_fee_id"]), "amount": str(a["amount"])}
        for a in normalized_allocations
    ]

    created_by_user_id = None
    if created_by:
        created_by_user_id = getattr(created_by, "id", created_by)

    order = OnlinePaymentOrder.objects.create(
        student=student,
        amount=amount,
        gateway=gateway,
        status="initiated",
        allocations_snapshot=allocations_snapshot,
        gateway_order_id=gateway_order_id,
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
    )

    payload = adapter.initiate_payment(order, return_url=return_url, failure_url=failure_url)
    order.status = "pending"
    order.save(update_fields=["status", "updated_at"])

    return order, payload


def settle_online_payment_order(
    *,
    order_id_or_gateway_order_id,
    raw_callback_payload,
    recorded_by=None,
):
    """
    Verifies gateway signature/payload and settles an OnlinePaymentOrder.

    Idempotency:
    - If order is already 'success', returns existing payment immediately.
    - If order is already 'reconciliation_required', returns status with audit reason.

    Financial Invariant & Interim Settlement Handling (Option B):
    - If gateway verification fails, saves order.status = 'failed' with audit reason.
    - If verification succeeds, enters atomic transaction: locks the OnlinePaymentOrder
      and referenced StudentFee rows with select_for_update.
    - If interim cash or other settlement reduced the fee's outstanding balance:
      - Sets order.status = 'reconciliation_required'
      - Preserves verified transaction data, ref_id, and audit explanation.
      - NEVER creates a partial Payment violating allocation-sum invariants or an advance-credit ledger.
    - If balances are intact:
      - Calls record_payment() with method='online' and gateway_reference.
      - Sets order.status = 'success', links order.payment.
    """
    from .gateways import get_gateway_adapter
    from .models import OnlinePaymentOrder, StudentFee

    order = None

    if isinstance(order_id_or_gateway_order_id, uuid.UUID):
        order = OnlinePaymentOrder.objects.filter(id=order_id_or_gateway_order_id).first()
    elif isinstance(order_id_or_gateway_order_id, str):
        try:
            u = uuid.UUID(order_id_or_gateway_order_id)
            order = OnlinePaymentOrder.objects.filter(id=u).first()
        except ValueError:
            order = None
        if not order:
            order = OnlinePaymentOrder.objects.filter(gateway_order_id=order_id_or_gateway_order_id).first()

    if not order:
        raise serializers.ValidationError({"order": "Payment order not found."})

    # Idempotency checks
    if order.status == "success":
        return {
            "status": "already_completed",
            "order": order,
            "payment": order.payment,
            "receipt_number": order.payment.receipt_number if order.payment else "",
        }

    if order.status == "reconciliation_required":
        return {
            "status": "reconciliation_required",
            "order": order,
            "reason": order.reconciliation_reason,
        }

    if order.status in ("failed", "expired"):
        raise serializers.ValidationError({
            "order": f"Cannot settle an order in '{order.status}' status."
        })

    # Gateway verification
    adapter = get_gateway_adapter(order.gateway)
    verify_result = adapter.verify_callback(order, raw_callback_payload)

    if not verify_result.is_valid:
        order.status = "failed"
        order.gateway_response = (
            raw_callback_payload
            if isinstance(raw_callback_payload, dict)
            else {"raw": str(raw_callback_payload)}
        )
        order.reconciliation_reason = verify_result.error_message
        order.save(update_fields=["status", "gateway_response", "reconciliation_reason", "updated_at"])
        raise serializers.ValidationError({"gateway": verify_result.error_message})

    with transaction.atomic():
        order = OnlinePaymentOrder.objects.select_for_update().get(id=order.id)
        if order.status == "success":
            return {
                "status": "already_completed",
                "order": order,
                "payment": order.payment,
                "receipt_number": order.payment.receipt_number if order.payment else "",
            }

        # Gateway confirmed funds
        order.gateway_reference = verify_result.gateway_reference
        order.gateway_response = verify_result.raw_data

        # Check expiration: if expired after gateway confirmed payment, require reconciliation
        if timezone.now() > order.expires_at:
            order.status = "reconciliation_required"
            order.reconciliation_reason = f"Gateway payment verified after order expiration at {order.expires_at}."
            order.save(update_fields=["status", "gateway_reference", "gateway_response", "reconciliation_reason", "updated_at"])
            return {
                "status": "reconciliation_required",
                "order": order,
                "reason": order.reconciliation_reason,
            }

        # Lock StudentFee rows in stable ID order to evaluate balances
        fee_ids = [uuid.UUID(a["student_fee_id"]) for a in order.allocations_snapshot]
        locked_fees = {
            sf.id: sf
            for sf in StudentFee.objects.select_for_update().filter(id__in=fee_ids).order_by("id")
        }

        if len(locked_fees) != len(fee_ids):
            order.status = "reconciliation_required"
            order.reconciliation_reason = "One or more allocated fee records are missing from the database."
            order.save(update_fields=["status", "gateway_reference", "gateway_response", "reconciliation_reason", "updated_at"])
            return {
                "status": "reconciliation_required",
                "order": order,
                "reason": order.reconciliation_reason,
            }

        can_allocate = True
        conflict_reasons = []
        allocations_for_payment = []

        for a in order.allocations_snapshot:
            fee_id = uuid.UUID(a["student_fee_id"])
            fee = locked_fees[fee_id]
            alloc_amt = Decimal(str(a["amount"]))

            if fee.status != "active":
                can_allocate = False
                conflict_reasons.append(f"Fee '{fee.fee_head.name}' is {fee.status}")

            outstanding = get_outstanding_balance(fee)
            if alloc_amt > outstanding:
                can_allocate = False
                conflict_reasons.append(
                    f"Allocation of {alloc_amt} exceeds current outstanding {outstanding} for '{fee.fee_head.name}'"
                )

            allocations_for_payment.append({"student_fee_id": fee_id, "amount": alloc_amt})

        if not can_allocate:
            # Interim cash conflict: Option B — require reconciliation
            order.status = "reconciliation_required"
            order.reconciliation_reason = "; ".join(conflict_reasons)
            order.save(update_fields=["status", "gateway_reference", "gateway_response", "reconciliation_reason", "updated_at"])
            return {
                "status": "reconciliation_required",
                "order": order,
                "reason": order.reconciliation_reason,
            }

        # Balances are intact: execute atomic record_payment
        payment = record_payment(
            student=order.student,
            amount=order.amount,
            method="online",
            allocations=allocations_for_payment,
            recorded_by=recorded_by,
            reference_note=f"Online payment via {order.gateway.upper()} (Ref: {order.gateway_reference})",
            gateway_reference=order.gateway_reference,
        )

        order.payment = payment
        order.status = "success"
        order.completed_at = timezone.now()
        order.save(update_fields=["payment", "status", "completed_at", "gateway_reference", "gateway_response", "updated_at"])

        return {
            "status": "success",
            "order": order,
            "payment": payment,
            "receipt_number": payment.receipt_number,
        }


def reconcile_online_payment_order(order, *, recorded_by=None):
    """
    Reconciles a pending or orphaned OnlinePaymentOrder by querying the gateway's status API.
    If the gateway reports COMPLETE, calls settle_online_payment_order.
    If the order has expired without payment, marks status as 'expired'.
    """
    from .gateways import get_gateway_adapter

    if order.status in ("success", "reconciliation_required", "failed"):
        return {"status": order.status, "order": order}

    adapter = get_gateway_adapter(order.gateway)
    status_result = adapter.query_status(order)

    if status_result.status == "COMPLETE":
        # Formulate payload for settlement
        callback_payload = {
            "status": "COMPLETE",
            "transaction_uuid": order.gateway_order_id,
            "ref_id": status_result.gateway_reference,
            "total_amount": str(order.amount),
        }
        return settle_online_payment_order(
            order_id_or_gateway_order_id=order.id,
            raw_callback_payload=status_result.raw_data or callback_payload,
            recorded_by=recorded_by,
        )

    if order.status == "pending" and timezone.now() > order.expires_at:
        order.status = "expired"
        order.reconciliation_reason = f"Order expired without gateway confirmation (Gateway status: {status_result.status})."
        order.save(update_fields=["status", "reconciliation_reason", "updated_at"])
        return {"status": "expired", "order": order}

    return {"status": order.status, "gateway_status": status_result.status, "order": order}
