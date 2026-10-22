from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0004_notificationsettings_alertlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationsettings",
            name="low_stock_alerts_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
