import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
        ("payments", "0006_reconciliation_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="plan",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="billing.plan"),
        ),
        migrations.AddField(
            model_name="payment",
            name="cycle",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name="payment",
            name="gateway",
            field=models.CharField(default="esewa", max_length=20),
        ),
        migrations.AddField(
            model_name="payment",
            name="gateway_order_id",
            field=models.CharField(blank=True, db_index=True, max_length=60),
        ),
    ]
