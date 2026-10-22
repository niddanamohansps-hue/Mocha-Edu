import attendance.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0002_attendancesession_academic_year_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancesettings",
            name="weekly_off_days",
            field=models.JSONField(
                blank=True,
                default=attendance.models.default_weekly_off_days,
                help_text="Weekdays the school is closed every week: 0 = Monday ... 6 = Sunday.",
            ),
        ),
    ]
