import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("staff", "0002_leavetype_leaveapplication_leaveapproval_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="StaffDocumentType",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["order", "name"]},
        ),
        migrations.CreateModel(
            name="StaffDocumentItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("received", "Received"), ("waived", "Not needed")],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("received_on", models.DateField(blank=True, null=True)),
                ("file", models.FileField(blank=True, null=True, upload_to="staff_documents/%Y/%m/")),
                ("note", models.CharField(blank=True, max_length=500)),
                ("updated_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "document_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="items",
                        to="staff.staffdocumenttype",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_items",
                        to="staff.staffmember",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "name"]},
        ),
        migrations.AddConstraint(
            model_name="staffdocumentitem",
            constraint=models.UniqueConstraint(fields=("staff", "name"), name="uniq_staff_document_name"),
        ),
    ]
