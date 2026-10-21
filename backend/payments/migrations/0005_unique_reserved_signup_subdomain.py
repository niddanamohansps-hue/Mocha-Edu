from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_migrate_legacy_payment_states"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=Q(("status__in", ["PENDING", "PAID", "PROVISIONING", "PROVISIONING_FAILED"])),
                fields=("subdomain",),
                name="uniq_reserved_signup_subdomain",
            ),
        ),
    ]
