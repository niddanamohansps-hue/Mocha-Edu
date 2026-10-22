"""Inventory Stage I2: suppliers, purchases (receiving against a purchase) and low-stock alerts.

Creates tenant schemas and uses real threads for the race cases, so it needs a disposable
PostgreSQL database and is meant to be run only in an isolated test stage.
"""
import threading
from datetime import date
from decimal import Decimal
from unittest import mock

from django.db import connections
from django_tenants.utils import schema_context, tenant_context
from rest_framework import serializers
from rest_framework.test import APIClient

from core.models import AuditLog
from notifications.models import EmailOutboxEvent, Notification, NotificationSettings

from . import alerts, services
from .models import Item, Purchase, StockLevel, StockLocation, StockMovement, Supplier
from .tests import BASE, D, InventoryFixture, Kind

TODAY = date(2026, 3, 1)


class PurchaseFixture(InventoryFixture):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.supplier = Supplier.objects.create(name="Everest Stationers", email="sales@everest.test")
            self.pens = Item.objects.create(sku="PEN-1", name="Pens", category=self.category, unit="pcs")

    def lines(self, **quantities):
        """``lines(chalk=("10", "12.50"), pens=("5", "3"))`` -> purchase line dicts."""
        items = {"chalk": self.chalk, "pens": self.pens}
        return [{"item": items[name], "quantity": D(q), "unit_cost": D(c)} for name, (q, c) in quantities.items()]

    def buy(self, school=None, **kwargs):
        with tenant_context(school or self.school):
            return services.receive_purchase(
                supplier=kwargs.pop("supplier", self.supplier), location=kwargs.pop("location", self.store),
                lines=kwargs.pop("lines", self.lines(chalk=("10", "12.50"), pens=("5", "3.00"))),
                purchase_date=kwargs.pop("purchase_date", TODAY), user_id=self.owner.id, **kwargs,
            )


class PurchaseServiceTests(PurchaseFixture):
    def test_a_purchase_receives_every_line_with_its_cost(self):
        purchase = self.buy(reference="INV-100")
        with tenant_context(self.school):
            self.assertEqual((self.level(), self.level(item=self.pens)), (D("10"), D("5")))
            moves = StockMovement.objects.filter(purchase_line__purchase=purchase)
            self.assertEqual({(m.kind, m.unit_cost, m.reference) for m in moves},
                             {(Kind.RECEIVE, D("12.50"), "INV-100"), (Kind.RECEIVE, D("3.00"), "INV-100")})
            self.assertEqual(purchase.total_cost, D("140.00"))
            self.assertEqual(purchase.lines.count(), 2)
            self.assertEqual(purchase.status, Purchase.Status.RECEIVED)

    def test_without_a_reference_the_movements_get_a_generated_one(self):
        purchase = self.buy()
        with tenant_context(self.school):
            reference = StockMovement.objects.filter(purchase_line__purchase=purchase).first().reference
        self.assertEqual(reference, f"PUR-{str(purchase.pk)[:8]}")

    def test_the_total_is_the_sum_of_the_line_totals(self):
        purchase = self.buy(lines=self.lines(chalk=("3", "0.33"), pens=("2.5", "1.10")))
        with tenant_context(self.school):
            self.assertEqual(Purchase.objects.get(pk=purchase.pk).total_cost, D("0.99") + D("2.75"))

    def test_one_bad_line_receives_nothing_at_all(self):
        with tenant_context(self.school):
            Item.objects.filter(pk=self.pens.pk).update(is_active=False)
            self.pens.refresh_from_db()
        with self.assertRaises(serializers.ValidationError):
            self.buy()
        with tenant_context(self.school):
            self.assertEqual(Purchase.objects.count(), 0)
            self.assertEqual(StockMovement.objects.count(), 0)
            self.assertIsNone(self.level())

    def test_bad_purchases_are_refused(self):
        cases = {
            "no lines": dict(lines=[]),
            "duplicate item": dict(lines=self.lines(chalk=("1", "1")) * 2),
            "zero quantity": dict(lines=self.lines(chalk=("0", "1"))),
            "negative cost": dict(lines=[{"item": self.chalk, "quantity": D("1"), "unit_cost": D("-1")}]),
            "total too large": dict(lines=self.lines(chalk=("999999999", "999999999"))),
        }
        for label, kwargs in cases.items():
            with self.subTest(label):
                with self.assertRaises(serializers.ValidationError):
                    self.buy(**kwargs)
        with tenant_context(self.school):
            Supplier.objects.filter(pk=self.supplier.pk).update(is_active=False)
            self.supplier.refresh_from_db()
            with self.assertRaises(serializers.ValidationError):
                services.receive_purchase(supplier=self.supplier, location=self.store, lines=self.lines(chalk=("1", "1")),
                                          purchase_date=TODAY)
            self.assertEqual(Purchase.objects.count(), 0)

    def test_too_many_lines_are_refused(self):
        too_many = [{"item": self.chalk, "quantity": D("1"), "unit_cost": D("1")}] * (services.MAX_PURCHASE_LINES + 1)
        with self.assertRaises(serializers.ValidationError):
            self.buy(lines=too_many)


class PurchaseCancellationTests(PurchaseFixture):
    def test_cancelling_reverses_every_line(self):
        purchase = self.buy()
        with tenant_context(self.school):
            cancelled = services.cancel_purchase(purchase, reason="Wrong supplier", user_id=self.owner.id)
            self.assertEqual((cancelled.status, cancelled.cancellation_reason), (Purchase.Status.CANCELLED, "Wrong supplier"))
            self.assertIsNotNone(cancelled.cancelled_at)
            self.assertEqual((self.level(), self.level(item=self.pens)), (D("0"), D("0")))
            self.assertEqual(StockMovement.objects.filter(kind=Kind.REVERSAL).count(), 2)

    def test_cancelling_is_refused_if_any_of_the_stock_was_used_and_changes_nothing(self):
        purchase = self.buy()
        with tenant_context(self.school):
            self.issue(8)  # chalk: 10 -> 2
            with self.assertRaises(serializers.ValidationError):
                services.cancel_purchase(purchase, reason="Mistake")
            self.assertEqual((self.level(), self.level(item=self.pens)), (D("2"), D("5")))
            self.assertEqual(StockMovement.objects.filter(kind=Kind.REVERSAL).count(), 0)
            self.assertEqual(Purchase.objects.get(pk=purchase.pk).status, Purchase.Status.RECEIVED)

    def test_a_purchase_is_cancelled_once_and_needs_a_reason(self):
        purchase = self.buy()
        with tenant_context(self.school):
            with self.assertRaises(serializers.ValidationError):
                services.cancel_purchase(purchase, reason="  ")
            services.cancel_purchase(purchase, reason="Duplicate")
            with self.assertRaises(serializers.ValidationError):
                services.cancel_purchase(purchase, reason="Again")
            self.assertEqual(StockMovement.objects.filter(kind=Kind.REVERSAL).count(), 2)

    def test_purchase_stock_cannot_be_reversed_line_by_line(self):
        purchase = self.buy()
        with tenant_context(self.school):
            movement = StockMovement.objects.filter(purchase_line__purchase=purchase).first()
            with self.assertRaises(serializers.ValidationError) as caught:
                services.reverse(movement, reason="x")
            self.assertIn("cancel the purchase", str(caught.exception.detail))


class SupplierAndLedgerTests(PurchaseFixture):
    def test_the_level_still_equals_the_ledger_after_purchases_and_cancellations(self):
        first = self.buy()
        self.buy(reference="INV-2")
        with tenant_context(self.school):
            services.cancel_purchase(first, reason="Duplicate")
            for item in (self.chalk, self.pens):
                self.assertEqual(self.level(item=item), self.ledger_sum(item=item))
            self.assertEqual(self.level(), D("10"))

    def test_history_protects_suppliers_and_purchase_lines(self):
        from django.db.models.deletion import ProtectedError
        purchase = self.buy()
        with tenant_context(self.school):
            with self.assertRaises(ProtectedError):
                self.supplier.delete()
            with self.assertRaises(ProtectedError):
                StockMovement.objects.filter(purchase_line__purchase=purchase).delete()

    def test_opposite_ordered_purchases_at_the_same_time_do_not_deadlock(self):
        barrier = threading.Barrier(4)
        errors, done = [], []

        def run(index):
            try:
                with schema_context(self.SCHEMA_A):
                    items = [self.chalk, self.pens] if index % 2 == 0 else [self.pens, self.chalk]
                    lines = [{"item": item, "quantity": D("1"), "unit_cost": D("1")} for item in items]
                    barrier.wait(timeout=30)
                    done.append(services.receive_purchase(supplier=self.supplier, location=self.store, lines=lines,
                                                          purchase_date=TODAY).pk)
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=90)
        self.assertEqual((errors, len(done)), ([], 4))
        with tenant_context(self.school):
            self.assertEqual((self.level(), self.level(item=self.pens)), (D("4"), D("4")))


class PurchaseApiTests(PurchaseFixture):
    def setUp(self):
        super().setUp()
        self.viewer = self._user("viewer", self.school, codenames=["view_inventory"])
        self.manager = self._user("manager", self.school, codenames=["view_inventory", "manage_inventory_items"])
        self.receiver = self._user("receiver", self.school, codenames=["view_inventory", "receive_stock"])
        self.adjuster = self._user("adjuster", self.school, codenames=["view_inventory", "adjust_stock"])
        self.nobody = self._user("nobody", self.school, codenames=[])

    def payload(self, **extra):
        data = {
            "supplier": str(self.supplier.id), "location": str(self.store.id), "purchase_date": "2026-03-01",
            "reference": "INV-7",
            "lines": [{"item": str(self.chalk.id), "quantity": "10", "unit_cost": "12.50"},
                      {"item": str(self.pens.id), "quantity": "5", "unit_cost": "3.00"}],
        }
        data.update(extra)
        return data

    def test_permissions(self):
        purchase = self.buy()
        cases = [
            ("get", "purchases/", None, self.viewer, self.nobody),
            ("get", f"purchases/{purchase.id}/", None, self.viewer, self.nobody),
            ("get", "suppliers/", None, self.viewer, self.nobody),
            ("post", "suppliers/", {"name": "New supplier"}, self.manager, self.receiver),
            ("post", "purchases/", self.payload(), self.receiver, self.manager),
            ("post", f"purchases/{purchase.id}/cancel/", {"reason": "x"}, self.adjuster, self.receiver),
        ]
        for method, path, data, allowed, denied in cases:
            with self.subTest(path=path, method=method):
                self.assertEqual(self._call(denied, method, path, data).status_code, 403)
                self.assertIn(self._call(None, method, path, data).status_code, (401, 403))
                self.assertIn(self._call(allowed, method, path, data).status_code, (200, 201))

    def test_creating_a_purchase_end_to_end(self):
        resp = self._call(self.owner, "post", "purchases/", self.payload())
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual((resp.data["status"], resp.data["total_cost"], resp.data["supplier_name"]),
                         ("received", "140.00", "Everest Stationers"))
        self.assertEqual(sorted(l["line_total"] for l in resp.data["lines"]), ["125.00", "15.00"])
        self.assertEqual(self._call(self.owner, "get", f"items/{self.chalk.id}/").data["on_hand"], "10.000")
        listing = self._call(self.owner, "get", "purchases/")
        self.assertEqual((listing.data["count"], len(listing.data["results"][0]["lines"])), (1, 2))
        cost = self._call(self.owner, "get", f"movements/?item={self.chalk.id}").data["results"][0]["unit_cost"]
        self.assertEqual(cost, "12.50")

    def test_bad_input_is_a_clean_400(self):
        bad = {
            "no lines": self.payload(lines=[]),
            "no supplier": self.payload(supplier=None),
            "unknown item": self.payload(lines=[{"item": "00000000-0000-0000-0000-000000000000", "quantity": "1", "unit_cost": "1"}]),
            "zero quantity": self.payload(lines=[{"item": str(self.chalk.id), "quantity": "0", "unit_cost": "1"}]),
            "negative cost": self.payload(lines=[{"item": str(self.chalk.id), "quantity": "1", "unit_cost": "-1"}]),
            "text cost": self.payload(lines=[{"item": str(self.chalk.id), "quantity": "1", "unit_cost": "abc"}]),
            "duplicate item": self.payload(lines=[{"item": str(self.chalk.id), "quantity": "1", "unit_cost": "1"}] * 2),
            "bad date": self.payload(purchase_date="31-31-2026"),
            "lines not a list": self.payload(lines="chalk"),
            "too many lines": self.payload(lines=[{"item": str(self.chalk.id), "quantity": "1", "unit_cost": "1"}] * 201),
        }
        for label, data in bad.items():
            with self.subTest(label):
                self.assertEqual(self._call(self.owner, "post", "purchases/", data).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", "purchases/", []).status_code, 400)
        with tenant_context(self.school):
            self.assertEqual((Purchase.objects.count(), StockMovement.objects.count()), (0, 0))

    def test_cancel_endpoint(self):
        pid = self._call(self.owner, "post", "purchases/", self.payload()).data["id"]
        self.assertEqual(self._call(self.owner, "post", f"purchases/{pid}/cancel/", {}).status_code, 400)
        resp = self._call(self.owner, "post", f"purchases/{pid}/cancel/", {"reason": "Wrong supplier"})
        self.assertEqual((resp.status_code, resp.data["status"]), (200, "cancelled"))
        self.assertEqual(self._call(self.owner, "post", f"purchases/{pid}/cancel/", {"reason": "again"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "get", f"items/{self.chalk.id}/").data["on_hand"], "0.000")

    def test_a_purchase_cannot_be_cancelled_after_its_stock_was_used(self):
        pid = self._call(self.owner, "post", "purchases/", self.payload()).data["id"]
        self._call(self.owner, "post", "movements/issue/", {"item": str(self.chalk.id), "location": str(self.store.id),
                                                            "quantity": "9", "issued_to_note": "Class 5"})
        resp = self._call(self.owner, "post", f"purchases/{pid}/cancel/", {"reason": "Mistake"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._call(self.owner, "get", f"purchases/{pid}/").data["status"], "received")

    def test_purchase_stock_cannot_be_reversed_through_the_movement_endpoint(self):
        resp = self._call(self.owner, "post", "purchases/", self.payload())
        movement = resp.data["lines"][0]["movement"]
        self.assertEqual(self._call(self.owner, "post", f"movements/{movement}/reverse/", {"reason": "x"}).status_code, 400)

    def test_purchases_cannot_be_edited_or_deleted(self):
        pid = self._call(self.owner, "post", "purchases/", self.payload()).data["id"]
        for method in ("put", "patch", "delete"):
            self.assertEqual(self._call(self.owner, method, f"purchases/{pid}/", {}).status_code, 405, method)

    def test_filters_and_search(self):
        self._call(self.owner, "post", "purchases/", self.payload())
        self._call(self.owner, "post", "purchases/", self.payload(reference="INV-8", purchase_date="2026-04-01"))
        self.assertEqual(self._call(self.owner, "get", "purchases/?search=INV-8").data["count"], 1)
        self.assertEqual(self._call(self.owner, "get", "purchases/?search=pens").data["count"], 2)
        self.assertEqual(self._call(self.owner, "get", "purchases/?purchase_date__gte=2026-03-15").data["count"], 1)
        self.assertEqual(self._call(self.owner, "get", f"purchases/?supplier={self.supplier.id}").data["count"], 2)
        self.assertEqual(self._call(self.owner, "get", "purchases/?status=cancelled").data["count"], 0)

    def test_audit_log(self):
        pid = self._call(self.owner, "post", "purchases/", self.payload()).data["id"]
        self._call(self.owner, "post", f"purchases/{pid}/cancel/", {"reason": "Wrong"})
        with tenant_context(self.school):
            entries = AuditLog.objects.filter(model_name="Purchase").order_by("created_at")
            self.assertEqual([e.action for e in entries], ["purchase_received", "purchase_cancelled"])
            self.assertEqual(entries[0].changes["total_cost"], "140.00")
            self.assertEqual(entries[0].actor_id, self.owner.id)

    def test_schools_are_separate(self):
        pid = self._call(self.owner, "post", "purchases/", self.payload()).data["id"]
        user_b = self._user("owner_b", self.school_b, role_slug="owner")
        self.assertEqual(self._call(user_b, "get", "purchases/", host=self.DOMAIN_B).data["results"], [])
        self.assertEqual(self._call(user_b, "get", f"purchases/{pid}/", host=self.DOMAIN_B).status_code, 404)
        self.assertEqual(self._call(user_b, "post", f"purchases/{pid}/cancel/", {"reason": "x"}, host=self.DOMAIN_B).status_code, 404)
        self.assertEqual(self._call(user_b, "post", "purchases/", self.payload(), host=self.DOMAIN_B).status_code, 400)
        self.assertEqual(self._call(user_b, "get", "suppliers/", host=self.DOMAIN_B).data["results"], [])

    def test_suppliers(self):
        self.assertEqual(self._call(self.owner, "post", "suppliers/", {"name": "Everest Stationers"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", "suppliers/", {"name": "X", "email": "nope"}).status_code, 400)
        self._call(self.owner, "post", "purchases/", self.payload())
        self.assertEqual(self._call(self.owner, "delete", f"suppliers/{self.supplier.id}/").status_code, 409)
        spare = self._call(self.owner, "post", "suppliers/", {"name": "Spare"}).data["id"]
        self.assertEqual(self._call(self.owner, "delete", f"suppliers/{spare}/").status_code, 204)
        self._call(self.owner, "patch", f"suppliers/{self.supplier.id}/", {"is_active": False})
        self.assertEqual(self._call(self.owner, "post", "purchases/", self.payload()).status_code, 400)
        self.assertEqual(self._call(self.owner, "get", "suppliers/?is_active=false").data["count"], 1)


class LowStockAlertTests(PurchaseFixture):
    """chalk has reorder level 5."""

    def setUp(self):
        super().setUp()
        self.manager = self._user("manager", self.school, codenames=["manage_inventory_items"])
        self.receiver = self._user("receiver", self.school, codenames=["receive_stock"])
        self.viewer = self._user("viewer", self.school, codenames=["view_inventory"])
        self.issuer = self._user("issuer", self.school, codenames=["issue_stock"])
        self.leaver = self._user("leaver", self.school, role_slug="owner")
        from accounts.models import User
        User.objects.filter(pk=self.leaver.pk).update(is_active=False)
        with tenant_context(self.school):
            self.stock(20)

    def enable(self, value=True):
        with tenant_context(self.school):
            NotificationSettings.objects.update_or_create(singleton=True, defaults={"low_stock_alerts_enabled": value})

    def notes(self):
        with tenant_context(self.school):
            return list(Notification.objects.filter(category="inventory"))

    def emails(self):
        with tenant_context(self.school):
            return list(EmailOutboxEvent.objects.all())

    def test_nothing_is_sent_until_the_school_turns_it_on(self):
        with tenant_context(self.school):
            self.issue(18)
            self.assertIsNone(Item.objects.get(pk=self.chalk.pk).low_stock_notified_at)
        self.assertEqual(self.notes(), [])

    def test_crossing_the_reorder_level_tells_the_people_who_manage_stock(self):
        self.enable()
        with tenant_context(self.school):
            self.issue(14)  # 20 -> 6, still above 5
        self.assertEqual(self.notes(), [])
        with tenant_context(self.school):
            self.issue(1)  # 6 -> 5: at the level
        notes = self.notes()
        self.assertEqual({n.recipient_user_id for n in notes}, {self.owner.id, self.manager.id, self.receiver.id})
        self.assertEqual(notes[0].title, "Low stock: Chalk")
        self.assertEqual(notes[0].body, "Chalk (CHK-1): 5.000 box left in total. The reorder level is 5.000.")
        self.assertEqual({e.to_email for e in self.emails()}, {u.email for u in (self.owner, self.manager, self.receiver)})

    def test_viewers_issuers_and_inactive_users_are_not_told(self):
        self.enable()
        with tenant_context(self.school):
            self.issue(19)
        told = {n.recipient_user_id for n in self.notes()}
        self.assertFalse(told & {self.viewer.id, self.issuer.id, self.leaver.id})

    def test_one_dip_gives_one_alert(self):
        self.enable()
        with tenant_context(self.school):
            self.issue(16)
            self.issue(1)
            self.issue(1)
        self.assertEqual(len(self.notes()), 3)  # three recipients, one alert

    def test_after_recovering_a_new_dip_alerts_again(self):
        self.enable()
        with tenant_context(self.school):
            self.issue(16)
            self.assertIsNotNone(Item.objects.get(pk=self.chalk.pk).low_stock_notified_at)
            self.stock(10)  # 14: back above the level
            self.assertIsNone(Item.objects.get(pk=self.chalk.pk).low_stock_notified_at)
            self.issue(10)  # 4: low again
        self.assertEqual(len(self.notes()), 6)

    def test_stock_is_counted_across_all_locations(self):
        self.enable()
        with tenant_context(self.school):
            self.stock(10, location=self.lab)  # 30 in total
            self.issue(20)  # store 0, lab 10: total 10, fine
        self.assertEqual(self.notes(), [])
        with tenant_context(self.school):
            services.record(item=self.chalk, location=self.lab, kind=Kind.WRITE_OFF, quantity=D("6"), reason="Spilled")
        self.assertEqual(len(self.notes()), 3)

    def test_items_without_a_level_or_inactive_items_never_alert(self):
        self.enable()
        with tenant_context(self.school):
            self.stock(5, item=self.pens)
            self.issue(4, item=self.pens)  # reorder level 0
            self.assertFalse(alerts._is_low(self.pens, D("0")))
            Item.objects.filter(pk=self.chalk.pk).update(is_active=False)
            self.chalk.refresh_from_db()
            self.assertFalse(alerts._is_low(self.chalk, D("0")))  # inactive items are never low
        self.assertEqual(self.notes(), [])

    def test_transfers_never_alert(self):
        self.enable()
        with tenant_context(self.school):
            self.issue(16)  # alert once (4 left)
            before = len(Notification.objects.all())
            Item.objects.filter(pk=self.chalk.pk).update(low_stock_notified_at=None)
            services.transfer(item=self.chalk, from_location=self.store, to_location=self.lab, quantity=D("2"))
            self.assertEqual(len(Notification.objects.all()), before)

    def test_a_purchase_that_restocks_resets_the_state(self):
        self.enable()
        with tenant_context(self.school):
            self.issue(17)
        self.buy(lines=self.lines(chalk=("10", "1")))
        with tenant_context(self.school):
            self.assertIsNone(Item.objects.get(pk=self.chalk.pk).low_stock_notified_at)

    def test_a_failing_alert_never_blocks_the_stock_movement_and_is_retried(self):
        self.enable()
        with tenant_context(self.school):
            with mock.patch("inventory.alerts.notify", side_effect=RuntimeError("inbox down")), \
                    self.assertLogs("inventory.alerts", level="ERROR"):
                movement = self.issue(17)
            self.assertEqual(movement.balance_after, D("3"))
            self.assertEqual(self.level(), D("3"))
            self.assertIsNone(Item.objects.get(pk=self.chalk.pk).low_stock_notified_at)
            self.issue(1)  # the next movement tries again
        self.assertEqual(len(self.notes()), 3)

    def test_simultaneous_issues_across_the_level_announce_once(self):
        self.enable()
        barrier = threading.Barrier(4)
        errors = []

        def run(index):
            try:
                with schema_context(self.SCHEMA_A):
                    barrier.wait(timeout=30)
                    self.issue(5, to=f"T{index}")
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=90)
        self.assertEqual(errors, [])
        with tenant_context(self.school):
            self.assertEqual(self.level(), D("0"))
        self.assertEqual(len(self.notes()), 3)

    def test_the_recipient_rule_is_owner_or_a_stock_manager(self):
        with tenant_context(self.school):
            ids = {user_id for user_id, _ in alerts.alert_recipients()}
        self.assertEqual(ids, {self.owner.id, self.manager.id, self.receiver.id})

    def _settings_call(self, method, data=None):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        return getattr(client, method)("/api/notifications/settings/", data, format="json", HTTP_HOST=self.DOMAIN_A)

    def test_the_setting_is_available_through_the_settings_api(self):
        resp = self._settings_call("get")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIs(resp.data["low_stock_alerts_enabled"], False)
        resp = self._settings_call("patch", {"low_stock_alerts_enabled": True})
        self.assertEqual((resp.status_code, resp.data["low_stock_alerts_enabled"]), (200, True))
        self.assertEqual(self._settings_call("patch", {"low_stock_alerts_enabled": "yes"}).status_code, 400)
        with tenant_context(self.school):
            self.assertTrue(NotificationSettings.load().low_stock_alerts_enabled)
