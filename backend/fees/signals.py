from django.db.models.signals import post_migrate
from django.dispatch import receiver

DEFAULT_FEE_HEADS = [
    "Tuition",
    "Admission",
    "Transport",
    "Library",
    "Examination",
    "Activity/Miscellaneous",
]


@receiver(post_migrate)
def seed_default_fee_heads(sender, **kwargs):
    if sender.name != "fees":
        return

    from django.db import connection

    from .models import FeeHead

    # Mirrors roles.signals.seed_roles exactly - FeeHead is tenant-specific
    # reference data, never seeded in the public schema.
    if connection.schema_name == "public":
        print("[FEES] Skipping fee head seeding in public schema (fee heads are tenant-specific)")
        return

    print(f"[FEES] Seeding default fee heads for schema: {connection.schema_name}")

    for name in DEFAULT_FEE_HEADS:
        FeeHead.objects.get_or_create(name=name)
