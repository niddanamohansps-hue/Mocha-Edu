from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0011_malpracticecase"),
    ]

    operations = [
        migrations.AddField(
            model_name="examseat",
            name="hall_status",
            field=models.CharField(
                blank=True, choices=[("present", "Present"), ("absent", "Absent")], default="", max_length=10
            ),
        ),
        migrations.AddField(
            model_name="examseat",
            name="hall_marked_by_user_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="examseat",
            name="hall_marked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
