import uuid

import django.db.models.deletion
from django.db import migrations, models


def absent_marks_to_attendance(apps, schema_editor):
    ExamMark = apps.get_model("examinations", "ExamMark")
    ExamMark.objects.filter(is_absent=True).update(attendance="absent")


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0003_two_person_publishing"),
    ]

    operations = [
        migrations.AddField(
            model_name="exammark",
            name="attendance",
            field=models.CharField(
                choices=[("present", "Present"), ("absent", "Absent"), ("medical", "Absent (medical)"),
                         ("malpractice", "Malpractice"), ("exempt", "Exempt")],
                default="present", max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="exammark",
            name="grace_marks",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=6),
        ),
        migrations.RunPython(absent_marks_to_attendance, migrations.RunPython.noop),
        migrations.CreateModel(
            name="ExamMarkChange",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("entry", "Entered"), ("correction", "Corrected"), ("import", "Imported"),
                                                   ("grace", "Grace marks"), ("recheck", "Recheck")], max_length=12)),
                ("old_marks", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("new_marks", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("old_attendance", models.CharField(blank=True, max_length=12)),
                ("new_attendance", models.CharField(blank=True, max_length=12)),
                ("old_grace", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("new_grace", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("reason", models.CharField(blank=True, max_length=500)),
                ("changed_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("mark", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="changes", to="examinations.exammark")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["mark", "-created_at"], name="exammarkchange_mark_idx")],
            },
        ),
        migrations.CreateModel(
            name="RecheckRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "Waiting"), ("accepted", "Accepted"), ("rejected", "Rejected")],
                                            default="pending", max_length=10)),
                ("reason", models.CharField(max_length=1000)),
                ("original_marks", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("revised_marks", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("decision_comment", models.CharField(blank=True, max_length=1000)),
                ("requested_by_user_id", models.UUIDField(blank=True, null=True)),
                ("decided_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("mark", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rechecks", to="examinations.exammark")),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("mark",),
                                                        name="exam_recheck_one_pending_per_mark")],
            },
        ),
    ]
