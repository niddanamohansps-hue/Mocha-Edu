from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("billing", "0003_starter_plans")]

    operations = [
        migrations.AddField(model_name="subscription", name="billing_state",
                            field=models.CharField(blank=True, max_length=2)),
        migrations.AddField(model_name="subscription", name="billing_gstin",
                            field=models.CharField(blank=True, max_length=15)),
        migrations.AddField(model_name="invoice", name="place_of_supply",
                            field=models.CharField(blank=True, max_length=2)),
        migrations.AddField(model_name="invoice", name="cgst_amount",
                            field=models.DecimalField(decimal_places=2, default=0, max_digits=10)),
        migrations.AddField(model_name="invoice", name="sgst_amount",
                            field=models.DecimalField(decimal_places=2, default=0, max_digits=10)),
        migrations.AddField(model_name="invoice", name="igst_amount",
                            field=models.DecimalField(decimal_places=2, default=0, max_digits=10)),
    ]
