import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="low_stock_notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200, unique=True)),
                ("contact_name", models.CharField(blank=True, max_length=150)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("address", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Purchase",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "reference",
                    models.CharField(blank=True, help_text="Supplier invoice or order number", max_length=100),
                ),
                ("purchase_date", models.DateField()),
                ("notes", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[("received", "Received"), ("cancelled", "Cancelled")],
                        default="received",
                        max_length=20,
                    ),
                ),
                ("total_cost", models.DecimalField(decimal_places=2, max_digits=14)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancellation_reason", models.CharField(blank=True, max_length=255)),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchases",
                        to="inventory.stocklocation",
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchases",
                        to="inventory.supplier",
                    ),
                ),
            ],
            options={"ordering": ["-purchase_date", "-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="PurchaseLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=12)),
                ("unit_cost", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_lines",
                        to="inventory.item",
                    ),
                ),
                (
                    "movement",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_line",
                        to="inventory.stockmovement",
                    ),
                ),
                (
                    "purchase",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="inventory.purchase"
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="purchase",
            index=models.Index(fields=["supplier", "-purchase_date"], name="inventory_purch_supplier_idx"),
        ),
        migrations.AddConstraint(
            model_name="purchase",
            constraint=models.CheckConstraint(
                condition=models.Q(("total_cost__gte", 0)), name="inventory_purchase_total_nonneg"
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseline",
            constraint=models.UniqueConstraint(fields=("purchase", "item"), name="inventory_purchaseline_unique_item"),
        ),
        migrations.AddConstraint(
            model_name="purchaseline",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gt", 0)), name="inventory_purchaseline_qty_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseline",
            constraint=models.CheckConstraint(
                condition=models.Q(("unit_cost__gte", 0)), name="inventory_purchaseline_cost_nonneg"
            ),
        ),
    ]
