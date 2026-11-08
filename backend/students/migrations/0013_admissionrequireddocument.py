import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0001_initial"),
        ("students", "0012_admissionseatlimit"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionRequiredDocument",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "document_type",
                    models.CharField(
                        choices=[
                            ("birth_certificate", "Birth Certificate"),
                            ("transfer_certificate", "Transfer Certificate (TC)"),
                            ("previous_marksheet", "Previous Academic Marksheet / Report Card"),
                            ("photo", "Passport Size Photograph"),
                            ("address_proof", "Address Proof"),
                            ("medical_record", "Medical Record"),
                            ("other", "Other Document"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "level",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admission_required_documents",
                        to="academics.academiclevel",
                    ),
                ),
            ],
            options={"ordering": ["level__order", "level__name", "document_type"]},
        ),
        migrations.AddConstraint(
            model_name="admissionrequireddocument",
            constraint=models.UniqueConstraint(fields=("level", "document_type"), name="uniq_required_doc_per_level"),
        ),
        migrations.AddConstraint(
            model_name="admissionrequireddocument",
            constraint=models.UniqueConstraint(
                condition=models.Q(("level__isnull", True)), fields=("document_type",), name="uniq_required_doc_all_classes"
            ),
        ),
    ]
