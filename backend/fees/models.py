import uuid
from decimal import Decimal

from django.db import models


FEE_FREQUENCY_CHOICES = [
    ("one_time", "One Time"),
    ("monthly", "Monthly"),
    ("term", "Term"),
    ("annual", "Annual"),
]

PAYMENT_METHOD_CHOICES = [
    ("cash", "Cash"),
    ("bank_transfer", "Bank Transfer"),
    ("upi", "UPI"),
    ("cheque", "Cheque"),
    ("online", "Online"),
]

PAYMENT_STATUS_CHOICES = [
    ("completed", "Completed"),
    ("reversed", "Reversed"),
]

STUDENT_FEE_STATUS_CHOICES = [
    ("active", "Active"),
    ("cancelled", "Cancelled"),
]

GATEWAY_CHOICES = [
    ("esewa", "eSewa"),
    ("khalti", "Khalti"),
]

ONLINE_ORDER_STATUS_CHOICES = [
    ("initiated", "Initiated"),
    ("pending", "Pending Gateway Confirmation"),
    ("success", "Payment Completed"),
    ("failed", "Payment Failed"),
    ("expired", "Order Expired"),
    ("reconciliation_required", "Reconciliation Required"),
]


class FeeHead(models.Model):
    """
    Tenant-configurable charge category (e.g. "Tuition", "Transport").
    Deliberately NOT a hardcoded Python choices list - naming varies too
    much by school/region to fix in code, mirroring the exact reasoning
    already used for examinations.ExamType.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FeeStructure(models.Model):
    """
    Definition layer: "this FeeHead costs X for this level/section/year."
    NOT a per-student record - StudentFee snapshots the amount/level/section
    at assignment time, so a later FeeStructure edit never retroactively
    changes what an already-assigned student owes.

    level/section are optional - some fees apply tenant-wide (e.g. an
    "Annual Day" fee), so scoping is opt-in, not mandatory.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fee_head = models.ForeignKey(FeeHead, on_delete=models.PROTECT, related_name="structures")
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fee_structures",
    )
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fee_structures",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=FEE_FREQUENCY_CHOICES, default="one_time")
    due_date = models.DateField(null=True, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["academic_year", "fee_head__name"]

    def __str__(self):
        return f"{self.fee_head.name} - {self.academic_year}"


class StudentFee(models.Model):
    """
    Per-student assignment: the source-of-truth for "what does this student
    owe and by when." Snapshots level_name/section_name at assignment time
    rather than live-joining StudentLevel at read time - StudentLevel has no
    history of a student's section across a school year (unique_together is
    (student, academic_year), so a mid-year section change overwrites the
    same row) - so a fee scoped "per section" must record what section the
    student was actually in when the fee was assigned, not whatever section
    they're in when someone reads it later.

    amount_due/due_date become immutable once any PaymentAllocation exists
    against this row (enforced in services.py, not the database - see
    can_edit_student_fee()). Cancellation is always soft (status flip +
    mandatory cancellation_reason), never a physical delete.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="fees")
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="student_fees",
    )
    fee_head = models.ForeignKey(FeeHead, on_delete=models.PROTECT, related_name="student_fees")
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    level_name = models.CharField(max_length=50, blank=True)
    section_name = models.CharField(max_length=50, blank=True)

    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    discount_reason = models.CharField(max_length=255, blank=True)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STUDENT_FEE_STATUS_CHOICES, default="active")
    cancellation_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["student", "academic_year"], name="studentfee_student_year_idx"),
            models.Index(fields=["due_date"], name="studentfee_due_date_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} - {self.fee_head.name} - {self.amount_due}"


class Payment(models.Model):
    """
    Immutable financial event - the actual money received. Never PATCH/PUT,
    ever, and never deleted (on_delete=PROTECT everywhere it's referenced).
    Corrections happen via reverse_payment() creating a NEW Payment row
    (status="reversed", reverses=<original>) - the original row is never
    mutated after creation.

    receipt_number: a receipt is a rendered view of this row plus its
    allocations, not a separate stored model (mirrors examinations'
    "aggregation only, no stored ReportCard model" precedent) - this field
    is the only piece of receipt-specific data that needs to persist.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash")
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="completed")
    receipt_number = models.CharField(max_length=50, unique=True)
    reference_note = models.CharField(max_length=255, blank=True)

    # Populated only once an online gateway exists (deferred - see design
    # report S8) - present now so a future gateway doesn't require a schema
    # change to Payment/PaymentAllocation.
    gateway_reference = models.CharField(max_length=255, blank=True)

    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal",
        help_text="Set only on a reversal Payment - points at the original Payment it reverses.",
    )

    recorded_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["student", "-created_at"], name="payment_student_history_idx"),
            models.Index(fields=["-created_at"], name="payment_created_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.receipt_number} - {self.student} - {self.amount}"


class PaymentAllocation(models.Model):
    """
    Immutable link: which StudentFee a Payment (or a reversal Payment) was
    applied against, and how much. A normal allocation's amount is positive;
    a reversal's allocation amount is the negation of the original, so
    summing every allocation against a StudentFee always yields the true
    net-paid amount without needing to filter by Payment.status anywhere.
    Never edited or deleted after creation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    student_fee = models.ForeignKey(StudentFee, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("payment", "student_fee")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(amount=0), name="paymentallocation_amount_nonzero"
            ),
        ]

    def __str__(self):
        return f"{self.payment_id} -> {self.student_fee_id} : {self.amount}"


class TenantPaymentGatewayConfig(models.Model):
    """
    Tenant-scoped payment gateway credentials. Allows an individual school
    to collect online fees directly into their own merchant account (e.g. eSewa)
    with secrets encrypted at rest using accounts.utils.crypto.
    If no active record exists for a gateway, system-level fallback (settings.ESEWA_*)
    is controlled by settings.FEES_ALLOW_GLOBAL_GATEWAY_FALLBACK.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, unique=True)
    merchant_code = models.CharField(max_length=100)
    encrypted_secret = models.CharField(max_length=512)
    is_active = models.BooleanField(default=True)
    allow_global_fallback = models.BooleanField(
        default=False,
        help_text="If False, a misconfigured or inactive tenant gateway fails closed instead of falling back to global keys.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["gateway"]

    def __str__(self):
        return f"{self.gateway} ({self.merchant_code}) - {'Active' if self.is_active else 'Inactive'}"

    def set_secret(self, raw_secret: str) -> None:
        from accounts.utils.crypto import encrypt_secret
        self.encrypted_secret = encrypt_secret(raw_secret)

    def get_secret(self) -> str:
        from accounts.utils.crypto import decrypt_secret
        return decrypt_secret(self.encrypted_secret)


class OnlinePaymentOrder(models.Model):
    """
    State machine for student online fee payments.

    Tracks the full lifecycle of an online payment intent:
    INITIATED -> PENDING -> SUCCESS | FAILED | EXPIRED | RECONCILIATION_REQUIRED.

    CRITICAL FINANCIAL INVARIANT:
    `fees.Payment` rows are strictly insert-only and immutable, representing
    finalized money received with positive PaymentAllocations.
    Therefore, pending online payments MUST NOT create a `Payment` prematurely.
    Only upon verified gateway confirmation and successful balance validation does
    an atomic `record_payment()` execute, linking the resulting `Payment` here.

    If the gateway confirms the charge, but interim settlement (e.g. cash at counter)
    reduced the fee's outstanding balance, the order transitions to
    `reconciliation_required` without violating invariants or discarding verified funds.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="online_payment_orders"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, default="esewa")
    status = models.CharField(
        max_length=30, choices=ONLINE_ORDER_STATUS_CHOICES, default="initiated", db_index=True
    )

    allocations_snapshot = models.JSONField(
        help_text="Intended allocation per StudentFee captured at order initiation time."
    )

    gateway_order_id = models.CharField(
        max_length=255, unique=True, db_index=True,
        help_text="Merchant transaction UUID passed to the gateway (e.g. transaction_uuid in eSewa)."
    )
    gateway_reference = models.CharField(
        max_length=255, blank=True,
        help_text="Gateway's transaction reference code upon confirmation (e.g. ref_id in eSewa)."
    )
    gateway_response = models.JSONField(
        default=dict, blank=True,
        help_text="Raw verified payload returned by the gateway callback or status inquiry."
    )

    reconciliation_reason = models.TextField(
        blank=True,
        help_text="Populated if order requires reconciliation due to interim balance reduction or gateway mismatch."
    )

    created_by_user_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Soft-link to the public User UUID who initiated this order (preserves cross-schema boundary).",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="online_order",
        help_text="Immutable Payment created upon successful gateway verification and allocation.",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "status"], name="online_order_student_st_idx"),
            models.Index(fields=["status", "expires_at"], name="online_order_status_exp_idx"),
        ]

    def __str__(self):
        return f"{self.gateway_order_id} - {self.student} - {self.amount} ({self.status})"

    @property
    def created_by(self):
        if not self.created_by_user_id:
            return None
        from accounts.models import User
        return User.objects.filter(id=self.created_by_user_id).first()
