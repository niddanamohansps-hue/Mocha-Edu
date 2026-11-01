from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0006_exam_sitting_seat_invigilation"),
    ]

    operations = [
        migrations.AddField(
            model_name="examination",
            name="date_sheet_published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="examination",
            name="date_sheet_version",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
