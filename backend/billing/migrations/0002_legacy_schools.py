"""
Schools that existed before billing keep full access: each gets an active "legacy" subscription on a
hidden plan, never billed automatically. The platform owner moves them to a real plan when agreed.
"""
from django.db import migrations

LEGACY_CODE = "legacy"


def forwards(apps, schema_editor):
    if schema_editor.connection.schema_name != "public":
        return
    Organization = apps.get_model("organizations", "Organization")
    Plan = apps.get_model("billing", "Plan")
    Subscription = apps.get_model("billing", "Subscription")
    schools = Organization.objects.exclude(schema_name="public")
    if not schools.exists():
        return
    plan, _ = Plan.objects.get_or_create(
        code=LEGACY_CODE,
        defaults={
            "name": "Existing school (before billing)",
            "description": "Full access, not billed automatically.",
            "is_public": False,
            "sort_order": 999,
        },
    )
    for school in schools:
        if not Subscription.objects.filter(organization=school).exists():
            Subscription.objects.create(
                organization=school, plan=plan, cycle="yearly", status="active", is_legacy=True, paid_until=None,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
        ("organizations", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
