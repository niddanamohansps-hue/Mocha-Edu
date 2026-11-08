import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0013_supplementary_exams"),
        ("timetable", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamRoomReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scripts_collected", models.PositiveIntegerField()),
                ("incidents", models.TextField(blank=True)),
                ("submitted_by_user_id", models.UUIDField(blank=True, null=True)),
                ("submitted_by_name", models.CharField(blank=True, max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exam_room_reports",
                        to="timetable.room",
                    ),
                ),
                (
                    "sitting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="room_reports",
                        to="examinations.examsitting",
                    ),
                ),
            ],
            options={"ordering": ["sitting__date", "sitting__start_time", "room__name"]},
        ),
        migrations.AddConstraint(
            model_name="examroomreport",
            constraint=models.UniqueConstraint(fields=("sitting", "room"), name="uniq_exam_room_report"),
        ),
    ]
