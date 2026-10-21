from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0005_unique_reserved_signup_subdomain"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="gateway_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="attention_notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
