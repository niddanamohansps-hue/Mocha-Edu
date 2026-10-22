import uuid
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalaryComponent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("code", models.CharField(max_length=30, unique=True)),
                (
                    "kind",
                    models.CharField(choices=[("earning", "Earning"), ("deduction", "Deduction")], max_length=10),
                ),
                (
                    "calculation",
                    models.CharField(
                        choices=[("fixed", "Fixed amount"), ("percent_of_basic", "Percentage of basic salary")],
                        default="fixed",
                        max_length=20,
                    ),
                ),
                ("default_value", models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=12)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["kind", "sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="PayrollSettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("round_to_whole_rupee", models.BooleanField(default=True)),
                ("require_separate_approver", models.BooleanField(default=True)),
                ("updated_by_user_id", models.UUIDField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="StaffSalary",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("basic_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("effective_from", models.DateField()),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="salaries", to="staff.staffmember"
                    ),
                ),
            ],
            options={"ordering": ["-effective_from", "-created_at"]},
        ),
        migrations.CreateModel(
            name="StaffSalaryComponent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("value", models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ("effective_from", models.DateField()),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "component",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="payroll.salarycomponent",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="salary_components",
                        to="staff.staffmember",
                    ),
                ),
            ],
            options={"ordering": ["component__kind", "component__sort_order", "-effective_from"]},
        ),
        migrations.AddConstraint(
            model_name="salarycomponent",
            constraint=models.CheckConstraint(
                condition=models.Q(("default_value__gte", 0)), name="payroll_component_value_nonneg"
            ),
        ),
        migrations.AddConstraint(
            model_name="salarycomponent",
            constraint=models.CheckConstraint(
                condition=models.Q(("calculation", "percent_of_basic"), _negated=True)
                | models.Q(("default_value__lte", 100)),
                name="payroll_component_percent_max",
            ),
        ),
        migrations.AddConstraint(
            model_name="payrollsettings",
            constraint=models.CheckConstraint(
                condition=models.Q(("singleton", True)), name="payroll_settings_singleton_true"
            ),
        ),
        migrations.AddConstraint(
            model_name="staffsalary",
            constraint=models.UniqueConstraint(fields=("staff", "effective_from"), name="payroll_salary_one_per_date"),
        ),
        migrations.AddConstraint(
            model_name="staffsalary",
            constraint=models.CheckConstraint(
                condition=models.Q(("basic_amount__gt", 0)), name="payroll_salary_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="staffsalarycomponent",
            constraint=models.UniqueConstraint(
                condition=models.Q(("effective_to__isnull", True)),
                fields=("staff", "component"),
                name="payroll_staffcomp_one_open",
            ),
        ),
        migrations.AddConstraint(
            model_name="staffsalarycomponent",
            constraint=models.CheckConstraint(
                condition=models.Q(("effective_to__isnull", True), ("effective_to__gte", models.F("effective_from")), _connector="OR"),
                name="payroll_staffcomp_dates_ordered",
            ),
        ),
        migrations.AddConstraint(
            model_name="staffsalarycomponent",
            constraint=models.CheckConstraint(
                condition=models.Q(("value__isnull", True), ("value__gte", 0), _connector="OR"),
                name="payroll_staffcomp_value_nonneg",
            ),
        ),
    ]
