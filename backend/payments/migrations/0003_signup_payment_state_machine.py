import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
        ("payments", "0002_alter_payment_password"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="paid_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="gateway_reference",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="payment",
            name="provisioned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="provisioning_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="payment",
            name="failure_code",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="payment",
            name="organization",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="signup_payment",
                to="organizations.organization",
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="password",
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AlterField(
            model_name="payment",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("PAID", "Paid"),
                    ("PROVISIONING", "Provisioning"),
                    ("PROVISIONED", "Provisioned"),
                    ("PROVISIONING_FAILED", "Provisioning failed"),
                    ("EXPIRED", "Expired"),
                    ("FAILED", "Failed"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
