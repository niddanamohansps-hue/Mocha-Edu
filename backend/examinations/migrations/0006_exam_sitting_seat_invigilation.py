import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0005_stage_c_components_and_weightage"),
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
        ("students", "0009_compliance_blank_defaults"),
        ("timetable", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamSitting",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "examination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sittings",
                        to="examinations.examination",
                    ),
                ),
            ],
            options={"ordering": ["date", "start_time"]},
        ),
        migrations.CreateModel(
            name="ExamSeat",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("seat_number", models.PositiveIntegerField()),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="exam_seats", to="timetable.room"
                    ),
                ),
                (
                    "schedule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seats",
                        to="examinations.examschedule",
                    ),
                ),
                (
                    "sitting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seats",
                        to="examinations.examsitting",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="exam_seats", to="students.student"
                    ),
                ),
            ],
            options={"ordering": ["room__name", "seat_number"]},
        ),
        migrations.CreateModel(
            name="ExamInvigilation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "role",
                    models.CharField(
                        choices=[("chief", "Chief invigilator"), ("invigilator", "Invigilator"), ("relief", "Relief")],
                        default="invigilator",
                        max_length=20,
                    ),
                ),
                ("created_by_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exam_invigilations",
                        to="timetable.room",
                    ),
                ),
                (
                    "sitting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invigilations",
                        to="examinations.examsitting",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exam_invigilations",
                        to="staff.staffmember",
                    ),
                ),
            ],
            options={"ordering": ["room__name", "role"]},
        ),
        migrations.AddConstraint(
            model_name="examsitting",
            constraint=models.UniqueConstraint(fields=("examination", "date", "start_time"), name="uniq_exam_sitting_slot"),
        ),
        migrations.AddConstraint(
            model_name="examseat",
            constraint=models.UniqueConstraint(fields=("sitting", "student"), name="uniq_exam_seat_student"),
        ),
        migrations.AddConstraint(
            model_name="examseat",
            constraint=models.UniqueConstraint(fields=("sitting", "room", "seat_number"), name="uniq_exam_seat_position"),
        ),
        migrations.AddConstraint(
            model_name="examinvigilation",
            constraint=models.UniqueConstraint(fields=("sitting", "staff"), name="uniq_exam_duty_staff_per_sitting"),
        ),
    ]
