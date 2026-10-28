import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("notifications", "0006_alertlog_enrollment_id_index")]

    operations = [
        migrations.CreateModel(
            name="PushSubscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.UUIDField(db_index=True)),
                ("endpoint", models.URLField(max_length=1000, unique=True)),
                ("p256dh", models.CharField(max_length=200)),
                ("auth", models.CharField(max_length=100)),
                ("user_agent", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("failures", models.PositiveSmallIntegerField(default=0)),
            ],
        ),
    ]
