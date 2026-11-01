import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_pushsubscription"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppOutboxEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("to_phone", models.CharField(max_length=20)),
                ("template", models.CharField(max_length=100)),
                ("language", models.CharField(default="en", max_length=10)),
                ("params", models.JSONField(default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("retrying", "Retrying"), ("sent", "Sent"), ("failed", "Failed")],
                        db_index=True,
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("max_attempts", models.PositiveIntegerField(default=3)),
                ("last_error", models.TextField(blank=True)),
                ("error_type", models.CharField(blank=True, max_length=10)),
                ("next_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("provider_message_id", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "indexes": [models.Index(fields=["status", "updated_at"], name="wa_outbox_status_updated_idx")],
            },
        ),
        migrations.AddField(
            model_name="alertlog",
            name="whatsapp_event",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="notifications.whatsappoutboxevent",
            ),
        ),
    ]
