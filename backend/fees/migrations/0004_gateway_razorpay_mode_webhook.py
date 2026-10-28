from django.db import migrations, models

GATEWAY_CHOICES = [("esewa", "eSewa"), ("khalti", "Khalti"), ("razorpay", "Razorpay")]


class Migration(migrations.Migration):

    dependencies = [
        ("fees", "0003_tenantpaymentgatewayconfig_onlinepaymentorder"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenantpaymentgatewayconfig",
            name="gateway",
            field=models.CharField(choices=GATEWAY_CHOICES, max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name="onlinepaymentorder",
            name="gateway",
            field=models.CharField(choices=GATEWAY_CHOICES, default="esewa", max_length=20),
        ),
        migrations.AddField(
            model_name="tenantpaymentgatewayconfig",
            name="encrypted_webhook_secret",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.AddField(
            model_name="tenantpaymentgatewayconfig",
            name="mode",
            field=models.CharField(choices=[("test", "Test"), ("live", "Live")], default="test", max_length=10),
        ),
        migrations.AddField(
            model_name="onlinepaymentorder",
            name="gateway_session_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255),
        ),
    ]
