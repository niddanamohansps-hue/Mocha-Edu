from decimal import Decimal
from django.db import connection
from django.db.models.signals import post_migrate
from django.dispatch import receiver

DEFAULT_EXPENSE_CATEGORIES = [
    ("Transport & Fuel", "TRANS", "Bus and van diesel, vehicle servicing, RTO tax and repairs", 1),
    ("Electricity & Utilities", "UTIL", "Electricity bills, water supply, generator diesel, broadband", 2),
    ("Repairs & Maintenance", "MAINT", "Campus plumbing, carpentry, whitewash and electrical upkeep", 3),
    ("Academic & Exam Supplies", "ACAD", "Chalk, answer booklets, printing question papers, lab consumables", 4),
    ("Staff Welfare & Refreshments", "WELFARE", "Daily staff tea, snacks, meetings and teacher celebrations", 5),
    ("Printing & Stationery", "PRINT", "Registers, envelopes, courier, office stationery and stamp duty", 6),
    ("Events & Sports", "EVENT", "Annual function, sports day, student prizes and audio/tent rentals", 7),
    ("Miscellaneous & Petty Cash", "MISC", "Incidental petty expenses and unforeseen campus repairs", 8),
]


@receiver(post_migrate)
def seed_default_expense_data(sender, **kwargs):
    if sender.name != "expenses":
        return

    # Skip public schema (tenant-specific data only)
    if connection.schema_name == "public":
        print("[EXPENSES] Skipping expense seeding in public schema (tenant-specific)")
        return

    print(f"[EXPENSES] Seeding default categories and accounts for schema: {connection.schema_name}")

    from .models import ExpenseCategory, PaymentAccount

    for name, code, desc, order in DEFAULT_EXPENSE_CATEGORIES:
        ExpenseCategory.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "description": desc,
                "sort_order": order,
                "is_active": True,
            },
        )

    # Seed default PaymentAccount if none exists
    if not PaymentAccount.objects.exists():
        PaymentAccount.objects.create(
            name="Main Cash Counter",
            account_type=PaymentAccount.AccountType.CASH,
            opening_balance=Decimal("0.00"),
            is_default=True,
            is_active=True,
        )

