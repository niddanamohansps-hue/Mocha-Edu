import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0010_exammarkchange_moderation_kind"),
        ("students", "0009_compliance_blank_defaults"),
    ]

    operations = [
        migrations.CreateModel(
            name="MalpracticeCase",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("description", models.TextField(help_text="What happened")),
                (
                    "evidence_notes",
                    models.TextField(blank=True, help_text="What was found: items, witnesses, answer-sheet notes"),
                ),
                ("reported_by_user_id", models.UUIDField(blank=True, null=True)),
                ("reported_by_name", models.CharField(blank=True, max_length=150)),
                (
                    "status",
                    models.CharField(
                        choices=[("reported", "Reported"), ("decided", "Decided")],
                        db_index=True,
                        default="reported",
                        max_length=10,
                    ),
                ),
                (
                    "decision",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("dismissed", "Dismissed, no action"),
                            ("warning", "Warning, marks stand"),
                            ("marks_cancelled", "This paper's marks cancelled"),
                            ("all_papers_cancelled", "All papers in this examination cancelled"),
                        ],
                        max_length=20,
                    ),
                ),
                ("decision_notes", models.TextField(blank=True)),
                ("decided_by_user_id", models.UUIDField(blank=True, null=True)),
                ("decided_by_name", models.CharField(blank=True, max_length=150)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "examination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="malpractice_cases",
                        to="examinations.examination",
                    ),
                ),
                (
                    "schedule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="malpractice_cases",
                        to="examinations.examschedule",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="malpractice_cases",
                        to="students.student",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="malpracticecase",
            constraint=models.UniqueConstraint(fields=("schedule", "student"), name="uniq_malpractice_case_per_paper"),
        ),
    ]
