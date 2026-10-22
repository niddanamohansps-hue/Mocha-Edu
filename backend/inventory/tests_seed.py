"""The seed_inventory_demo command: builds consistent demo data, refuses to run twice, and --clear
removes exactly what it made. Creates a tenant schema, so it needs a disposable PostgreSQL database."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Sum
from django_tenants.utils import tenant_context

from .models import (
    Asset, AssetAssignment, AssetCategory, AssetEvent, Item, ItemCategory, MaintenanceRecord, Purchase, StockLevel,
    StockLocation, StockMovement, Supplier,
)
from .tests import D, InventoryFixture


class SeedInventoryDemoTests(InventoryFixture):
    def seed(self, **extra):
        out = StringIO()
        call_command("seed_inventory_demo", schema=self.SCHEMA_A, stdout=out, **extra)
        return out.getvalue()

    def counts(self):
        with tenant_context(self.school):
            return {
                "items": Item.objects.filter(sku__startswith="DEMO-").count(),
                "assets": Asset.objects.filter(tag__startswith="DEMO-A-").count(),
                "purchases": Purchase.objects.count(),
                "movements": StockMovement.objects.filter(item__sku__startswith="DEMO-").count(),
            }

    def test_it_builds_a_realistic_and_consistent_dataset(self):
        self.seed()
        counts = self.counts()
        self.assertEqual((counts["items"], counts["assets"], counts["purchases"]), (14, 16, 6))
        with tenant_context(self.school):
            # the ledger rule holds for every demo item and location
            for level in StockLevel.objects.filter(item__sku__startswith="DEMO-"):
                total = StockMovement.objects.filter(item=level.item, location=level.location).aggregate(t=Sum("quantity_delta"))["t"]
                self.assertEqual(level.quantity, total, f"{level.item.sku} at {level.location.name}")
                self.assertGreaterEqual(level.quantity, 0)
            # some items are low on purpose, and some are healthy
            totals = {i.sku: i.levels.aggregate(t=Sum("quantity"))["t"] or D("0") for i in Item.objects.filter(sku__startswith="DEMO-")}
            low = [sku for sku, qty in totals.items() if Item.objects.get(sku=sku).reorder_level > 0 and qty <= Item.objects.get(sku=sku).reorder_level]
            self.assertGreaterEqual(len(low), 5)
            self.assertLess(len(low), 14)
            self.assertEqual(totals["DEMO-001"], D("15"))
            self.assertEqual(totals["DEMO-008"], D("30"))  # the cancelled purchase and the reversed issue net out
            # every kind of movement appears
            kinds = set(StockMovement.objects.values_list("kind", flat=True))
            self.assertTrue({"receive", "issue", "return", "adjust_in", "adjust_out", "write_off", "transfer_in",
                             "transfer_out", "reversal"} <= kinds)
            self.assertEqual(Purchase.objects.filter(status="cancelled").count(), 1)
            # assets cover the whole lifecycle
            statuses = set(Asset.objects.filter(tag__startswith="DEMO-A-").values_list("status", flat=True))
            self.assertEqual(statuses, {"available", "assigned", "in_repair", "lost", "disposed"})
            self.assertEqual(MaintenanceRecord.objects.count(), 2)
            self.assertEqual(MaintenanceRecord.objects.filter(closed_at__isnull=True).count(), 1)
            self.assertEqual(AssetAssignment.objects.filter(returned_at__isnull=True).count(), 4)
            # alerts are not switched on by seeding
            from notifications.models import NotificationSettings
            self.assertFalse(NotificationSettings.load().low_stock_alerts_enabled)

    def test_it_uses_real_staff_when_the_school_has_some_and_runs_without_any(self):
        self.seed()
        with tenant_context(self.school):
            self.assertTrue(StockMovement.objects.filter(issued_to_staff=self.keeper).exists())
        self.seed(clear=True)
        with tenant_context(self.school):
            from staff.models import StaffMember
            StaffMember.objects.all().delete()
        self.seed()  # no staff at all: issues go to named groups instead
        with tenant_context(self.school):
            self.assertFalse(StockMovement.objects.filter(issued_to_staff__isnull=False).exists())
            self.assertTrue(StockMovement.objects.filter(kind="issue").exclude(issued_to_note="").exists())

    def test_running_twice_is_refused_and_changes_nothing(self):
        self.seed()
        before = self.counts()
        with self.assertRaises(CommandError):
            self.seed()
        self.assertEqual(self.counts(), before)

    def test_clear_removes_the_demo_data_and_leaves_everything_else(self):
        with tenant_context(self.school):
            mine_items = Item.objects.count()
            mine_levels = StockLevel.objects.count()
            Supplier.objects.create(name="My own supplier")
        self.seed()
        self.seed(clear=True)
        with tenant_context(self.school):
            self.assertEqual((Item.objects.filter(sku__startswith="DEMO-").count(), Asset.objects.count(), Purchase.objects.count()), (0, 0, 0))
            self.assertEqual(StockMovement.objects.filter(item__sku__startswith="DEMO-").count(), 0)
            self.assertEqual((AssetEvent.objects.count(), AssetAssignment.objects.count(), MaintenanceRecord.objects.count()), (0, 0, 0))
            self.assertEqual((Item.objects.count(), StockLevel.objects.count()), (mine_items, mine_levels))
            self.assertTrue(Supplier.objects.filter(name="My own supplier").exists())
            self.assertFalse(Supplier.objects.filter(name="Himalayan Stationers").exists())
            self.assertFalse(StockLocation.objects.filter(name="Sports Room").exists())
        self.seed()  # and it can be created again afterwards
        self.assertEqual(self.counts()["items"], 14)

    def test_a_shared_list_still_in_use_is_kept_on_clear(self):
        self.seed()
        with tenant_context(self.school):
            Asset.objects.create(tag="MINE-1", name="My desk", category=AssetCategory.objects.get(name="Furniture"))
            ItemCategory.objects.create(name="Mine")
        out = StringIO()
        call_command("seed_inventory_demo", schema=self.SCHEMA_A, clear=True, stdout=out)
        self.assertIn("Kept AssetCategory 'Furniture'", out.getvalue())
        with tenant_context(self.school):
            self.assertTrue(Asset.objects.filter(tag="MINE-1").exists())
            self.assertTrue(ItemCategory.objects.filter(name="Mine").exists())

    def test_clear_with_nothing_to_remove_is_harmless(self):
        self.assertIn("nothing to remove", self.seed(clear=True))

    def test_bad_schemas_are_refused(self):
        for schema in ("public", "no_such_school"):
            with self.subTest(schema):
                with self.assertRaises(CommandError):
                    call_command("seed_inventory_demo", schema=schema, stdout=StringIO())
