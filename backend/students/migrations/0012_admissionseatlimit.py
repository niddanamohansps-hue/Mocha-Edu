import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0001_initial"),
        ("students", "0011_application_documents_reminded"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionSeatLimit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("academic_year", models.CharField(max_length=20)),
                ("seats", models.PositiveIntegerField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "level",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admission_seat_limits",
                        to="academics.academiclevel",
                    ),
                ),
            ],
            options={"ordering": ["academic_year", "level__order", "level__name"]},
        ),
        migrations.AddConstraint(
            model_name="admissionseatlimit",
            constraint=models.UniqueConstraint(fields=("academic_year", "level"), name="uniq_admission_seat_limit"),
        ),
    ]
