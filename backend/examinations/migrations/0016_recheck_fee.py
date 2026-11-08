from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0015_report_card_style"),
    ]

    operations = [
        migrations.AddField(
            model_name="examinationsettings",
            name="recheck_fee",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="recheckrequest",
            name="fee_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="recheckrequest",
            name="fee_paid_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="recheckrequest",
            name="fee_received_by_user_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="recheckrequest",
            name="fee_reference",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
