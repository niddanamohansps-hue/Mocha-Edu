import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
        ("timetable", "0002_period_academic_year_ref_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ItemCategory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name_plural": "item categories", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="StockLocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "room",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="timetable.room",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Item",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sku", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=200)),
                (
                    "unit",
                    models.CharField(help_text="Unit of measure, e.g. pcs, box, kg, litre", max_length=20),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "reorder_level",
                    models.DecimalField(
                        decimal_places=3,
                        default=Decimal("0"),
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="items",
                        to="inventory.itemcategory",
                    ),
                ),
            ],
            options={"ordering": ["name", "sku"]},
        ),
        migrations.CreateModel(
            name="StockLevel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=12)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="levels", to="inventory.item"
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="levels",
                        to="inventory.stocklocation",
                    ),
                ),
            ],
            options={"ordering": ["item__name", "location__name"]},
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("receive", "Received"),
                            ("issue", "Issued"),
                            ("return", "Returned"),
                            ("adjust_in", "Adjusted up"),
                            ("adjust_out", "Adjusted down"),
                            ("write_off", "Written off"),
                            ("transfer_out", "Transferred out"),
                            ("transfer_in", "Transferred in"),
                            ("reversal", "Reversal"),
                        ],
                        max_length=20,
                    ),
                ),
                ("quantity_delta", models.DecimalField(decimal_places=3, max_digits=12)),
                ("balance_after", models.DecimalField(decimal_places=3, max_digits=12)),
                ("unit_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("issued_to_note", models.CharField(blank=True, max_length=255)),
                ("transfer_group", models.UUIDField(blank=True, db_index=True, null=True)),
                ("recorded_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "issued_to_staff",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="staff.staffmember",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="inventory.item"
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="movements",
                        to="inventory.stocklocation",
                    ),
                ),
                (
                    "reverses",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reversal",
                        to="inventory.stockmovement",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.CheckConstraint(
                condition=models.Q(("reorder_level__gte", 0)), name="inventory_item_reorder_nonneg"
            ),
        ),
        migrations.AddConstraint(
            model_name="stocklevel",
            constraint=models.UniqueConstraint(fields=("item", "location"), name="inventory_stocklevel_unique"),
        ),
        migrations.AddConstraint(
            model_name="stocklevel",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gte", 0)), name="inventory_stocklevel_nonneg"
            ),
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["item", "-created_at"], name="inventory_move_item_idx"),
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["location", "-created_at"], name="inventory_move_location_idx"),
        ),
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity_delta", 0), _negated=True), name="inventory_move_delta_nonzero"
            ),
        ),
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.CheckConstraint(
                condition=models.Q(("balance_after__gte", 0)), name="inventory_move_balance_nonneg"
            ),
        ),
    ]
