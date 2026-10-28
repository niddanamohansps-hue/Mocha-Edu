import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

CYCLES = [("monthly", "Monthly"), ("yearly", "Yearly"), ("one_time", "One-time")]
PRICE = dict(max_digits=10, decimal_places=2, null=True, blank=True,
             validators=[django.core.validators.MinValueValidator(Decimal("1.00"))])


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=80)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("features", models.JSONField(blank=True, default=list, help_text="Short lines shown on the pricing page.")),
                ("student_limit", models.PositiveIntegerField(blank=True, help_text="Empty = unlimited.", null=True)),
                ("monthly_price", models.DecimalField(**PRICE)),
                ("yearly_price", models.DecimalField(**PRICE)),
                ("one_time_price", models.DecimalField(**PRICE)),
                ("one_time_validity_days", models.PositiveIntegerField(blank=True, help_text="How long a one-time purchase lasts. Empty = for life.", null=True)),
                ("trial_days", models.PositiveSmallIntegerField(default=0, help_text="0 = no free trial.")),
                ("gst_percent", models.DecimalField(decimal_places=2, default=Decimal("18.00"), max_digits=5)),
                ("is_public", models.BooleanField(default=True, help_text="Shown on the pricing page and at signup.")),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("razorpay_monthly_plan_id", models.CharField(blank=True, max_length=60)),
                ("razorpay_yearly_plan_id", models.CharField(blank=True, max_length=60)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="InvoiceCounter",
            fields=[
                ("financial_year", models.CharField(max_length=7, primary_key=True, serialize=False)),
                ("last_number", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("cycle", models.CharField(choices=CYCLES, max_length=10)),
                ("status", models.CharField(choices=[("pending", "Waiting for first payment"), ("trial", "Free trial"), ("active", "Active"), ("past_due", "Payment overdue (grace period)"), ("read_only", "Read-only (unpaid)"), ("cancelled", "Cancelled")], db_index=True, default="pending", max_length=12)),
                ("trial_ends_at", models.DateTimeField(blank=True, null=True)),
                ("paid_until", models.DateTimeField(blank=True, help_text="Access is paid up to here. Empty with ACTIVE = for life.", null=True)),
                ("grace_ends_at", models.DateTimeField(blank=True, null=True)),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("is_legacy", models.BooleanField(default=False)),
                ("razorpay_subscription_id", models.CharField(blank=True, db_index=True, max_length=60)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="subscription", to="organizations.organization")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="billing.plan")),
            ],
            options={"indexes": [models.Index(fields=["status", "paid_until"], name="billing_sub_status_paid_idx")]},
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.CharField(blank=True, max_length=30, null=True, unique=True)),
                ("status", models.CharField(choices=[("draft", "Awaiting payment"), ("paid", "Paid"), ("failed", "Failed"), ("void", "Cancelled")], db_index=True, default="draft", max_length=10)),
                ("plan_name", models.CharField(max_length=80)),
                ("cycle", models.CharField(choices=CYCLES, max_length=10)),
                ("period_start", models.DateTimeField()),
                ("period_end", models.DateTimeField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("gst_percent", models.DecimalField(decimal_places=2, max_digits=5)),
                ("gst_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("total", models.DecimalField(decimal_places=2, max_digits=10)),
                ("billed_name", models.CharField(max_length=255)),
                ("billed_email", models.EmailField(blank=True, max_length=254)),
                ("billed_address", models.TextField(blank=True)),
                ("billed_gstin", models.CharField(blank=True, max_length=15)),
                ("razorpay_order_id", models.CharField(blank=True, db_index=True, max_length=60)),
                ("razorpay_payment_id", models.CharField(blank=True, max_length=60, null=True, unique=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="billing.subscription")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
