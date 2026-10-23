import uuid
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
        ("payroll", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PayrollRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("year", models.PositiveSmallIntegerField()),
                ("month", models.PositiveSmallIntegerField()),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("calculated", "Calculated"),
                            ("approved", "Approved"),
                            ("paid", "Paid"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="draft",
                        max_length=12,
                    ),
                ),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("working_days", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("weekly_off_days", models.JSONField(blank=True, default=list)),
                ("round_to_whole_rupee", models.BooleanField(default=True)),
                ("calculation_notes", models.JSONField(blank=True, default=dict)),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("prepared_by_user_id", models.UUIDField(blank=True, null=True)),
                ("calculated_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by_user_id", models.UUIDField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("paid_on", models.DateField(blank=True, null=True)),
                ("paid_by_user_id", models.UUIDField(blank=True, null=True)),
                (
                    "payment_method",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("bank_transfer", "Bank transfer"),
                            ("cash", "Cash"),
                            ("cheque", "Cheque"),
                            ("other", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                ("payment_reference", models.CharField(blank=True, max_length=100)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_by_user_id", models.UUIDField(blank=True, null=True)),
                ("cancellation_reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-year", "-month", "-created_at"]},
        ),
        migrations.CreateModel(
            name="Payslip",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("employee_id", models.CharField(max_length=50)),
                ("staff_name", models.CharField(max_length=200)),
                ("designation", models.CharField(blank=True, max_length=100)),
                ("department", models.CharField(blank=True, max_length=100)),
                ("basic_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("gross_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("deductions_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("net_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("working_days", models.PositiveSmallIntegerField()),
                ("unpaid_days", models.DecimalField(decimal_places=1, default=Decimal("0"), max_digits=5)),
                ("unmarked_days", models.DecimalField(decimal_places=1, default=Decimal("0"), max_digits=5)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="payslips", to="payroll.payrollrun"
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="payslips", to="staff.staffmember"
                    ),
                ),
            ],
            options={"ordering": ["staff_name", "employee_id"]},
        ),
        migrations.CreateModel(
            name="PayslipLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=30)),
                ("name", models.CharField(max_length=100)),
                (
                    "kind",
                    models.CharField(
                        choices=[("basic", "Basic salary"), ("earning", "Earning"), ("deduction", "Deduction")],
                        max_length=10,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("detail", models.CharField(blank=True, max_length=255)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "payslip",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="payroll.payslip"
                    ),
                ),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="PayrollAdjustment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "kind",
                    models.CharField(choices=[("earning", "Earning"), ("deduction", "Deduction")], max_length=10),
                ),
                ("name", models.CharField(max_length=100)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("reason", models.CharField(max_length=255)),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="adjustments",
                        to="payroll.payrollrun",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payroll_adjustments",
                        to="staff.staffmember",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="payrollrun",
            constraint=models.CheckConstraint(
                condition=models.Q(("month__gte", 1), ("month__lte", 12)), name="payroll_run_month_range"
            ),
        ),
        migrations.AddConstraint(
            model_name="payrollrun",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "cancelled"), _negated=True),
                fields=("year", "month"),
                name="payroll_run_one_per_month",
            ),
        ),
        migrations.AddConstraint(
            model_name="payslip",
            constraint=models.UniqueConstraint(fields=("run", "staff"), name="payroll_payslip_one_per_run"),
        ),
        migrations.AddConstraint(
            model_name="payslipline",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gte", 0)), name="payroll_line_amount_nonneg"),
        ),
        migrations.AddConstraint(
            model_name="payrolladjustment",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="payroll_adjustment_positive"),
        ),
    ]
