"""
Adds synthetic inventory data (stock, purchases, assets) to an EXISTING school for manual UI testing.

Everything is fictional and tagged so it can be recognised and removed again: item SKUs start with
``DEMO-``, asset tags with ``DEMO-A-``, and supplier/category/location names are listed below. The data
is created through the real inventory services, so it follows the same rules as the screens (no
negative stock, locked transitions, immutable ledger).

Usage (run from the backend folder, against the school you want to fill):
    python manage.py seed_inventory_demo                       # the demo school (greenvalley_demo)
    python manage.py seed_inventory_demo --schema my_school
    python manage.py seed_inventory_demo --clear               # remove what this command created

It refuses to run twice (use --clear first). --clear removes the items, purchases, movements and assets
carrying the DEMO- prefixes, and then the suppliers, categories and locations with the exact names above
that nothing else uses; a list that is still in use by other data is kept. Low-stock alerts are not
switched on by this command.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django_tenants.utils import tenant_context

D = Decimal
SKU_PREFIX = "DEMO-"
TAG_PREFIX = "DEMO-A-"

ITEM_CATEGORIES = ["Stationery", "Cleaning Supplies", "Lab Supplies", "Sports Equipment", "Printing"]
ASSET_CATEGORIES = ["Computers", "Furniture", "Lab Equipment", "Audio Visual"]
LOCATIONS = ["Main Store", "Science Lab Store", "Admin Office", "Sports Room"]
SUPPLIERS = [
    ("Himalayan Stationers", "Sita Karki", "9801000001", "sales@himalayan-stationers.test"),
    ("Everest Lab Supplies", "Ramesh Gurung", "9801000002", "orders@everest-lab.test"),
    ("Kathmandu Office Mart", "Anita Shrestha", "9801000003", "hello@ktm-office-mart.test"),
    ("Pokhara Sports House", "Bikash Thapa", "9801000004", "info@pokhara-sports.test"),
]

# sku, name, category, unit, reorder level
ITEMS = [
    ("DEMO-001", "A4 Paper (ream)", "Printing", "ream", "20"),
    ("DEMO-002", "Whiteboard Marker (blue)", "Stationery", "pcs", "30"),
    ("DEMO-003", "Whiteboard Marker (black)", "Stationery", "pcs", "30"),
    ("DEMO-004", "Chalk (box of 100)", "Stationery", "box", "10"),
    ("DEMO-005", "Exercise Copy (200 pages)", "Stationery", "pcs", "100"),
    ("DEMO-006", "Floor Cleaner (5 litre)", "Cleaning Supplies", "can", "4"),
    ("DEMO-007", "Hand Soap (500 ml)", "Cleaning Supplies", "bottle", "12"),
    ("DEMO-008", "Dustbin Liner (pack)", "Cleaning Supplies", "pack", "10"),
    ("DEMO-009", "Test Tube (pack of 10)", "Lab Supplies", "pack", "6"),
    ("DEMO-010", "Hydrochloric Acid (500 ml)", "Lab Supplies", "bottle", "3"),
    ("DEMO-011", "Football (size 5)", "Sports Equipment", "pcs", "4"),
    ("DEMO-012", "Skipping Rope", "Sports Equipment", "pcs", "10"),
    ("DEMO-013", "Printer Toner Cartridge", "Printing", "pcs", "2"),
    ("DEMO-014", "Stapler Pins (box)", "Stationery", "box", "0"),
]

# tag, name, category, serial, supplier (index into SUPPLIERS), cost, condition, location
ASSETS = [
    ("DEMO-A-001", "Teacher Laptop - Dell Latitude", "Computers", "DL-77310", 2, "92000.00", "good", "Admin Office"),
    ("DEMO-A-002", "Teacher Laptop - Dell Latitude", "Computers", "DL-77311", 2, "92000.00", "good", "Admin Office"),
    ("DEMO-A-003", "Principal Desktop PC", "Computers", "HP-55120", 2, "78500.00", "good", "Admin Office"),
    ("DEMO-A-004", "Computer Lab PC 01", "Computers", "LB-0001", 2, "61000.00", "fair", "Main Store"),
    ("DEMO-A-005", "Computer Lab PC 02", "Computers", "LB-0002", 2, "61000.00", "fair", "Main Store"),
    ("DEMO-A-006", "Student Desk (double)", "Furniture", "", 2, "6500.00", "new", "Main Store"),
    ("DEMO-A-007", "Teacher Table", "Furniture", "", 2, "9800.00", "good", "Main Store"),
    ("DEMO-A-008", "Steel Cupboard", "Furniture", "", 2, "21500.00", "good", "Admin Office"),
    ("DEMO-A-009", "Microscope (binocular)", "Lab Equipment", "MC-4410", 1, "38000.00", "good", "Science Lab Store"),
    ("DEMO-A-010", "Microscope (binocular)", "Lab Equipment", "MC-4411", 1, "38000.00", "poor", "Science Lab Store"),
    ("DEMO-A-011", "Digital Balance", "Lab Equipment", "DB-2208", 1, "14500.00", "good", "Science Lab Store"),
    ("DEMO-A-012", "Projector - Epson EB-X06", "Audio Visual", "EP-90321", 2, "54000.00", "good", "Admin Office"),
    ("DEMO-A-013", "Projector - Epson EB-X06", "Audio Visual", "EP-90322", 2, "54000.00", "fair", "Admin Office"),
    ("DEMO-A-014", "Public Address System", "Audio Visual", "PA-1180", 2, "47000.00", "good", "Sports Room"),
    ("DEMO-A-015", "Old Overhead Projector", "Audio Visual", "OH-0007", 2, "15000.00", "poor", "Main Store"),
    ("DEMO-A-016", "Wireless Microphone Set", "Audio Visual", "WM-3301", 2, "12500.00", "good", "Sports Room"),
]


class Command(BaseCommand):
    help = "Adds (or removes) synthetic inventory data - stock, purchases and assets - for one existing school."

    def add_arguments(self, parser):
        parser.add_argument("--schema", default="greenvalley_demo", help="Schema name of the school (default: greenvalley_demo).")
        parser.add_argument("--clear", action="store_true", help="Remove the data this command created instead of adding it.")

    def handle(self, *args, **options):
        from organizations.models import Organization

        schema = options["schema"]
        if schema == "public":
            raise CommandError("Inventory belongs to a school, not the public schema.")
        organization = Organization.objects.filter(schema_name=schema).first()
        if organization is None:
            raise CommandError(f"No school with schema '{schema}' exists.")

        with tenant_context(organization):
            if options["clear"]:
                self._clear()
            else:
                self._seed()

    # ------------------------------------------------------------------------------------------------

    def _seed(self):
        from inventory.models import Asset, Item

        if Item.objects.filter(sku__startswith=SKU_PREFIX).exists() or Asset.objects.filter(tag__startswith=TAG_PREFIX).exists():
            raise CommandError("Demo inventory already exists in this school. Run with --clear first to recreate it.")
        with transaction.atomic():
            summary = self._build()
        self.stdout.write(self.style.SUCCESS("Demo inventory created: " + ", ".join(f"{n} {label}" for label, n in summary.items())))
        self.stdout.write("Low-stock alerts were NOT switched on. Several items are below their reorder level on purpose.")

    def _build(self):
        from inventory import asset_services, services
        from inventory.models import (
            Asset, AssetCategory, Item, ItemCategory, StockLocation, StockMovement, Supplier,
        )
        from staff.models import StaffMember

        today = timezone.localdate()
        categories = {name: ItemCategory.objects.get_or_create(name=name)[0] for name in ITEM_CATEGORIES}
        asset_categories = {name: AssetCategory.objects.get_or_create(name=name)[0] for name in ASSET_CATEGORIES}
        locations = {name: StockLocation.objects.get_or_create(name=name)[0] for name in LOCATIONS}
        suppliers = [
            Supplier.objects.get_or_create(
                name=name, defaults={"contact_name": contact, "phone": phone, "email": email, "address": "Kathmandu, Nepal"}
            )[0]
            for name, contact, phone, email in SUPPLIERS
        ]
        items = {
            sku: Item.objects.create(sku=sku, name=name, category=categories[category], unit=unit, reorder_level=D(reorder))
            for sku, name, category, unit, reorder in ITEMS
        }
        staff = list(StaffMember.objects.filter(is_active=True).select_related("profile").order_by("employee_id")[:6])
        main, lab, office, sports = (locations[n] for n in LOCATIONS)

        def line(sku, quantity, cost):
            return {"item": items[sku], "quantity": D(quantity), "unit_cost": D(cost)}

        # --- purchases (older to newer) ---
        purchases = [
            (suppliers[0], main, 75, "HS-INV-1042", [line("DEMO-001", "60", "685.00"), line("DEMO-002", "120", "38.00"),
                                                       line("DEMO-003", "120", "38.00"), line("DEMO-004", "40", "210.00"),
                                                       line("DEMO-005", "400", "42.50"), line("DEMO-014", "30", "55.00")]),
            (suppliers[2], main, 60, "KOM-2231", [line("DEMO-006", "12", "980.00"), line("DEMO-007", "40", "145.00"),
                                                  line("DEMO-008", "30", "120.00"), line("DEMO-013", "6", "7400.00")]),
            (suppliers[1], lab, 45, "ELS-0087", [line("DEMO-009", "20", "460.00"), line("DEMO-010", "8", "890.00")]),
            (suppliers[3], sports, 30, "PSH-5560", [line("DEMO-011", "10", "1450.00"), line("DEMO-012", "30", "180.00")]),
            (suppliers[0], main, 10, "HS-INV-1107", [line("DEMO-001", "40", "690.00"), line("DEMO-002", "60", "39.00")]),
        ]
        made = []
        for supplier, location, days_ago, reference, lines in purchases:
            made.append(services.receive_purchase(
                supplier=supplier, location=location, lines=lines, purchase_date=today - timedelta(days=days_ago),
                reference=reference, notes="Demo data",
            ))
        # a purchase entered by mistake and cancelled
        mistaken = services.receive_purchase(
            supplier=suppliers[2], location=main, purchase_date=today - timedelta(days=20), reference="KOM-2299",
            notes="Demo data", lines=[line("DEMO-008", "100", "120.00")],
        )
        services.cancel_purchase(mistaken, reason="Duplicate of an earlier order")

        # --- day-to-day movements ---
        def issue(sku, quantity, location, staff_index, note, ref=""):
            """Issue to a real staff member when the school has any, otherwise to a named group."""
            holder = {"issued_to_staff": staff[staff_index % len(staff)]} if staff else {"issued_to_note": note}
            return services.record(item=items[sku], location=location, kind=StockMovement.Kind.ISSUE,
                                   quantity=D(quantity), reference=ref, **holder)

        # Several items are left at or below their reorder level on purpose, so the "Low stock" views have something to show.
        issue("DEMO-001", "55", main, 0, "Examination office", ref="REQ-001")        # A4 paper: 100 -> 45
        issue("DEMO-001", "30", main, 1, "Examination office", ref="REQ-014")        # A4 paper: 15 (reorder level 20)
        issue("DEMO-002", "150", main, 2, "Class 6-10 teachers", ref="REQ-003")     # blue markers: 180 -> 30 (reorder level 30)
        issue("DEMO-003", "100", main, 3, "Class 6-10 teachers", ref="REQ-004")     # black markers: 120 -> 20 (reorder level 30)
        issue("DEMO-005", "330", main, 4, "Class 1-5 teachers", ref="REQ-006")      # exercise copies: 400 -> 70 (reorder level 100)
        issue("DEMO-007", "34", main, 5, "Housekeeping", ref="REQ-009")            # hand soap: 40 -> 6 (reorder level 12)
        issue("DEMO-009", "17", lab, 0, "Chemistry lab", ref="LAB-02")             # test tubes: 20 -> 3 (reorder level 6)
        issue("DEMO-011", "6", sports, 1, "Sports teacher", ref="SP-01")           # footballs: 10 -> 4 (reorder level 4)
        services.record(item=items["DEMO-011"], location=sports, kind=StockMovement.Kind.RETURN, quantity=D("1"),
                        issued_to_note="Sports teacher", reason="Returned after the inter-house match")
        services.record(item=items["DEMO-012"], location=sports, kind=StockMovement.Kind.WRITE_OFF, quantity=D("3"),
                        reason="Worn out, ropes snapped")
        services.record(item=items["DEMO-004"], location=main, kind=StockMovement.Kind.ADJUST_OUT, quantity=D("2"),
                        reason="Stock count: two boxes missing")
        services.record(item=items["DEMO-014"], location=main, kind=StockMovement.Kind.ADJUST_IN, quantity=D("4"),
                        reason="Stock count: four boxes found in a cupboard")
        services.transfer(item=items["DEMO-006"], from_location=main, to_location=office, quantity=D("3"),
                          reason="Cleaner's cupboard in the admin block")
        wrong = issue("DEMO-008", "5", main, 2, "Wrong class", ref="REQ-020")
        services.reverse(wrong, reason="Issued to the wrong department by mistake")

        # --- assets ---
        created = {}
        for index, (tag, name, category, serial, supplier_index, cost, condition, location) in enumerate(ASSETS):
            created[tag] = asset_services.register(
                tag=tag, name=name, category=asset_categories[category], serial_number=serial,
                supplier=suppliers[supplier_index],
                purchase_date=today - timedelta(days=400 - index * 20), purchase_cost=D(cost),
                condition=condition, location=locations[location],
            )
        for number, member_index in ((1, 0), (2, 1), (3, 2)):
            note = "" if staff else "Staff member"
            asset_services.assign(created[f"DEMO-A-00{number}"], staff=staff[member_index % len(staff)] if staff else None,
                                  location=office, note=note)
        asset_services.assign(created["DEMO-A-012"], location=office, note="Class 8 projector")
        asset_services.assign(created["DEMO-A-016"], location=sports, note="Annual day programme")
        asset_services.return_asset(created["DEMO-A-016"], location=sports, condition="good", note="Programme over")
        asset_services.send_to_repair(created["DEMO-A-010"], reason="Focus knob stuck")
        asset_services.send_to_repair(created["DEMO-A-013"], reason="Lamp has failed")
        asset_services.complete_repair(created["DEMO-A-013"], cost=D("3200.00"), notes="New lamp fitted", condition="good")
        asset_services.mark_lost(created["DEMO-A-011"], reason="Not found during the yearly audit")
        asset_services.dispose(created["DEMO-A-015"], reason="Beyond repair; sold as scrap")

        return {
            "item categories": len(ITEM_CATEGORIES), "locations": len(LOCATIONS), "suppliers": len(SUPPLIERS),
            "items": len(ITEMS), "purchases": len(made) + 1, "stock movements": StockMovement.objects.count(),
            "asset categories": len(ASSET_CATEGORIES), "assets": Asset.objects.count(),
        }

    # ------------------------------------------------------------------------------------------------

    def _clear(self):
        """Delete only what this command created, children first. The ledger is protected against
        deletion by the application code, so it is removed with direct queryset deletes (this command
        is the one deliberate exception)."""
        from inventory.models import (
            Asset, AssetAssignment, AssetCategory, AssetEvent, Item, ItemCategory, MaintenanceRecord, Purchase,
            PurchaseLine, StockLevel, StockLocation, StockMovement, Supplier,
        )

        items = Item.objects.filter(sku__startswith=SKU_PREFIX)
        assets = Asset.objects.filter(tag__startswith=TAG_PREFIX)
        if not items.exists() and not assets.exists():
            self.stdout.write("No demo inventory found; nothing to remove.")
            return
        with transaction.atomic():
            lines = PurchaseLine.objects.filter(item__in=items)
            purchase_ids = list(lines.values_list("purchase_id", flat=True).distinct())
            lines.delete()
            Purchase.objects.filter(pk__in=purchase_ids).delete()
            movements = StockMovement.objects.filter(item__in=items)
            movements.filter(reverses__isnull=False).delete()  # reversals first: they point at the originals
            movements.delete()
            StockLevel.objects.filter(item__in=items).delete()
            items.delete()
            AssetEvent.objects.filter(asset__in=assets).delete()
            AssetAssignment.objects.filter(asset__in=assets).delete()
            MaintenanceRecord.objects.filter(asset__in=assets).delete()
            assets.delete()
            # Shared lists with the exact names this command uses, and only if nothing else still uses them.
            for model, names in ((Supplier, [s[0] for s in SUPPLIERS]), (ItemCategory, ITEM_CATEGORIES),
                                 (AssetCategory, ASSET_CATEGORIES), (StockLocation, LOCATIONS)):
                for record in model.objects.filter(name__in=names):
                    try:
                        with transaction.atomic():
                            record.delete()
                    except ProtectedError:  # in use by something that is not demo data: keep it
                        self.stdout.write(f"Kept {model.__name__} '{record.name}' (still in use).")
        self.stdout.write(self.style.SUCCESS("Demo inventory removed."))
