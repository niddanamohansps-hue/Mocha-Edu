from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0016_recheck_fee"),
    ]

    operations = [
        migrations.AddField(
            model_name="recheckrequest",
            name="fee_refunded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="recheckrequest",
            name="fee_refund_reference",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
