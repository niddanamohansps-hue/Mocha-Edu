import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0003_calendarevent"),
        ("examinations", "0012_examseat_hall_status"),
        ("students", "0009_compliance_blank_defaults"),
    ]

    operations = [
        migrations.AddField(
            model_name="examination",
            name="supplementary_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="supplementaries",
                to="examinations.examination",
            ),
        ),
        migrations.CreateModel(
            name="SupplementaryCandidate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "reason",
                    models.CharField(choices=[("failed", "Failed"), ("absent", "Absent")], max_length=10),
                ),
                (
                    "original_percentage",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "examination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplementary_candidates",
                        to="examinations.examination",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplementary_candidacies",
                        to="students.student",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supplementary_candidacies",
                        to="academics.subject",
                    ),
                ),
            ],
            options={"ordering": ["subject__name", "student__enrollment_id"]},
        ),
        migrations.AddConstraint(
            model_name="supplementarycandidate",
            constraint=models.UniqueConstraint(fields=("examination", "student", "subject"), name="uniq_supplementary_candidate"),
        ),
    ]
