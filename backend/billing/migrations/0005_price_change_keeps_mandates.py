from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("billing", "0004_gst_split")]

    operations = [
        migrations.AddField(model_name="plan", name="razorpay_monthly_amount",
                            field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="plan", name="razorpay_yearly_amount",
                            field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="subscription", name="autopay_amount_paise",
                            field=models.PositiveIntegerField(blank=True, null=True)),
    ]
