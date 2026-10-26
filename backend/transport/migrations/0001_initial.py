import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("fees", "0003_tenantpaymentgatewayconfig_onlinepaymentorder"),
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
        ("students", "0007_admissiondocument_scan_details_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Vehicle",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("registration_number", models.CharField(max_length=30, unique=True)),
                ("name", models.CharField(blank=True, max_length=100)),
                ("make_model", models.CharField(blank=True, max_length=100)),
                (
                    "capacity",
                    models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)]),
                ),
                ("insurance_expiry", models.DateField(blank=True, null=True)),
                ("fitness_expiry", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["registration_number"]},
        ),
        migrations.CreateModel(
            name="Driver",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("full_name", models.CharField(max_length=150)),
                (
                    "role",
                    models.CharField(choices=[("driver", "Driver"), ("helper", "Helper")], default="driver", max_length=10),
                ),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("license_number", models.CharField(blank=True, max_length=50)),
                ("license_expiry", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "staff",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff.staffmember",
                    ),
                ),
            ],
            options={"ordering": ["full_name"]},
        ),
        migrations.CreateModel(
            name="Route",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "driver",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="driven_routes",
                        to="transport.driver",
                    ),
                ),
                (
                    "helper",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="helped_routes",
                        to="transport.driver",
                    ),
                ),
                (
                    "vehicle",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="routes",
                        to="transport.vehicle",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="RouteStop",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                (
                    "sequence",
                    models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)]),
                ),
                ("pickup_time", models.TimeField(blank=True, null=True)),
                ("drop_time", models.TimeField(blank=True, null=True)),
                (
                    "monthly_fee",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "route",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="stops", to="transport.route"
                    ),
                ),
            ],
            options={"ordering": ["route", "sequence"]},
        ),
        migrations.CreateModel(
            name="StudentTransport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transport_assignments",
                        to="students.student",
                    ),
                ),
                (
                    "stop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="transport.routestop",
                    ),
                ),
            ],
            options={"ordering": ["-start_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="TransportBill",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("month", models.DateField(help_text="The first day of the month that was billed.")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("billed_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transport_bills",
                        to="students.student",
                    ),
                ),
                (
                    "student_fee",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transport_bill",
                        to="fees.studentfee",
                    ),
                ),
                (
                    "stop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="bills", to="transport.routestop"
                    ),
                ),
            ],
            options={"ordering": ["-month", "student"]},
        ),
        migrations.AddConstraint(
            model_name="routestop",
            constraint=models.UniqueConstraint(fields=("route", "sequence"), name="transport_stop_unique_sequence"),
        ),
        migrations.AddConstraint(
            model_name="routestop",
            constraint=models.UniqueConstraint(fields=("route", "name"), name="transport_stop_unique_name"),
        ),
        migrations.AddConstraint(
            model_name="routestop",
            constraint=models.CheckConstraint(
                condition=models.Q(("monthly_fee__gte", 0)), name="transport_stop_fee_not_negative"
            ),
        ),
        migrations.AddConstraint(
            model_name="studenttransport",
            constraint=models.UniqueConstraint(
                condition=models.Q(("end_date__isnull", True)),
                fields=("student",),
                name="transport_one_open_seat_per_student",
            ),
        ),
        migrations.AddConstraint(
            model_name="studenttransport",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_date__isnull", True), ("end_date__gte", models.F("start_date")), _connector="OR"),
                name="transport_seat_end_after_start",
            ),
        ),
        migrations.AddConstraint(
            model_name="transportbill",
            constraint=models.UniqueConstraint(fields=("student", "month"), name="transport_one_bill_per_student_month"),
        ),
    ]
