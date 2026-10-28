"""
What schools pay the platform for EduSekai (not school fees: those are in the fees app).

Platform-wide (public schema): a Plan is what is sold; each school has one Subscription saying which plan,
how it is paid (monthly, yearly, or once) and until when it is paid for; every charge is an Invoice.
Money is kept in rupees with paise (Decimal, 2 places); Razorpay amounts are converted at its edge.
"""
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

MONTHLY, YEARLY, ONE_TIME = "monthly", "yearly", "one_time"
CYCLE_CHOICES = [(MONTHLY, "Monthly"), (YEARLY, "Yearly"), (ONE_TIME, "One-time")]


class Plan(models.Model):
    """A plan can be offered on any of the three cycles: a price left empty means "not offered that way"."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    features = models.JSONField(default=list, blank=True, help_text="Short lines shown on the pricing page.")
    student_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Empty = unlimited.")

    # Prices exclude GST; GST is added on the invoice.
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                        validators=[MinValueValidator(Decimal("1.00"))])
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       validators=[MinValueValidator(Decimal("1.00"))])
    one_time_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         validators=[MinValueValidator(Decimal("1.00"))])
    one_time_validity_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="How long a one-time purchase lasts. Empty = for life.")
    trial_days = models.PositiveSmallIntegerField(default=0, help_text="0 = no free trial.")
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("18.00"))

    is_public = models.BooleanField(default=True, help_text="Shown on the pricing page and at signup.")
    sort_order = models.PositiveSmallIntegerField(default=0)
    # Razorpay's own plan ids for the recurring cycles, created on first use (they cannot be edited later:
    # a price change makes a new Razorpay plan, and existing subscriptions keep theirs).
    razorpay_monthly_plan_id = models.CharField(max_length=60, blank=True)
    razorpay_yearly_plan_id = models.CharField(max_length=60, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def price_for(self, cycle):
        return {MONTHLY: self.monthly_price, YEARLY: self.yearly_price, ONE_TIME: self.one_time_price}[cycle]

    def offers(self, cycle):
        return self.price_for(cycle) is not None


class Subscription(models.Model):
    """One per school. ``paid_until`` is what access is decided on; statuses explain why."""

    TRIAL, ACTIVE, PAST_DUE, READ_ONLY, CANCELLED, PENDING = (
        "trial", "active", "past_due", "read_only", "cancelled", "pending")
    STATUS_CHOICES = [
        (PENDING, "Waiting for first payment"),
        (TRIAL, "Free trial"),
        (ACTIVE, "Active"),
        (PAST_DUE, "Payment overdue (grace period)"),
        (READ_ONLY, "Read-only (unpaid)"),
        (CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField("organizations.Organization", on_delete=models.PROTECT,
                                        related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    cycle = models.CharField(max_length=10, choices=CYCLE_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING, db_index=True)

    trial_ends_at = models.DateTimeField(null=True, blank=True)
    paid_until = models.DateTimeField(null=True, blank=True,
                                      help_text="Access is paid up to here. Empty with ACTIVE = for life.")
    grace_ends_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    # Schools that existed before billing: full access, never billed automatically.
    is_legacy = models.BooleanField(default=False)

    razorpay_subscription_id = models.CharField(max_length=60, blank=True, db_index=True)
    # GST details the school gives on its Billing page (state = GST state code, e.g. "29").
    billing_state = models.CharField(max_length=2, blank=True)
    billing_gstin = models.CharField(max_length=15, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "paid_until"], name="billing_sub_status_paid_idx")]

    def __str__(self):
        return f"{self.organization} - {self.plan} ({self.get_cycle_display()}, {self.get_status_display()})"

    def can_write(self, now=None):
        """True while the school may change data. Reading is always allowed."""
        now = now or timezone.now()
        if self.is_legacy:
            return True
        if self.status == self.TRIAL:
            return bool(self.trial_ends_at and now < self.trial_ends_at)
        if self.status == self.ACTIVE:
            return self.paid_until is None or now < self.paid_until
        if self.status == self.PAST_DUE:
            return bool(self.grace_ends_at and now < self.grace_ends_at)
        return False


class Invoice(models.Model):
    """One charge. Numbered per Indian financial year (April-March) when it is paid: ES/2026-27/00001."""

    DRAFT, PAID, FAILED, VOID = "draft", "paid", "failed", "void"
    STATUS_CHOICES = [(DRAFT, "Awaiting payment"), (PAID, "Paid"), (FAILED, "Failed"), (VOID, "Cancelled")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="invoices")
    number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT, db_index=True)

    plan_name = models.CharField(max_length=80)
    cycle = models.CharField(max_length=10, choices=CYCLE_CHOICES)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField(null=True, blank=True)  # empty = for life
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # before GST
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Who is billed, copied at issue time so the invoice never changes afterwards.
    billed_name = models.CharField(max_length=255)
    billed_email = models.EmailField(blank=True)
    billed_address = models.TextField(blank=True)
    billed_gstin = models.CharField(max_length=15, blank=True)
    place_of_supply = models.CharField(max_length=2, blank=True)
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    razorpay_order_id = models.CharField(max_length=60, blank=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=60, blank=True, unique=True, null=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number or f"Draft {self.id}"


class InvoiceCounter(models.Model):
    """The last invoice number used in each financial year (rows are locked while a number is taken)."""

    financial_year = models.CharField(max_length=7, primary_key=True)  # "2026-27"
    last_number = models.PositiveIntegerField(default=0)
