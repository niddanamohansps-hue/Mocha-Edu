import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
        ("inventory", "0002_suppliers_purchases"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssetCategory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name_plural": "asset categories", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Asset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "tag",
                    models.CharField(help_text="The school's asset tag number", max_length=50, unique=True),
                ),
                ("name", models.CharField(max_length=200)),
                ("serial_number", models.CharField(blank=True, max_length=100)),
                ("description", models.TextField(blank=True)),
                ("purchase_date", models.DateField(blank=True, null=True)),
                ("purchase_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                (
                    "condition",
                    models.CharField(
                        choices=[("new", "New"), ("good", "Good"), ("fair", "Fair"), ("poor", "Poor")],
                        default="good",
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("available", "Available"),
                            ("assigned", "Assigned"),
                            ("in_repair", "In repair"),
                            ("lost", "Lost"),
                            ("disposed", "Disposed"),
                        ],
                        default="available",
                        max_length=20,
                    ),
                ),
                ("disposed_at", models.DateTimeField(blank=True, null=True)),
                ("disposal_reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assets",
                        to="inventory.assetcategory",
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assets",
                        to="inventory.stocklocation",
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assets",
                        to="inventory.supplier",
                    ),
                ),
            ],
            options={"ordering": ["tag"]},
        ),
        migrations.CreateModel(
            name="AssetAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_by_user_id", models.UUIDField(blank=True, null=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("returned_by_user_id", models.UUIDField(blank=True, null=True)),
                (
                    "return_condition",
                    models.CharField(
                        blank=True,
                        choices=[("new", "New"), ("good", "Good"), ("fair", "Fair"), ("poor", "Poor")],
                        max_length=10,
                    ),
                ),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="inventory.asset",
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="inventory.stocklocation",
                    ),
                ),
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
            options={"ordering": ["-assigned_at", "-id"]},
        ),
        migrations.CreateModel(
            name="MaintenanceRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reason", models.CharField(max_length=255)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("opened_by_user_id", models.UUIDField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closed_by_user_id", models.UUIDField(blank=True, null=True)),
                ("cost", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("notes", models.CharField(blank=True, max_length=255)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="maintenance",
                        to="inventory.asset",
                    ),
                ),
            ],
            options={"ordering": ["-opened_at", "-id"]},
        ),
        migrations.CreateModel(
            name="AssetEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("registered", "Registered"),
                            ("assigned", "Assigned"),
                            ("returned", "Returned"),
                            ("moved", "Moved"),
                            ("sent_to_repair", "Sent to repair"),
                            ("repaired", "Repair completed"),
                            ("lost", "Marked lost"),
                            ("found", "Found"),
                            ("disposed", "Disposed"),
                        ],
                        max_length=20,
                    ),
                ),
                ("from_status", models.CharField(blank=True, max_length=20)),
                ("to_status", models.CharField(max_length=20)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="events", to="inventory.asset"
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="asset",
            index=models.Index(fields=["status"], name="inventory_asset_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="asset",
            constraint=models.CheckConstraint(
                condition=models.Q(("purchase_cost__isnull", True), ("purchase_cost__gte", 0), _connector="OR"),
                name="inventory_asset_cost_nonneg",
            ),
        ),
        migrations.AddConstraint(
            model_name="asset",
            constraint=models.CheckConstraint(
                condition=models.Q(("status", "disposed"), _negated=True)
                | models.Q(("disposed_at__isnull", False)),
                name="inventory_asset_disposed_dated",
            ),
        ),
        migrations.AddConstraint(
            model_name="assetassignment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("returned_at__isnull", True)),
                fields=("asset",),
                name="inventory_assign_one_open",
            ),
        ),
        migrations.AddConstraint(
            model_name="assetassignment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("staff__isnull", False),
                    ("location__isnull", False),
                    models.Q(("note", ""), _negated=True),
                    _connector="OR",
                ),
                name="inventory_assign_has_holder",
            ),
        ),
        migrations.AddConstraint(
            model_name="maintenancerecord",
            constraint=models.UniqueConstraint(
                condition=models.Q(("closed_at__isnull", True)),
                fields=("asset",),
                name="inventory_maint_one_open",
            ),
        ),
        migrations.AddConstraint(
            model_name="maintenancerecord",
            constraint=models.CheckConstraint(
                condition=models.Q(("cost__isnull", True), ("cost__gte", 0), _connector="OR"),
                name="inventory_maint_cost_nonneg",
            ),
        ),
        migrations.AddIndex(
            model_name="assetevent",
            index=models.Index(fields=["asset", "-created_at"], name="inventory_assetev_asset_idx"),
        ),
    ]
