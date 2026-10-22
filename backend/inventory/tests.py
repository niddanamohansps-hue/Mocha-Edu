"""Inventory Stage I1: stock items, locations and the movement ledger.

Creates tenant schemas and uses real threads for the race cases, so it needs a disposable
PostgreSQL database and is meant to be run only in an isolated test stage.
"""
import threading
import uuid
from decimal import Decimal

from django.db import IntegrityError, connection, connections, transaction
from django.db.models import Sum
from django.test import TransactionTestCase
from django_tenants.utils import schema_context, tenant_context
from rest_framework import serializers
from rest_framework.test import APIClient

from accounts.models import User
from core.models import AuditLog
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.constants import SYSTEM_PERMISSIONS
from roles.models import Permission, Role, UserRole
from staff.models import StaffMember

from . import services
from .models import Item, ItemCategory, StockLevel, StockLocation, StockMovement

D = Decimal
Kind = StockMovement.Kind
PASSWORD = "Pass1234!"
PERMISSIONS = {"view_inventory", "manage_inventory_items", "receive_stock", "issue_stock", "adjust_stock"}
BASE = "/api/inventory"


class InventoryFixture(TransactionTestCase):
    SCHEMA_A, DOMAIN_A = "inv_a", "inv-a.localhost"
    SCHEMA_B, DOMAIN_B = "inv_b", "inv-b.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA_A, self.SCHEMA_B]):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="inv_").delete()

    def _school(self, schema, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema, name=schema)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _user(self, name, school, *, role_slug=None, codenames=None):
        connection.set_schema_to_public()
        user = User.objects.create_user(username=f"inv_{name}", email=f"inv_{name}@inv.test", password=PASSWORD)
        with tenant_context(school):
            Profile.objects.create(user_id=user.id, first_name=name, last_name="User")
            if role_slug:
                role = Role.objects.get(slug=role_slug)
            else:
                slug = f"inv-{uuid.uuid4().hex[:10]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
        return user

    def _call(self, user, method, path, data=None, host=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return getattr(client, method)(f"{BASE}/{path}", data, format="json", HTTP_HOST=host or self.DOMAIN_A)

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school = self._school(self.SCHEMA_A, self.DOMAIN_A)
        self.school_b = self._school(self.SCHEMA_B, self.DOMAIN_B)
        self.owner = self._user("owner", self.school, role_slug="owner")
        with tenant_context(self.school):
            self.category = ItemCategory.objects.create(name="Stationery")
            self.store = StockLocation.objects.create(name="Main store")
            self.lab = StockLocation.objects.create(name="Science lab")
            self.chalk = Item.objects.create(sku="CHK-1", name="Chalk", category=self.category, unit="box",
                                             reorder_level=D("5"))
            profile = Profile.objects.create(first_name="Store", last_name="Keeper")
            self.keeper = StaffMember.objects.create(profile=profile, employee_id="E-INV-1", designation="Storekeeper")

    # -- helpers used inside tenant_context
    def stock(self, qty, item=None, location=None, **extra):
        return services.record(item=item or self.chalk, location=location or self.store, kind=Kind.RECEIVE,
                               quantity=D(str(qty)), user_id=self.owner.id, **extra)

    def issue(self, qty, item=None, location=None, to="Mr Rai"):
        return services.record(item=item or self.chalk, location=location or self.store, kind=Kind.ISSUE,
                               quantity=D(str(qty)), user_id=self.owner.id, issued_to_note=to)

    def level(self, item=None, location=None):
        row = StockLevel.objects.filter(item=item or self.chalk, location=location or self.store).first()
        return row.quantity if row else None

    def ledger_sum(self, item=None, location=None):
        return StockMovement.objects.filter(item=item or self.chalk, location=location or self.store).aggregate(
            total=Sum("quantity_delta"))["total"] or D("0")


class ServiceRuleTests(InventoryFixture):
    def test_receiving_creates_the_level_and_a_movement_with_the_new_balance(self):
        with tenant_context(self.school):
            movement = self.stock(10, unit_cost=D("12.50"), reference="PO-1")
            self.assertEqual(self.level(), D("10"))
            self.assertEqual((movement.kind, movement.quantity_delta, movement.balance_after), (Kind.RECEIVE, D("10"), D("10")))
            self.assertEqual((movement.unit_cost, movement.reference, movement.recorded_by_user_id), (D("12.50"), "PO-1", self.owner.id))

    def test_issue_reduces_stock_and_needs_to_say_who_received_it(self):
        with tenant_context(self.school):
            self.stock(10)
            self.assertEqual(self.issue(4).balance_after, D("6"))
            with self.assertRaises(serializers.ValidationError):
                services.record(item=self.chalk, location=self.store, kind=Kind.ISSUE, quantity=D("1"))
            ok = services.record(item=self.chalk, location=self.store, kind=Kind.ISSUE, quantity=D("1"), issued_to_staff=self.keeper)
            self.assertEqual(ok.issued_to_staff_id, self.keeper.id)
            self.assertEqual(self.level(), D("5"))

    def test_issuing_more_than_is_on_hand_fails_and_changes_nothing(self):
        with tenant_context(self.school):
            self.stock(3)
            with self.assertRaises(serializers.ValidationError) as caught:
                self.issue(4)
            self.assertIn("Not enough stock", str(caught.exception.detail))
            self.assertEqual(self.level(), D("3"))
            self.assertEqual(StockMovement.objects.count(), 1)

    def test_issuing_from_a_location_that_never_had_the_item_fails_cleanly(self):
        with tenant_context(self.school):
            with self.assertRaises(serializers.ValidationError):
                self.issue(1, location=self.lab)
            self.assertEqual(StockMovement.objects.count(), 0)
            self.assertIsNone(self.level(location=self.lab))  # the failed attempt left no trace at all

    def test_returns_add_stock_back(self):
        with tenant_context(self.school):
            self.stock(5)
            self.issue(2)
            back = services.record(item=self.chalk, location=self.store, kind=Kind.RETURN, quantity=D("1"), issued_to_note="Mr Rai")
            self.assertEqual(back.balance_after, D("4"))

    def test_quantities_must_be_positive_and_a_cost_belongs_to_receiving_only(self):
        with tenant_context(self.school):
            self.stock(5)
            for bad in (D("0"), D("-1"), None):
                with self.assertRaises(serializers.ValidationError):
                    services.record(item=self.chalk, location=self.store, kind=Kind.RECEIVE, quantity=bad)
            with self.assertRaises(serializers.ValidationError):
                services.record(item=self.chalk, location=self.store, kind=Kind.ISSUE, quantity=D("1"),
                                issued_to_note="x", unit_cost=D("3"))

    def test_adjustments_and_write_offs_need_a_reason(self):
        with tenant_context(self.school):
            self.stock(10)
            for kind in (Kind.ADJUST_IN, Kind.ADJUST_OUT, Kind.WRITE_OFF):
                with self.subTest(kind):
                    with self.assertRaises(serializers.ValidationError):
                        services.record(item=self.chalk, location=self.store, kind=kind, quantity=D("1"), reason="  ")
            services.record(item=self.chalk, location=self.store, kind=Kind.ADJUST_OUT, quantity=D("2"), reason="Count")
            services.record(item=self.chalk, location=self.store, kind=Kind.WRITE_OFF, quantity=D("1"), reason="Water damage")
            services.record(item=self.chalk, location=self.store, kind=Kind.ADJUST_IN, quantity=D("4"), reason="Found")
            self.assertEqual(self.level(), D("11"))

    def test_inactive_items_and_locations_are_refused(self):
        with tenant_context(self.school):
            self.stock(5)
            Item.objects.filter(pk=self.chalk.pk).update(is_active=False)
            self.chalk.refresh_from_db()
            with self.assertRaises(serializers.ValidationError):
                self.stock(1)
            Item.objects.filter(pk=self.chalk.pk).update(is_active=True)
            StockLocation.objects.filter(pk=self.store.pk).update(is_active=False)
            self.store.refresh_from_db()
            with self.assertRaises(serializers.ValidationError):
                self.issue(1)

    def test_decimal_quantities_are_exact(self):
        with tenant_context(self.school):
            self.stock("0.1")
            self.stock("0.2")
            self.assertEqual(self.level(), D("0.300"))
            self.issue("0.3")
            self.assertEqual(self.level(), D("0.000"))


class TransferTests(InventoryFixture):
    def test_a_transfer_moves_stock_with_two_linked_movements(self):
        with tenant_context(self.school):
            self.stock(10)
            out, into = services.transfer(item=self.chalk, from_location=self.store, to_location=self.lab,
                                          quantity=D("4"), user_id=self.owner.id, reason="Lab restock")
            self.assertEqual((self.level(), self.level(location=self.lab)), (D("6"), D("4")))
            self.assertEqual((out.kind, into.kind), (Kind.TRANSFER_OUT, Kind.TRANSFER_IN))
            self.assertEqual(out.transfer_group, into.transfer_group)
            self.assertIsNotNone(out.transfer_group)
            self.assertEqual((out.quantity_delta, into.quantity_delta), (D("-4"), D("4")))

    def test_a_transfer_is_all_or_nothing(self):
        with tenant_context(self.school):
            self.stock(3)
            with self.assertRaises(serializers.ValidationError):
                services.transfer(item=self.chalk, from_location=self.store, to_location=self.lab, quantity=D("4"))
            self.assertEqual((self.level(), self.level(location=self.lab)), (D("3"), None))
            self.assertEqual(StockMovement.objects.count(), 1)

    def test_a_transfer_to_the_same_place_is_refused(self):
        with tenant_context(self.school):
            self.stock(3)
            with self.assertRaises(serializers.ValidationError):
                services.transfer(item=self.chalk, from_location=self.store, to_location=self.store, quantity=D("1"))

    def test_transfer_legs_cannot_be_reversed_one_by_one(self):
        with tenant_context(self.school):
            self.stock(5)
            out, into = services.transfer(item=self.chalk, from_location=self.store, to_location=self.lab, quantity=D("2"))
            for leg in (out, into):
                with self.assertRaises(serializers.ValidationError):
                    services.reverse(leg, reason="oops")


class ReversalTests(InventoryFixture):
    def test_a_reversal_undoes_the_movement_and_links_to_it(self):
        with tenant_context(self.school):
            received = self.stock(10)
            issued = self.issue(4)
            undo = services.reverse(issued, reason="Wrong teacher", user_id=self.owner.id)
            self.assertEqual((undo.kind, undo.quantity_delta, undo.reverses_id), (Kind.REVERSAL, D("4"), issued.id))
            self.assertEqual(self.level(), D("10"))
            undo_receive = services.reverse(received, reason="Duplicate entry")
            self.assertEqual(undo_receive.quantity_delta, D("-10"))
            self.assertEqual(self.level(), D("0"))

    def test_a_movement_can_only_be_reversed_once_and_a_reversal_never(self):
        with tenant_context(self.school):
            self.stock(10)
            issued = self.issue(2)
            undo = services.reverse(issued, reason="x")
            with self.assertRaises(serializers.ValidationError):
                services.reverse(issued, reason="again")
            with self.assertRaises(serializers.ValidationError):
                services.reverse(undo, reason="undo the undo")
            self.assertEqual(self.level(), D("10"))

    def test_reversing_stock_that_has_since_been_used_is_refused(self):
        with tenant_context(self.school):
            received = self.stock(5)
            self.issue(4)
            with self.assertRaises(serializers.ValidationError):
                services.reverse(received, reason="Entered twice")
            self.assertEqual(self.level(), D("1"))
            self.assertFalse(StockMovement.objects.filter(reverses=received).exists())

    def test_a_reason_is_required(self):
        with tenant_context(self.school):
            self.stock(5)
            issued = self.issue(1)
            with self.assertRaises(serializers.ValidationError):
                services.reverse(issued, reason="")


class LedgerIntegrityTests(InventoryFixture):
    def test_the_level_always_equals_the_sum_of_the_movements(self):
        with tenant_context(self.school):
            self.stock(20)
            self.stock(5, location=self.lab)
            moved = self.issue(3)
            services.transfer(item=self.chalk, from_location=self.store, to_location=self.lab, quantity=D("6"))
            services.record(item=self.chalk, location=self.lab, kind=Kind.WRITE_OFF, quantity=D("2"), reason="Broken")
            services.reverse(moved, reason="Cancelled")
            services.record(item=self.chalk, location=self.store, kind=Kind.ADJUST_OUT, quantity=D("1"), reason="Count")
            for location in (self.store, self.lab):
                self.assertEqual(self.level(location=location), self.ledger_sum(location=location))
            last = StockMovement.objects.filter(location=self.store).order_by("created_at", "id").last()
            self.assertEqual(last.balance_after, self.level())

    def test_movements_are_immutable(self):
        with tenant_context(self.school):
            movement = self.stock(5)
            movement.reason = "changed"
            with self.assertRaises(RuntimeError):
                movement.save()
            with self.assertRaises(RuntimeError):
                movement.delete()
            self.assertEqual(StockMovement.objects.get(pk=movement.pk).reason, "")

    def test_the_database_itself_refuses_a_negative_balance_or_a_zero_movement(self):
        with tenant_context(self.school):
            self.stock(5)
            with self.assertRaises(IntegrityError), transaction.atomic():
                StockLevel.objects.filter(item=self.chalk).update(quantity=D("-1"))
            with self.assertRaises(IntegrityError), transaction.atomic():
                StockMovement.objects.create(item=self.chalk, location=self.store, kind=Kind.RECEIVE,
                                             quantity_delta=D("0"), balance_after=D("5"))
            with self.assertRaises(IntegrityError), transaction.atomic():
                Item.objects.filter(pk=self.chalk.pk).update(reorder_level=D("-1"))

    def test_one_level_row_per_item_and_location(self):
        with tenant_context(self.school):
            self.stock(1)
            with self.assertRaises(IntegrityError), transaction.atomic():
                StockLevel.objects.create(item=self.chalk, location=self.store, quantity=D("1"))

    def test_history_protects_items_and_locations_from_deletion(self):
        from django.db.models.deletion import ProtectedError
        with tenant_context(self.school):
            self.stock(1)
            for record in (self.chalk, self.store, self.category):
                with self.assertRaises(ProtectedError):
                    record.delete()


class ConcurrencyTests(InventoryFixture):
    def _race(self, count, work):
        barrier = threading.Barrier(count)
        results, errors = [], []

        def run(index):
            try:
                with schema_context(self.SCHEMA_A):
                    barrier.wait(timeout=30)
                    results.append(work(index))
            except serializers.ValidationError:
                results.append("refused")
            except Exception as exc:  # noqa: BLE001 - reported by the assertion below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=90)
        self.assertEqual(errors, [])
        return results

    def test_simultaneous_issues_of_the_last_units_never_oversell(self):
        with tenant_context(self.school):
            self.stock(3)
        results = self._race(6, lambda i: self.issue(1, to=f"Teacher {i}").pk)
        self.assertEqual(sum(1 for r in results if r == "refused"), 3)
        with tenant_context(self.school):
            self.assertEqual(self.level(), D("0"))
            self.assertEqual(self.ledger_sum(), D("0"))
            self.assertEqual(StockMovement.objects.filter(kind=Kind.ISSUE).count(), 3)

    def test_the_first_receipts_into_a_new_location_make_one_level_row(self):
        results = self._race(5, lambda i: self.stock(2, location=self.lab).pk)
        self.assertEqual(len(results), 5)
        with tenant_context(self.school):
            self.assertEqual(StockLevel.objects.filter(item=self.chalk, location=self.lab).count(), 1)
            self.assertEqual(self.level(location=self.lab), D("10"))
            self.assertEqual(self.ledger_sum(location=self.lab), D("10"))

    def test_two_people_reversing_the_same_movement_make_one_reversal(self):
        with tenant_context(self.school):
            self.stock(10)
            issued = self.issue(4)
        results = self._race(2, lambda i: services.reverse(issued, reason=f"by {i}").pk)
        self.assertEqual(sum(1 for r in results if r == "refused"), 1)
        with tenant_context(self.school):
            self.assertEqual(self.level(), D("10"))
            self.assertEqual(StockMovement.objects.filter(reverses=issued).count(), 1)

    def test_opposite_transfers_at_the_same_time_do_not_deadlock(self):
        with tenant_context(self.school):
            self.stock(10)
            self.stock(10, location=self.lab)

        def work(index):
            source, target = (self.store, self.lab) if index % 2 == 0 else (self.lab, self.store)
            return services.transfer(item=self.chalk, from_location=source, to_location=target, quantity=D("1"))[0].pk

        results = self._race(6, work)
        self.assertEqual(len(results), 6)
        with tenant_context(self.school):
            self.assertEqual(self.level() + self.level(location=self.lab), D("20"))
            for location in (self.store, self.lab):
                self.assertEqual(self.level(location=location), self.ledger_sum(location=location))


class ApiTests(InventoryFixture):
    def setUp(self):
        super().setUp()
        self.viewer = self._user("viewer", self.school, codenames=["view_inventory"])
        self.manager = self._user("manager", self.school, codenames=["view_inventory", "manage_inventory_items"])
        self.receiver = self._user("receiver", self.school, codenames=["view_inventory", "receive_stock"])
        self.issuer = self._user("issuer", self.school, codenames=["view_inventory", "issue_stock"])
        self.adjuster = self._user("adjuster", self.school, codenames=["view_inventory", "adjust_stock"])
        self.nobody = self._user("nobody", self.school, codenames=[])
        with tenant_context(self.school):
            self.stock(10)
            self.first_movement = StockMovement.objects.get()

    def body(self, **extra):
        data = {"item": str(self.chalk.id), "location": str(self.store.id), "quantity": "2"}
        data.update(extra)
        return data

    def test_every_endpoint_requires_the_right_permission(self):
        cases = [
            # (method, path, payload, who may, who may not)
            ("get", "items/", None, self.viewer, self.nobody),
            ("get", "stock/", None, self.viewer, self.nobody),
            ("get", "movements/", None, self.viewer, self.nobody),
            ("get", "categories/", None, self.viewer, self.nobody),
            ("get", "locations/", None, self.viewer, self.nobody),
            ("post", "categories/", {"name": "New"}, self.manager, self.viewer),
            ("post", "locations/", {"name": "New loc"}, self.manager, self.receiver),
            ("post", "items/", {"sku": "N-1", "name": "N", "category": str(self.category.id), "unit": "pcs"}, self.manager, self.issuer),
            ("post", "movements/receive/", self.body(), self.receiver, self.issuer),
            ("post", "movements/issue/", self.body(issued_to_note="x"), self.issuer, self.receiver),
            ("post", "movements/return/", self.body(), self.issuer, self.receiver),
            ("post", "movements/transfer/", {"item": str(self.chalk.id), "from_location": str(self.store.id),
                                             "to_location": str(self.lab.id), "quantity": "1"}, self.issuer, self.adjuster),
            ("post", "movements/adjust/", self.body(direction="in", reason="x"), self.adjuster, self.issuer),
            ("post", "movements/write-off/", self.body(reason="x"), self.adjuster, self.receiver),
            ("post", f"movements/{self.first_movement.id}/reverse/", {"reason": "x"}, self.adjuster, self.issuer),
        ]
        for method, path, payload, allowed, denied in cases:
            with self.subTest(path=path, method=method):
                self.assertEqual(self._call(denied, method, path, payload).status_code, 403)
                self.assertEqual(self._call(None, method, path, payload).status_code in (401, 403), True)
                self.assertIn(self._call(allowed, method, path, payload).status_code, (200, 201))

    def test_the_owner_may_do_everything(self):
        self.assertEqual(self._call(self.owner, "post", "movements/receive/", self.body()).status_code, 201)
        self.assertEqual(self._call(self.owner, "get", "items/").status_code, 200)

    def test_the_new_permissions_exist_and_the_owner_role_holds_them_but_other_system_roles_do_not(self):
        self.assertTrue(PERMISSIONS <= {p["codename"] for p in SYSTEM_PERMISSIONS})
        with tenant_context(self.school):
            self.assertTrue(PERMISSIONS <= set(Role.objects.get(slug="owner").permissions.values_list("codename", flat=True)))
            for slug in ("staff", "instructor", "student", "parent"):
                held = set(Role.objects.get(slug=slug).permissions.values_list("codename", flat=True))
                self.assertFalse(held & PERMISSIONS, slug)

    def test_schools_cannot_see_each_others_inventory(self):
        user_b = self._user("owner_b", self.school_b, role_slug="owner")
        self.assertEqual(self._call(user_b, "get", "items/", host=self.DOMAIN_B).data["results"], [])
        self.assertEqual(self._call(user_b, "get", f"items/{self.chalk.id}/", host=self.DOMAIN_B).status_code, 404)
        self.assertEqual(self._call(user_b, "post", "movements/issue/", self.body(issued_to_note="x"), host=self.DOMAIN_B).status_code, 400)
        # a member of school B has no standing in school A
        self.assertEqual(self._call(user_b, "get", "items/", host=self.DOMAIN_A).status_code, 403)

    def test_receive_issue_and_the_ledger_end_to_end(self):
        resp = self._call(self.owner, "post", "movements/receive/", self.body(quantity="5", unit_cost="12.50", reference="PO-9"))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual((resp.data["kind"], resp.data["balance_after"]), ("receive", "15.000"))
        resp = self._call(self.owner, "post", "movements/issue/", self.body(quantity="3", issued_to_staff=str(self.keeper.id)))
        self.assertEqual((resp.status_code, resp.data["balance_after"]), (201, "12.000"))
        listing = self._call(self.owner, "get", f"movements/?item={self.chalk.id}")
        self.assertEqual(listing.data["count"], 3)
        self.assertEqual(self._call(self.owner, "get", "movements/?kind=issue").data["count"], 1)

    def test_bad_input_is_a_clean_400_never_a_500(self):
        bad = [
            ("movements/receive/", self.body(quantity="0")),
            ("movements/receive/", self.body(quantity="-1")),
            ("movements/receive/", self.body(quantity="abc")),
            ("movements/receive/", self.body(quantity="0.0005")),
            ("movements/receive/", self.body(quantity="99999999999")),
            ("movements/receive/", self.body(item=str(uuid.uuid4()))),
            ("movements/receive/", self.body(location="not-a-uuid")),
            ("movements/receive/", {}),
            ("movements/receive/", self.body(unit_cost="-1")),
            ("movements/issue/", self.body(quantity="999", issued_to_note="x")),
            ("movements/issue/", self.body()),
            ("movements/adjust/", self.body(direction="sideways", reason="x")),
            ("movements/adjust/", self.body(direction="in")),
            ("movements/write-off/", self.body()),
            ("movements/transfer/", {"item": str(self.chalk.id), "from_location": str(self.store.id),
                                     "to_location": str(self.store.id), "quantity": "1"}),
        ]
        for path, payload in bad:
            with self.subTest(path=path, payload=payload):
                self.assertEqual(self._call(self.owner, "post", path, payload).status_code, 400)

    def test_nothing_changes_when_a_request_is_refused(self):
        self._call(self.owner, "post", "movements/issue/", self.body(quantity="999", issued_to_note="x"))
        with tenant_context(self.school):
            self.assertEqual(self.level(), D("10"))
            self.assertEqual(StockMovement.objects.count(), 1)

    def test_every_change_is_written_to_the_audit_log(self):
        self._call(self.owner, "post", "movements/receive/", self.body())
        self._call(self.owner, "post", "movements/issue/", self.body(issued_to_note="x"))
        self._call(self.owner, "post", "movements/transfer/", {"item": str(self.chalk.id), "from_location": str(self.store.id),
                                                               "to_location": str(self.lab.id), "quantity": "1"})
        with tenant_context(self.school):
            actions = list(AuditLog.objects.filter(model_name="StockMovement").values_list("action", flat=True))
            self.assertEqual(sorted(actions), sorted(["stock_received", "stock_issued", "stock_transferred", "stock_transferred"]))
            entry = AuditLog.objects.filter(action="stock_issued").first()
            self.assertEqual(entry.actor_id, self.owner.id)
            self.assertEqual(entry.changes["delta"], "-2.000")

    def test_reverse_endpoint(self):
        issued = self._call(self.owner, "post", "movements/issue/", self.body(issued_to_note="x")).data["id"]
        resp = self._call(self.owner, "post", f"movements/{issued}/reverse/", {"reason": "Mistake"})
        self.assertEqual((resp.status_code, resp.data["kind"], resp.data["balance_after"]), (201, "reversal", "10.000"))
        self.assertEqual(self._call(self.owner, "post", f"movements/{issued}/reverse/", {"reason": "again"}).status_code, 400)
        self.assertTrue(self._call(self.owner, "get", f"movements/{issued}/").data["reversed"])
        self.assertEqual(self._call(self.owner, "post", f"movements/{issued}/reverse/", {}).status_code, 400)

    def test_the_ledger_cannot_be_written_directly(self):
        with tenant_context(self.school):
            level_id = StockLevel.objects.first().id
        for method, path in (("post", "movements/"), ("put", f"movements/{self.first_movement.id}/"),
                             ("patch", f"movements/{self.first_movement.id}/"), ("delete", f"movements/{self.first_movement.id}/"),
                             ("post", "stock/"), ("delete", f"stock/{level_id}/")):
            with self.subTest(method=method, path=path):
                self.assertEqual(self._call(self.owner, method, path, {}).status_code, 405)

    def test_items_report_on_hand_and_low_stock(self):
        with tenant_context(self.school):
            pens = Item.objects.create(sku="PEN-1", name="Pens", category=self.category, unit="pcs", reorder_level=D("0"))
            gum = Item.objects.create(sku="GUM-1", name="Glue", category=self.category, unit="pcs", reorder_level=D("4"))
            services.record(item=pens, location=self.store, kind=Kind.RECEIVE, quantity=D("1"))
            services.record(item=gum, location=self.store, kind=Kind.RECEIVE, quantity=D("1"))
            Item.objects.filter(pk=gum.pk).update(is_active=False)  # stock 1 <= level 4, but inactive
        rows = {r["sku"]: r for r in self._call(self.owner, "get", "items/").data["results"]}
        self.assertEqual((rows["CHK-1"]["on_hand"], rows["CHK-1"]["low_stock"]), ("10.000", False))
        self.assertFalse(rows["PEN-1"]["low_stock"])  # reorder level 0 means never low
        self.assertFalse(rows["GUM-1"]["low_stock"])  # inactive items are never low
        self._call(self.owner, "post", "movements/issue/", self.body(quantity="6", issued_to_note="x"))
        self.assertEqual({r["sku"] for r in self._call(self.owner, "get", "items/?low_stock=true").data["results"]}, {"CHK-1"})
        self.assertEqual(self._call(self.owner, "get", "items/?low_stock=true").data["results"][0]["on_hand"], "4.000")

    def test_on_hand_adds_up_across_locations(self):
        with tenant_context(self.school):
            self.stock(7, location=self.lab)
        row = self._call(self.owner, "get", f"items/{self.chalk.id}/").data
        self.assertEqual(row["on_hand"], "17.000")
        levels = self._call(self.owner, "get", f"stock/?item={self.chalk.id}").data["results"]
        self.assertEqual(sorted(l["quantity"] for l in levels), ["10.000", "7.000"])

    def test_updating_an_item_reports_its_real_stock(self):
        resp = self._call(self.owner, "patch", f"items/{self.chalk.id}/", {"name": "Chalk (white)"})
        self.assertEqual((resp.status_code, resp.data["on_hand"], resp.data["low_stock"]), (200, "10.000", False))

    def test_items_cannot_be_deleted_but_can_be_deactivated(self):
        self.assertEqual(self._call(self.owner, "delete", f"items/{self.chalk.id}/").status_code, 405)
        resp = self._call(self.owner, "patch", f"items/{self.chalk.id}/", {"is_active": False})
        self.assertEqual((resp.status_code, resp.data["is_active"]), (200, False))
        self.assertEqual(self._call(self.owner, "post", "movements/receive/", self.body()).status_code, 400)

    def test_configuration_records_in_use_cannot_be_deleted(self):
        self.assertEqual(self._call(self.owner, "delete", f"categories/{self.category.id}/").status_code, 409)
        self.assertEqual(self._call(self.owner, "delete", f"locations/{self.store.id}/").status_code, 409)
        spare = self._call(self.owner, "post", "locations/", {"name": "Spare"}).data["id"]
        self.assertEqual(self._call(self.owner, "delete", f"locations/{spare}/").status_code, 204)

    def test_item_validation(self):
        payload = {"sku": "CHK-1", "name": "Dup", "category": str(self.category.id), "unit": "pcs"}
        self.assertEqual(self._call(self.owner, "post", "items/", payload).status_code, 400)  # duplicate SKU
        payload.update(sku="OK-1", reorder_level="-1")
        self.assertEqual(self._call(self.owner, "post", "items/", payload).status_code, 400)
        payload.update(reorder_level="3")
        self.assertEqual(self._call(self.owner, "post", "items/", payload).status_code, 201)
        self.assertEqual(self._call(self.owner, "post", "categories/", {"name": "Stationery"}).status_code, 400)

    def test_list_filters_and_search(self):
        self.assertEqual(self._call(self.owner, "get", "items/?search=chalk").data["count"], 1)
        self.assertEqual(self._call(self.owner, "get", "items/?search=zzz").data["count"], 0)
        self.assertEqual(self._call(self.owner, "get", f"items/?category={self.category.id}").data["count"], 1)
        self.assertEqual(self._call(self.owner, "get", "locations/?is_active=false").data["count"], 0)
        with tenant_context(self.school):
            self.issue(10)
        self.assertEqual(self._call(self.owner, "get", "stock/?hide_empty=true").data["count"], 0)
        self.assertEqual(self._call(self.owner, "get", "stock/").data["count"], 1)
