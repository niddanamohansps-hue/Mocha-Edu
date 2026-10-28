from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_notificationsettings_low_stock_alerts_enabled"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alertlog",
            name="enrollment_id",
            field=models.CharField(blank=True, db_index=True, max_length=50),
        ),
    ]
