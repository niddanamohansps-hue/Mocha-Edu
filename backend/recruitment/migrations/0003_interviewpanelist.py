import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recruitment", "0002_applicant_reference_access"),
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="InterviewPanelist",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "score",
                    models.DecimalField(blank=True, decimal_places=1, help_text="0 to 10", max_digits=4, null=True),
                ),
                ("feedback", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "interview",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="panelists",
                        to="recruitment.interview",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="interview_panels",
                        to="staff.staffmember",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="interviewpanelist",
            constraint=models.UniqueConstraint(fields=("interview", "staff"), name="uniq_panelist_per_interview"),
        ),
    ]
