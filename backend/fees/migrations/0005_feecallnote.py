import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fees", "0004_gateway_razorpay_mode_webhook"),
        ("students", "0013_admissionrequireddocument"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeeCallNote",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("reached", "Spoke to the family"),
                            ("no_answer", "No answer"),
                            ("promised", "Promised to pay"),
                            ("refused", "Refused or disputes the fee"),
                        ],
                        max_length=20,
                    ),
                ),
                ("note", models.CharField(max_length=500)),
                ("promise_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("promise_date", models.DateField(blank=True, null=True)),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_by_name", models.CharField(blank=True, max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fee_call_notes",
                        to="students.student",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="feecallnote",
            index=models.Index(fields=["student", "-created_at"], name="feecall_student_idx"),
        ),
    ]
