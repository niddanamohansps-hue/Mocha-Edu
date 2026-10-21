from datetime import timedelta

from django.db import migrations

RESERVING = ["PENDING", "PAID", "PROVISIONING", "PROVISIONING_FAILED"]
LEGACY_TTL = timedelta(minutes=60)


def migrate_states(apps, schema_editor):
    """
    Map the old three-state rows onto the state machine so the one-reservation-per-subdomain
    constraint (next migration) can be added.

    * COMPLETED with an institution -> PROVISIONED (password discarded).
    * COMPLETED with no institution  -> PROVISIONING_FAILED, so a paid signup that never got its
      institution becomes visible and retryable instead of looking finished.
    * PENDING                        -> expires 60 minutes after creation; the stale ones EXPIRE.
    * Any subdomain still reserved by more than one row keeps its newest row; older ones EXPIRE.
    """
    Payment = apps.get_model("payments", "Payment")
    Organization = apps.get_model("organizations", "Organization")
    from django.utils import timezone

    now = timezone.now()
    existing_schemas = set(Organization.objects.values_list("schema_name", flat=True))

    for payment in Payment.objects.filter(status="COMPLETED"):
        if payment.subdomain in existing_schemas:
            payment.status = "PROVISIONED"
            payment.provisioned_at = payment.updated_at
            payment.password = ""
        else:
            payment.status = "PROVISIONING_FAILED"
            payment.failure_code = "legacy_no_institution"
        payment.paid_at = payment.updated_at
        payment.save(update_fields=["status", "provisioned_at", "password", "failure_code", "paid_at"])

    for payment in Payment.objects.filter(status="PENDING"):
        payment.expires_at = payment.created_at + LEGACY_TTL
        payment.status = "PENDING" if payment.expires_at > now else "EXPIRED"
        payment.save(update_fields=["expires_at", "status"])

    seen = set()
    for payment in Payment.objects.filter(status__in=RESERVING).order_by("-created_at", "-id"):
        if payment.subdomain in seen:
            payment.status = "EXPIRED"
            payment.failure_code = payment.failure_code or "legacy_duplicate_subdomain"
            payment.save(update_fields=["status", "failure_code"])
        else:
            seen.add(payment.subdomain)


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
        ("payments", "0003_signup_payment_state_machine"),
    ]

    operations = [
        # Not reversible: the old states cannot be restored faithfully.
        migrations.RunPython(migrate_states, migrations.RunPython.noop),
    ]
