"""Inventory Stage I3: the asset register (registration, assignment, repair, lost/found, disposal).

Creates tenant schemas and uses real threads for the race cases, so it needs a disposable
PostgreSQL database and is meant to be run only in an isolated test stage.
"""
import threading
from decimal import Decimal

from django.db import IntegrityError, connections, transaction
from django.db.models.deletion import ProtectedError
from django_tenants.utils import schema_context, tenant_context
from rest_framework import serializers

from core.models import AuditLog
from profiles.models import Profile
from staff.models import StaffMember

from . import asset_services as svc
from .models import Asset, AssetAssignment, AssetCategory, AssetEvent, MaintenanceRecord, Supplier
from .tests import D, InventoryFixture

Status = Asset.Status


class AssetFixture(InventoryFixture):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.laptops = AssetCategory.objects.create(name="Computers")
            self.supplier = Supplier.objects.create(name="Dell Nepal")
            self.asset = Asset.objects.create(tag="A-001", name="Teacher laptop", category=self.laptops,
                                              serial_number="SN123", purchase_cost=D("85000.00"))
            self.second = Asset.objects.create(tag="A-002", name="Projector", category=self.laptops)
            self.ravi = StaffMember.objects.create(
                profile=Profile.objects.create(first_name="Ravi", last_name="Shrestha"), employee_id="E-AS-1",
                designation="Teacher")
            self.retired = StaffMember.objects.create(
                profile=Profile.objects.create(first_name="Old", last_name="Timer"), employee_id="E-AS-2",
                designation="Teacher", is_active=False)

    def fresh(self, asset=None):
        return Asset.objects.get(pk=(asset or self.asset).pk)

    def events(self, asset=None):
        return list(AssetEvent.objects.filter(asset=asset or self.asset).order_by("created_at", "id")
                    .values_list("kind", "from_status", "to_status"))


class LifecycleTests(AssetFixture):
    def test_registering_records_the_event_and_starts_available(self):
        with tenant_context(self.school):
            asset = svc.register(user_id=self.owner.id, tag="A-100", name="Desk", category=self.laptops, location=self.lab)
            self.assertEqual((asset.status, asset.location_id), (Status.AVAILABLE, self.lab.id))
            self.assertEqual(self.events(asset), [("registered", "", "available")])

    def test_assign_and_return(self):
        with tenant_context(self.school):
            svc.assign(self.asset, user_id=self.owner.id, staff=self.ravi, location=self.lab, note="Class 7 room")
            asset = self.fresh()
            self.assertEqual((asset.status, asset.location_id), (Status.ASSIGNED, self.lab.id))
            open_rows = AssetAssignment.objects.filter(asset=asset, returned_at__isnull=True)
            self.assertEqual((open_rows.count(), open_rows.first().staff_id), (1, self.ravi.id))
            svc.return_asset(self.asset, user_id=self.owner.id, location=self.store, condition="fair")
            asset = self.fresh()
            self.assertEqual((asset.status, asset.location_id, asset.condition), (Status.AVAILABLE, self.store.id, "fair"))
            closed = AssetAssignment.objects.get(asset=asset)
            self.assertIsNotNone(closed.returned_at)
            self.assertEqual((closed.return_condition, closed.returned_by_user_id), ("fair", self.owner.id))
            self.assertEqual([e[0] for e in self.events()], ["assigned", "returned"])

    def test_an_assignment_needs_a_holder_and_an_active_staff_member(self):
        with tenant_context(self.school):
            with self.assertRaises(serializers.ValidationError):
                svc.assign(self.asset)
            with self.assertRaises(serializers.ValidationError):
                svc.assign(self.asset, staff=self.retired)
            StockLocation = type(self.store)
            StockLocation.objects.filter(pk=self.lab.pk).update(is_active=False)
            self.lab.refresh_from_db()
            with self.assertRaises(serializers.ValidationError):
                svc.assign(self.asset, location=self.lab)
            self.assertEqual(self.fresh().status, Status.AVAILABLE)
            svc.assign(self.asset, note="Science club")  # a note alone is a valid holder
            self.assertEqual(self.fresh().status, Status.ASSIGNED)

    def test_only_available_assets_can_be_assigned_and_only_assigned_ones_returned(self):
        with tenant_context(self.school):
            with self.assertRaises(serializers.ValidationError):
                svc.return_asset(self.asset)
            svc.assign(self.asset, staff=self.ravi)
            with self.assertRaises(serializers.ValidationError):
                svc.assign(self.asset, staff=self.ravi)
            svc.send_to_repair(self.asset, reason="Screen")
            with self.assertRaises(serializers.ValidationError):
                svc.assign(self.asset, staff=self.ravi)

    def test_repair_cycle_closes_the_assignment_and_records_the_cost(self):
        with tenant_context(self.school):
            svc.assign(self.asset, staff=self.ravi)
            svc.send_to_repair(self.asset, reason="Cracked screen", user_id=self.owner.id)
            self.assertEqual(self.fresh().status, Status.IN_REPAIR)
            self.assertEqual(AssetAssignment.objects.filter(asset=self.asset, returned_at__isnull=True).count(), 0)
            with self.assertRaises(serializers.ValidationError):
                svc.send_to_repair(self.asset, reason="again")
            svc.complete_repair(self.asset, user_id=self.owner.id, cost=D("4500.00"), notes="New panel", condition="good")
            asset = self.fresh()
            self.assertEqual((asset.status, asset.condition), (Status.AVAILABLE, "good"))
            record = MaintenanceRecord.objects.get(asset=asset)
            self.assertEqual((record.reason, record.cost, record.notes), ("Cracked screen", D("4500.00"), "New panel"))
            self.assertIsNotNone(record.closed_at)
            self.assertEqual([e[0] for e in self.events()], ["assigned", "sent_to_repair", "repaired"])

    def test_repair_needs_a_reason_and_a_non_negative_cost(self):
        with tenant_context(self.school):
            with self.assertRaises(serializers.ValidationError):
                svc.send_to_repair(self.asset, reason="  ")
            svc.send_to_repair(self.asset, reason="Fan noise")
            with self.assertRaises(serializers.ValidationError):
                svc.complete_repair(self.asset, cost=D("-1"))
            self.assertEqual(self.fresh().status, Status.IN_REPAIR)

    def test_lost_and_found(self):
        with tenant_context(self.school):
            svc.assign(self.asset, staff=self.ravi)
            with self.assertRaises(serializers.ValidationError):
                svc.mark_lost(self.asset, reason="")
            svc.mark_lost(self.asset, reason="Left on a bus", user_id=self.owner.id)
            self.assertEqual(self.fresh().status, Status.LOST)
            self.assertEqual(AssetAssignment.objects.filter(asset=self.asset, returned_at__isnull=True).count(), 0)
            for blocked in (lambda: svc.assign(self.asset, staff=self.ravi), lambda: svc.send_to_repair(self.asset, reason="x")):
                with self.assertRaises(serializers.ValidationError):
                    blocked()
            svc.mark_found(self.asset, location=self.store)
            asset = self.fresh()
            self.assertEqual((asset.status, asset.location_id), (Status.AVAILABLE, self.store.id))
            with self.assertRaises(serializers.ValidationError):
                svc.mark_found(self.asset)

    def test_disposal_is_final(self):
        with tenant_context(self.school):
            svc.assign(self.asset, staff=self.ravi)
            with self.assertRaises(serializers.ValidationError):
                svc.dispose(self.asset, reason="Scrapped")  # must be returned first
            svc.return_asset(self.asset)
            with self.assertRaises(serializers.ValidationError):
                svc.dispose(self.asset, reason="")
            svc.dispose(self.asset, reason="Beyond repair", user_id=self.owner.id)
            asset = self.fresh()
            self.assertEqual((asset.status, asset.disposal_reason), (Status.DISPOSED, "Beyond repair"))
            self.assertIsNotNone(asset.disposed_at)
            for blocked in (lambda: svc.assign(self.asset, staff=self.ravi), lambda: svc.send_to_repair(self.asset, reason="x"),
                            lambda: svc.mark_lost(self.asset, reason="x"), lambda: svc.mark_found(self.asset),
                            lambda: svc.dispose(self.asset, reason="x"), lambda: svc.move(self.asset, location=self.lab)):
                with self.assertRaises(serializers.ValidationError):
                    blocked()

    def test_a_lost_asset_can_be_disposed_of(self):
        with tenant_context(self.school):
            svc.mark_lost(self.asset, reason="Stolen")
            svc.dispose(self.asset, reason="Written off after police report")
            self.assertEqual(self.fresh().status, Status.DISPOSED)

    def test_move(self):
        with tenant_context(self.school):
            svc.move(self.asset, location=self.lab, user_id=self.owner.id)
            self.assertEqual(self.fresh().location_id, self.lab.id)
            with self.assertRaises(serializers.ValidationError):
                svc.move(self.asset, location=self.lab)
            with self.assertRaises(serializers.ValidationError):
                svc.move(self.asset, location=None)
            self.assertEqual(self.events()[-1], ("moved", "available", "available"))


class IntegrityTests(AssetFixture):
    def test_events_are_immutable(self):
        with tenant_context(self.school):
            svc.assign(self.asset, staff=self.ravi)
            event = AssetEvent.objects.first()
            event.note = "changed"
            with self.assertRaises(RuntimeError):
                event.save()
            with self.assertRaises(RuntimeError):
                event.delete()

    def test_the_database_allows_one_open_assignment_and_one_open_repair(self):
        with tenant_context(self.school):
            svc.assign(self.asset, staff=self.ravi)
            with self.assertRaises(IntegrityError), transaction.atomic():
                AssetAssignment.objects.create(asset=self.asset, note="second")
            with self.assertRaises(IntegrityError), transaction.atomic():
                AssetAssignment.objects.create(asset=self.second)  # no holder at all
            MaintenanceRecord.objects.create(asset=self.second, reason="a")
            with self.assertRaises(IntegrityError), transaction.atomic():
                MaintenanceRecord.objects.create(asset=self.second, reason="b")

    def test_other_database_rules(self):
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Asset.objects.filter(pk=self.asset.pk).update(purchase_cost=D("-1"))
            with self.assertRaises(IntegrityError), transaction.atomic():
                Asset.objects.filter(pk=self.asset.pk).update(status=Status.DISPOSED)  # no disposal date
            with self.assertRaises(IntegrityError), transaction.atomic():
                Asset.objects.create(tag="A-001", name="Duplicate tag", category=self.laptops)

    def test_history_protects_everything_it_points_at(self):
        with tenant_context(self.school):
            svc.assign(self.asset, staff=self.ravi, location=self.lab)
            for record in (self.asset, self.laptops, self.ravi, self.lab):
                with self.assertRaises(ProtectedError):
                    record.delete()


class ConcurrencyTests(AssetFixture):
    def test_two_people_assigning_the_same_asset_at_once_get_one_winner(self):
        barrier = threading.Barrier(4)
        outcomes, errors = [], []

        def run(index):
            try:
                with schema_context(self.SCHEMA_A):
                    barrier.wait(timeout=30)
                    svc.assign(self.asset, staff=self.ravi, note=f"person {index}")
                    outcomes.append("ok")
            except serializers.ValidationError:
                outcomes.append("refused")
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
        self.assertEqual((outcomes.count("ok"), outcomes.count("refused")), (1, 3))
        with tenant_context(self.school):
            self.assertEqual(AssetAssignment.objects.filter(asset=self.asset).count(), 1)
            self.assertEqual(self.fresh().status, Status.ASSIGNED)

    def test_assigning_while_it_is_sent_to_repair_leaves_a_consistent_state(self):
        barrier = threading.Barrier(2)
        errors = []

        def run(action):
            try:
                with schema_context(self.SCHEMA_A):
                    barrier.wait(timeout=30)
                    if action == "assign":
                        svc.assign(self.asset, staff=self.ravi)
                    else:
                        svc.send_to_repair(self.asset, reason="Race")
            except serializers.ValidationError:
                pass
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run, args=(a,)) for a in ("assign", "repair")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=90)
        self.assertEqual(errors, [])
        with tenant_context(self.school):
            asset = self.fresh()
            open_assignments = AssetAssignment.objects.filter(asset=asset, returned_at__isnull=True).count()
            open_repairs = MaintenanceRecord.objects.filter(asset=asset, closed_at__isnull=True).count()
            if asset.status == Status.ASSIGNED:
                self.assertEqual((open_assignments, open_repairs), (1, 0))
            else:
                self.assertEqual((asset.status, open_assignments, open_repairs), (Status.IN_REPAIR, 0, 1))


class AssetApiTests(AssetFixture):
    def setUp(self):
        super().setUp()
        self.viewer = self._user("viewer", self.school, codenames=["view_assets"])
        self.manager = self._user("manager", self.school, codenames=["view_assets", "manage_assets"])
        self.assigner = self._user("assigner", self.school, codenames=["view_assets", "assign_assets"])
        self.stock_only = self._user("stockonly", self.school, codenames=["view_inventory", "manage_inventory_items"])
        self.nobody = self._user("nobody", self.school, codenames=[])

    def url(self, suffix=""):
        return f"assets/{self.asset.id}/{suffix}"

    def test_permissions(self):
        cases = [
            ("get", "assets/", None, self.viewer, self.nobody),
            ("get", "assets/summary/", None, self.viewer, self.stock_only),
            ("get", self.url(), None, self.viewer, self.stock_only),
            ("get", self.url("history/"), None, self.viewer, self.nobody),
            ("get", self.url("assignments/"), None, self.viewer, self.nobody),
            ("get", self.url("maintenance/"), None, self.viewer, self.nobody),
            ("get", "asset-categories/", None, self.viewer, self.nobody),
            ("post", "asset-categories/", {"name": "Furniture"}, self.manager, self.assigner),
            ("post", "assets/", {"tag": "N-1", "name": "New", "category": str(self.laptops.id)}, self.manager, self.assigner),
            ("patch", self.url(), {"name": "Renamed"}, self.manager, self.assigner),
            ("post", self.url("assign/"), {"note": "Class"}, self.assigner, self.manager),
            ("post", self.url("repair/"), {"reason": "x"}, self.manager, self.assigner),
        ]
        for method, path, data, allowed, denied in cases:
            with self.subTest(path=path, method=method):
                self.assertEqual(self._call(denied, method, path, data).status_code, 403)
                self.assertIn(self._call(None, method, path, data).status_code, (401, 403))
                self.assertIn(self._call(allowed, method, path, data).status_code, (200, 201))

    def test_return_move_and_the_other_lifecycle_actions_need_the_right_permission(self):
        for path, data, allowed, denied in [
            ("return/", {}, self.assigner, self.manager),
            ("move/", {"location": str(self.lab.id)}, self.assigner, self.manager),
            ("complete-repair/", {}, self.manager, self.assigner),
            ("lost/", {"reason": "x"}, self.manager, self.assigner),
            ("found/", {}, self.manager, self.assigner),
            ("dispose/", {"reason": "x"}, self.manager, self.assigner),
        ]:
            with self.subTest(path=path):
                self.assertEqual(self._call(denied, "post", self.url(path), data).status_code, 403)
                # allowed may still get 400 because of the asset's current state, but never 403
                self.assertNotEqual(self._call(allowed, "post", self.url(path), data).status_code, 403)

    def test_new_permissions_exist_and_are_owner_only(self):
        from roles.constants import SYSTEM_PERMISSIONS
        from roles.models import Role
        names = {"view_assets", "manage_assets", "assign_assets"}
        self.assertTrue(names <= {p["codename"] for p in SYSTEM_PERMISSIONS})
        with tenant_context(self.school):
            self.assertTrue(names <= set(Role.objects.get(slug="owner").permissions.values_list("codename", flat=True)))
            for slug in ("staff", "instructor", "student", "parent"):
                self.assertFalse(names & set(Role.objects.get(slug=slug).permissions.values_list("codename", flat=True)))

    def test_full_lifecycle_through_the_api(self):
        call = lambda method, suffix, data=None: self._call(self.owner, method, self.url(suffix), data)  # noqa: E731
        resp = call("post", "assign/", {"staff": str(self.ravi.id), "location": str(self.lab.id), "note": "Lab use"})
        self.assertEqual((resp.status_code, resp.data["status"]), (200, "assigned"), resp.data)
        self.assertEqual(resp.data["current_assignment"]["staff_name"], "Ravi Shrestha")
        self.assertEqual(call("post", "assign/", {"note": "again"}).status_code, 400)
        self.assertEqual(call("post", "return/", {"condition": "fair", "location": str(self.store.id)}).data["status"], "available")
        self.assertIsNone(call("get", "").data["current_assignment"])
        self.assertEqual(call("post", "repair/", {"reason": "Fan"}).data["status"], "in_repair")
        resp = call("post", "complete-repair/", {"cost": "1200.50", "notes": "Fan replaced", "condition": "good"})
        self.assertEqual((resp.data["status"], resp.data["condition"]), ("available", "good"))
        self.assertEqual(call("post", "lost/", {"reason": "Misplaced"}).data["status"], "lost")
        self.assertEqual(call("post", "found/", {"location": str(self.store.id)}).data["status"], "available")
        self.assertEqual(str(call("post", "move/", {"location": str(self.lab.id)}).data["location"]), str(self.lab.id))
        self.assertEqual(call("post", "dispose/", {"reason": "Obsolete"}).data["status"], "disposed")
        kinds = [e["kind"] for e in call("get", "history/").data["results"]]
        self.assertEqual(kinds[::-1], ["assigned", "returned", "sent_to_repair", "repaired", "lost", "found", "moved", "disposed"])
        self.assertEqual(call("get", "assignments/").data["count"], 1)
        maintenance = call("get", "maintenance/").data["results"]
        self.assertEqual((len(maintenance), maintenance[0]["cost"]), (1, "1200.50"))

    def test_bad_input_is_a_clean_400(self):
        bad = [
            ("assign/", {}), ("assign/", {"staff": "not-a-uuid"}), ("assign/", {"staff": str(self.retired.id)}),
            ("assign/", {"location": "00000000-0000-0000-0000-000000000000"}),
            ("repair/", {}), ("repair/", {"reason": " "}), ("lost/", {}), ("dispose/", {}), ("move/", {}),
            ("return/", {}), ("complete-repair/", {}), ("found/", {}),
        ]
        for suffix, data in bad:
            with self.subTest(suffix=suffix, data=data):
                self.assertEqual(self._call(self.owner, "post", self.url(suffix), data).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", self.url("repair/"), {"reason": "x"}).status_code, 200)
        for data in ({"cost": "-5"}, {"cost": "abc"}, {"condition": "excellent"}):
            self.assertEqual(self._call(self.owner, "post", self.url("complete-repair/"), data).status_code, 400)
        self.assertEqual(self.fresh_status(), "in_repair")

    def fresh_status(self):
        with tenant_context(self.school):
            return self.fresh().status

    def test_registration_rules(self):
        base = {"tag": "B-1", "name": "Bench", "category": str(self.laptops.id)}
        resp = self._call(self.owner, "post", "assets/", {**base, "purchase_cost": "1500.00", "location": str(self.lab.id),
                                                        "supplier": str(self.supplier.id), "status": "disposed"})
        self.assertEqual((resp.status_code, resp.data["status"], resp.data["location_name"]), (201, "available", "Science lab"))
        for label, data in {
            "duplicate tag": {**base},
            "no tag": {"name": "x", "category": str(self.laptops.id)},
            "no category": {"tag": "B-2", "name": "x"},
            "negative cost": {**base, "tag": "B-3", "purchase_cost": "-1"},
            "unknown category": {**base, "tag": "B-4", "category": "00000000-0000-0000-0000-000000000000"},
        }.items():
            with self.subTest(label):
                self.assertEqual(self._call(self.owner, "post", "assets/", data).status_code, 400)

    def test_editing_never_changes_status_location_or_tag(self):
        resp = self._call(self.owner, "patch", self.url(), {"name": "Better laptop", "condition": "fair", "status": "disposed",
                                                         "location": str(self.lab.id)})
        self.assertEqual((resp.status_code, resp.data["name"], resp.data["status"], resp.data["location"]),
                         (200, "Better laptop", "available", None))
        resp = self._call(self.owner, "patch", self.url(), {"tag": "CHANGED"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._call(self.owner, "patch", self.url(), {"tag": "A-001", "serial_number": "SN999"}).status_code, 200)

    def test_assets_cannot_be_deleted(self):
        self.assertEqual(self._call(self.owner, "delete", self.url()).status_code, 405)
        self.assertEqual(self._call(self.owner, "delete", f"asset-categories/{self.laptops.id}/").status_code, 409)

    def test_filters_search_and_summary(self):
        self._call(self.owner, "post", self.url("assign/"), {"note": "Class"})
        self.assertEqual(self._call(self.owner, "get", "assets/?status=assigned").data["count"], 1)
        self.assertEqual(self._call(self.owner, "get", "assets/?search=sn123").data["count"], 1)
        self.assertEqual(self._call(self.owner, "get", "assets/?search=projector").data["count"], 1)
        self.assertEqual(self._call(self.owner, "get", f"assets/?category={self.laptops.id}").data["count"], 2)
        self._call(self.owner, "post", f"assets/{self.second.id}/dispose/", {"reason": "Old"})
        summary = self._call(self.owner, "get", "assets/summary/").data
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["by_status"], {"available": 0, "assigned": 1, "in_repair": 0, "lost": 0, "disposed": 1})
        self.assertEqual(summary["by_category"], [{"category": "Computers", "count": 1}])
        self.assertEqual(summary["purchase_cost_in_service"], "85000.00")

    def test_audit_log(self):
        self._call(self.owner, "post", "assets/", {"tag": "L-1", "name": "Lamp", "category": str(self.laptops.id)})
        self._call(self.owner, "post", self.url("assign/"), {"staff": str(self.ravi.id)})
        self._call(self.owner, "post", self.url("return/"), {})
        with tenant_context(self.school):
            actions = list(AuditLog.objects.filter(model_name="Asset").order_by("created_at").values_list("action", flat=True))
            self.assertEqual(actions, ["asset_registered", "asset_assigned", "asset_returned"])
            self.assertEqual(AuditLog.objects.filter(action="asset_assigned").first().actor_id, self.owner.id)

    def test_schools_are_separate(self):
        user_b = self._user("owner_b", self.school_b, role_slug="owner")
        self.assertEqual(self._call(user_b, "get", "assets/", host=self.DOMAIN_B).data["results"], [])
        self.assertEqual(self._call(user_b, "get", self.url(), host=self.DOMAIN_B).status_code, 404)
        self.assertEqual(self._call(user_b, "post", self.url("assign/"), {"note": "x"}, host=self.DOMAIN_B).status_code, 404)
        self.assertEqual(self._call(user_b, "get", "assets/", host=self.DOMAIN_A).status_code, 403)
