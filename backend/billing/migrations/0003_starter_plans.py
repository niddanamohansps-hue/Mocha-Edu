"""
Three starting plans so signup works out of the box. The prices are PLACEHOLDERS: the platform owner sets
the real ones in the Django admin (Billing > Plans). Existing plans with the same code are left alone.
"""
from decimal import Decimal

from django.db import migrations

PLANS = [
    {
        "code": "starter", "name": "Starter", "sort_order": 1, "student_limit": 300, "trial_days": 0,
        "description": "For small schools.",
        "features": ["Up to 300 students", "All core modules", "Parent & student portals", "Email support"],
        "monthly_price": Decimal("1999.00"), "yearly_price": Decimal("19990.00"),
        "one_time_price": Decimal("49990.00"), "one_time_validity_days": 3 * 365,
    },
    {
        "code": "professional", "name": "Professional", "sort_order": 2, "student_limit": 1500, "trial_days": 14,
        "description": "For growing schools.",
        "features": ["Up to 1,500 students", "Everything in Starter", "Online fee collection", "Priority support"],
        "monthly_price": Decimal("4999.00"), "yearly_price": Decimal("49990.00"),
        "one_time_price": Decimal("124990.00"), "one_time_validity_days": 3 * 365,
    },
    {
        "code": "enterprise", "name": "Enterprise", "sort_order": 3, "student_limit": None, "trial_days": 14,
        "description": "For school groups and large campuses.",
        "features": ["Unlimited students", "Everything in Professional", "Dedicated support"],
        "monthly_price": Decimal("9999.00"), "yearly_price": Decimal("99990.00"),
        "one_time_price": None, "one_time_validity_days": None,
    },
]


def forwards(apps, schema_editor):
    if schema_editor.connection.schema_name != "public":
        return
    Plan = apps.get_model("billing", "Plan")
    for spec in PLANS:
        Plan.objects.get_or_create(code=spec["code"], defaults={k: v for k, v in spec.items() if k != "code"})


class Migration(migrations.Migration):

    dependencies = [("billing", "0002_legacy_schools")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
