"""Stage 1 of automated alerts: settings, alert log, permissions and the dedupe helper.

No alert *trigger* exists yet, so everything here exercises the foundation directly. The tests
create tenant schemas and use real threads for the race cases, so they need a disposable
PostgreSQL database and are meant to be run only in an isolated test stage.
"""

import json
import threading
import uuid
from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.core import mail
from django.db import IntegrityError, connection, connections, transaction
from django.test import SimpleTestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django_tenants.utils import schema_context, tenant_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from core.models import AuditLog
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles import signals as role_signals
from roles.models import Permission, Role, UserRole
from students.models import Student

from . import alerts
from .models import AlertLog, EmailOutboxEvent, Notification, NotificationSettings

PASSWORD = "Pass1234!"
SETTINGS_URL = "/api/notifications/settings/"
LOG_URL = "/api/notifications/alert-log/"
NEW_PERMISSIONS = {"manage_notification_settings", "view_notification_log"}
DEFAULTS = {
    "fee_reminders_enabled": False,
    "absence_alerts_enabled": False,
    "payment_receipts_enabled": False,
    "low_stock_alerts_enabled": False,
    "fee_reminder_days_before": 3,
    "overdue_reminder_interval_days": 7,
    "max_overdue_reminders": 3,
}


class AlertFoundationFixture(TransactionTestCase):
    SCHEMA_A, DOMAIN_A = "alert_found_a", "alertfound-a.localhost"
    SCHEMA_B, DOMAIN_B = "alert_found_b", "alertfound-b.localhost"

    # ------------------------------------------------------------------ helpers
    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA_A, self.SCHEMA_B]):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="alf_").delete()

    def _school(self, schema, domain, name):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _user(self, username, *, school=None, role_slug=None, codenames=None, superuser=False, active=True):
        """A global user. With ``school`` and ``role_slug``/``codenames`` it becomes a member of that
        tenant (Profile first, then the role, so the profile signal never duplicates it)."""
        connection.set_schema_to_public()
        make = User.objects.create_superuser if superuser else User.objects.create_user
        user = make(username=username, email=f"{username}@alertfound.test", password=PASSWORD)
        if not active:
            user.is_active = False
            user.save(update_fields=["is_active"])
        if school is not None and (role_slug or codenames is not None):
            with tenant_context(school):
                Profile.objects.create(user_id=user.id, first_name=username, last_name="Member")
                if role_slug:
                    role = Role.objects.get(slug=role_slug)
                else:
                    slug = f"alf-{uuid.uuid4().hex[:10]}"
                    role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                    role.permissions.set(Permission.objects.filter(codename__in=codenames))
                UserRole.objects.create(user=user, role=role)
        return user

    def _as(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _cookie(self, user):
        connection.set_schema_to_public()
        client = APIClient()
        client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        return client

    def _req(self, client, method, path, host=None, data=None, **extra):
        return getattr(client, method)(path, data, format="json", HTTP_HOST=host or self.DOMAIN_A, **extra)

    @staticmethod
    def _ids(response):
        data = response.data["results"] if isinstance(response.data, dict) and "results" in response.data else response.data
        return [str(item["id"]) for item in data]

    def _settings_count(self, school):
        with tenant_context(school):
            return NotificationSettings.objects.count()

    # ------------------------------------------------------------------ fixture
    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school_a = self._school(self.SCHEMA_A, self.DOMAIN_A, "Alert Found A")
        self.school_b = self._school(self.SCHEMA_B, self.DOMAIN_B, "Alert Found B")

        self.owner = self._user("alf_owner", school=self.school_a, role_slug="owner")
        self.owner_b = self._user("alf_owner_b", school=self.school_b, role_slug="owner")
        self.superuser = self._user("alf_superuser", superuser=True)
        self.manager = self._user("alf_manager", school=self.school_a, codenames=["manage_notification_settings"])
        self.viewer = self._user("alf_viewer", school=self.school_a, codenames=["view_notification_log"])
        self.student_user = self._user("alf_student_user", school=self.school_a, role_slug="student")
        self.parent_user = self._user("alf_parent_user", school=self.school_a, role_slug="parent")
        self.plain_staff = self._user("alf_plain_staff", school=self.school_a, codenames=[])
        self.outsider = self._user("alf_outsider")  # global user, member of no tenant


class SettingsApiTests(AlertFoundationFixture):
    def test_get_returns_all_off_defaults_and_writes_nothing(self):
        resp = self._req(self._as(self.owner), "get", SETTINGS_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            dict(resp.data),
            {**DEFAULTS, "time_zone": "UTC", "is_default": True, "updated_at": None},
        )
        # Reading is read-only: still no row, no audit entry, even after repeated reads.
        self._req(self._as(self.owner), "get", SETTINGS_URL)
        self.assertEqual(self._settings_count(self.school_a), 0)
        with tenant_context(self.school_a):
            self.assertEqual(AuditLog.objects.filter(action="notification_settings_changed").count(), 0)

    def test_patch_creates_one_row_then_updates_it_and_audits_each_change(self):
        owner = self._as(self.owner)
        resp = self._req(owner, "patch", SETTINGS_URL, data={"fee_reminders_enabled": True, "fee_reminder_days_before": 5})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data["fee_reminders_enabled"])
        self.assertEqual(resp.data["fee_reminder_days_before"], 5)
        self.assertFalse(resp.data["is_default"])
        self.assertIsNotNone(resp.data["updated_at"])
        self.assertEqual(self._settings_count(self.school_a), 1)

        resp = self._req(owner, "patch", SETTINGS_URL, data={"max_overdue_reminders": 4})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._settings_count(self.school_a), 1)
        # Partial update: earlier changes are kept.
        self.assertTrue(resp.data["fee_reminders_enabled"])
        self.assertEqual(resp.data["fee_reminder_days_before"], 5)
        self.assertEqual(resp.data["max_overdue_reminders"], 4)
        self.assertEqual(self._req(owner, "get", SETTINGS_URL).data["max_overdue_reminders"], 4)

        with tenant_context(self.school_a):
            entries = list(AuditLog.objects.filter(action="notification_settings_changed").order_by("created_at"))
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].changes["old"]["fee_reminders_enabled"], False)
            self.assertEqual(entries[0].changes["new"]["fee_reminders_enabled"], True)
            self.assertEqual(entries[1].changes["old"]["max_overdue_reminders"], 3)
            self.assertEqual(entries[1].changes["new"]["max_overdue_reminders"], 4)
            self.assertEqual(entries[1].actor_username, self.owner.username)
            self.assertEqual(NotificationSettings.objects.get().updated_by_user_id, self.owner.id)

    def test_settings_are_independent_per_tenant(self):
        self._req(self._as(self.owner), "patch", SETTINGS_URL, data={"absence_alerts_enabled": True})
        resp = self._req(self._as(self.owner_b), "get", SETTINGS_URL, host=self.DOMAIN_B)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["absence_alerts_enabled"])
        self.assertTrue(resp.data["is_default"])
        self.assertEqual(self._settings_count(self.school_b), 0)
        # School A's owner has no standing in school B.
        resp = self._req(self._as(self.owner), "get", SETTINGS_URL, host=self.DOMAIN_B)
        self.assertEqual(resp.status_code, 403)

    def test_invalid_input_is_rejected_and_nothing_is_written(self):
        owner = self._as(self.owner)
        bad_payloads = [
            {"fee_reminder_days_before": -1}, {"fee_reminder_days_before": 31},
            {"overdue_reminder_interval_days": 0}, {"overdue_reminder_interval_days": 31},
            {"max_overdue_reminders": 0}, {"max_overdue_reminders": 11},
            {"fee_reminder_days_before": "abc"}, {"fee_reminder_days_before": 3.5},
            {"fee_reminders_enabled": "yes"}, {"fee_reminders_enabled": 1}, {"absence_alerts_enabled": None},
            {"id": str(uuid.uuid4())}, {"singleton": False}, {"time_zone": "Asia/Kathmandu"},
            {"is_default": False}, {"updated_at": "2026-01-01T00:00:00Z"}, {"unknown_field": 1},
            {"fee_reminder_days_before": 5, "unknown_field": 1},  # one bad key rejects the whole request
            {},
        ]
        for payload in bad_payloads:
            resp = self._req(owner, "patch", SETTINGS_URL, data=payload)
            self.assertEqual(resp.status_code, 400, payload)
        self.assertEqual(self._settings_count(self.school_a), 0)
        with tenant_context(self.school_a):
            self.assertEqual(AuditLog.objects.filter(action="notification_settings_changed").count(), 0)

        # With an existing row, rejected requests leave every stored value unchanged.
        self._req(owner, "patch", SETTINGS_URL, data={"fee_reminder_days_before": 9})
        with tenant_context(self.school_a):
            before = NotificationSettings.objects.get().editable_values()
            audit_before = AuditLog.objects.filter(action="notification_settings_changed").count()
        self.assertEqual(self._req(owner, "patch", SETTINGS_URL, data={"fee_reminder_days_before": 5, "max_overdue_reminders": 99}).status_code, 400)
        with tenant_context(self.school_a):
            self.assertEqual(NotificationSettings.objects.get().editable_values(), before)
            self.assertEqual(AuditLog.objects.filter(action="notification_settings_changed").count(), audit_before)

    def test_only_get_and_patch_exist(self):
        owner = self._as(self.owner)
        for method in ("put", "post", "delete"):
            self.assertEqual(self._req(owner, method, SETTINGS_URL, data={"fee_reminders_enabled": True}).status_code, 405, method)
        for method in ("put", "post", "patch", "delete"):
            self.assertEqual(self._req(owner, method, LOG_URL, data={}).status_code, 405, method)
        self.assertEqual(self._settings_count(self.school_a), 0)

    def test_access_matrix(self):
        patch = {"payment_receipts_enabled": True}

        # (user, GET settings, PATCH settings, GET log)
        expectations = [
            (self.owner, 200, 200, 200),
            (self.superuser, 200, 200, 200),
            (self.manager, 200, 200, 403),
            (self.viewer, 200, 403, 200),
            (self.student_user, 403, 403, 403),
            (self.parent_user, 403, 403, 403),
            (self.plain_staff, 403, 403, 403),
            (self.outsider, 403, 403, 403),  # authenticated but not a member: explicit permission refuses
        ]
        for user, get_status, patch_status, log_status in expectations:
            client = self._as(user)
            self.assertEqual(self._req(client, "get", SETTINGS_URL).status_code, get_status, f"GET settings as {user.username}")
            self.assertEqual(self._req(client, "patch", SETTINGS_URL, data=patch).status_code, patch_status, f"PATCH settings as {user.username}")
            self.assertEqual(self._req(client, "get", LOG_URL).status_code, log_status, f"GET log as {user.username}")

        # Through real cookie authentication the non-member is not authenticated at all.
        self.assertEqual(self._req(self._cookie(self.outsider), "get", SETTINGS_URL).status_code, 401)
        self.assertEqual(self._req(self._cookie(self.outsider), "get", LOG_URL).status_code, 401)
        self.assertEqual(self._req(self._cookie(self.owner), "get", SETTINGS_URL).status_code, 200)
        self.assertEqual(self._req(APIClient(), "get", SETTINGS_URL).status_code, 401)

    def test_a_failing_audit_write_does_not_undo_the_change(self):
        with mock.patch.object(AuditLog.objects, "create", side_effect=RuntimeError("audit unavailable")):
            resp = self._req(self._as(self.owner), "patch", SETTINGS_URL, data={"fee_reminders_enabled": True})
        self.assertEqual(resp.status_code, 200)
        with tenant_context(self.school_a):
            self.assertTrue(NotificationSettings.objects.get().fee_reminders_enabled)
            self.assertEqual(AuditLog.objects.filter(action="notification_settings_changed").count(), 0)

    def test_database_enforces_the_singleton_and_value_ranges(self):
        with tenant_context(self.school_a):
            NotificationSettings.objects.create()
            for kwargs in ({}, {"singleton": False}):  # a second row / a row that is not the singleton
                with self.assertRaises(IntegrityError), transaction.atomic():
                    NotificationSettings.objects.create(**kwargs)
            for bad in (
                {"fee_reminder_days_before": 31}, {"overdue_reminder_interval_days": 0},
                {"max_overdue_reminders": 11},
            ):  # bypasses model validators on purpose: the database itself must refuse
                with self.assertRaises(IntegrityError), transaction.atomic():
                    NotificationSettings.objects.bulk_create([NotificationSettings(singleton=None, **bad)])
            self.assertEqual(NotificationSettings.objects.count(), 1)

    def test_simultaneous_first_updates_make_one_row_and_lose_nothing(self):
        barrier = threading.Barrier(2)
        errors = []

        def worker(**values):
            try:
                with schema_context(self.SCHEMA_A):
                    barrier.wait(timeout=30)
                    NotificationSettings.update_singleton(user_id=None, **values)
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=worker, kwargs={"fee_reminders_enabled": True}),
            threading.Thread(target=worker, kwargs={"absence_alerts_enabled": True}),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertEqual(errors, [])
        with tenant_context(self.school_a):
            self.assertEqual(NotificationSettings.objects.count(), 1)
            row = NotificationSettings.objects.get()
            self.assertTrue(row.fee_reminders_enabled)
            self.assertTrue(row.absence_alerts_enabled)  # neither concurrent update overwrote the other


class PermissionBehaviourTests(AlertFoundationFixture):
    def test_new_permissions_are_registered_but_given_to_no_existing_role_definition(self):
        with tenant_context(self.school_a):
            perms = Permission.objects.filter(codename__in=NEW_PERMISSIONS)
            self.assertEqual({p.codename for p in perms}, NEW_PERMISSIONS)
            self.assertEqual({p.module for p in perms}, {"Alerts"})
            # The module name must not contain "notification": an existing test asserts the inbox needs none.
            self.assertFalse(Permission.objects.filter(module__icontains="notification").exists())
            for slug in ("staff", "instructor", "student", "parent"):
                granted = set(Role.objects.get(slug=slug).permissions.values_list("codename", flat=True))
                self.assertFalse(granted & NEW_PERMISSIONS, slug)

    def test_new_tenant_owner_role_is_created_with_them_existing_owners_are_not_changed(self):
        with tenant_context(self.school_a):
            owner_role = Role.objects.get(slug="owner")
            # A tenant provisioned after this change: the owner role is created with every registered permission.
            self.assertTrue(NEW_PERMISSIONS <= set(owner_role.permissions.values_list("codename", flat=True)))

            # Simulate a tenant that existed before the permissions were introduced.
            owner_role.permissions.remove(*Permission.objects.filter(codename__in=NEW_PERMISSIONS))
            before = {r.slug: (r.name, r.description, frozenset(r.permissions.values_list("codename", flat=True))) for r in Role.objects.all()}
            role_signals.seed_default_roles()  # what the next migration would do for that tenant
            after = {r.slug: (r.name, r.description, frozenset(r.permissions.values_list("codename", flat=True))) for r in Role.objects.all()}
            self.assertEqual(before, after)  # nothing backfilled, nothing changed
            self.assertFalse(NEW_PERMISSIONS & after["owner"][2])

        # Enforcement does not depend on the stored grant: the owner role bypasses permission checks.
        owner = self._as(self.owner)
        self.assertEqual(self._req(owner, "get", SETTINGS_URL).status_code, 200)
        self.assertEqual(self._req(owner, "patch", SETTINGS_URL, data={"fee_reminders_enabled": True}).status_code, 200)
        self.assertEqual(self._req(owner, "get", LOG_URL).status_code, 200)


class AlertLogApiTests(AlertFoundationFixture):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school_a):
            profile = Profile.objects.create(first_name="Secretname", last_name="Studentname")
            self.student = Student.objects.create(profile=profile, enrollment_id="ENR-ALF-1", status="active")
            self.other_student = Student.objects.create(
                profile=Profile.objects.create(first_name="Other", last_name="Child"), enrollment_id="ENR-ALF-2", status="active"
            )
        self.recipient = alerts.AlertRecipient(user_id=uuid.uuid4(), email="jane.doe@example.com")

    def _send(self, kind="absence", key=None, student=None, recipient=None, school=None):
        with tenant_context(school or self.school_a):
            student = student or self.student
            return alerts.dispatch_alert(
                kind=kind, dedupe_key=key or f"{kind}:{uuid.uuid4()}", recipient=recipient or self.recipient,
                student=student, title="Alert title", body="Alert body 12345.67",
            ).log

    def test_response_contains_only_the_approved_fields_and_leaks_nothing(self):
        log = self._send()
        resp = self._req(self._as(self.viewer), "get", LOG_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        row = resp.data["results"][0]
        self.assertEqual(set(row), {"id", "kind", "created_at", "delivery_status", "enrollment_id", "recipient"})
        self.assertEqual(row["id"], str(log.id))
        self.assertEqual(row["kind"], "absence")
        self.assertEqual(row["enrollment_id"], "ENR-ALF-1")
        self.assertEqual(row["recipient"], "j***@e***.com")
        raw = json.dumps(resp.data)
        for secret in ("jane.doe@example.com", "Secretname", "Studentname", str(self.recipient.user_id),
                       str(self.student.id), "12345.67", "Alert body"):
            self.assertNotIn(secret, raw)

    def test_delivery_status_comes_from_the_real_outbox_statuses(self):
        self.assertEqual(
            {s for s, _ in EmailOutboxEvent.Status.choices}, {"pending", "retrying", "sent", "failed"}
        )  # the only states that exist; nothing else is mapped
        with tenant_context(self.school_a):
            expected = {}
            for status in ("pending", "retrying", "sent", "failed"):
                event = EmailOutboxEvent.objects.create(to_email="x@example.com", subject="s", body="b", status=status)
                log = AlertLog.objects.create(
                    kind="absence", dedupe_key=f"status:{status}", recipient_user_id=uuid.uuid4(),
                    student_id=self.student.id, enrollment_id="ENR-ALF-1", outbox_event=event,
                )
                expected[str(log.id)] = status
            bare = AlertLog.objects.create(
                kind="absence", dedupe_key="status:none", recipient_user_id=uuid.uuid4(), student_id=self.student.id
            )
            expected[str(bare.id)] = "in_app_only"
        resp = self._req(self._as(self.viewer), "get", LOG_URL)
        self.assertEqual({str(r["id"]): r["delivery_status"] for r in resp.data["results"]}, expected)

    def test_filters_validation_ordering_and_pagination(self):
        a = self._send("absence", "k1")
        b = self._send("fee_overdue", "k2", student=self.other_student)
        c = self._send("absence", "k3")
        with tenant_context(self.school_a):
            AlertLog.objects.filter(pk=a.pk).update(created_at=datetime(2026, 1, 10, 12, tzinfo=dt_timezone.utc))
            AlertLog.objects.filter(pk=b.pk).update(created_at=datetime(2026, 2, 10, 12, tzinfo=dt_timezone.utc))
            AlertLog.objects.filter(pk=c.pk).update(created_at=datetime(2026, 3, 10, 12, tzinfo=dt_timezone.utc))
        viewer = self._as(self.viewer)
        listing = lambda **params: self._req(viewer, "get", LOG_URL + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else ""))  # noqa: E731

        self.assertEqual(self._ids(listing()), [str(c.id), str(b.id), str(a.id)])  # newest first
        self.assertEqual(self._ids(listing(kind="absence")), [str(c.id), str(a.id)])
        self.assertEqual(self._ids(listing(enrollment_id="ENR-ALF-2")), [str(b.id)])
        self.assertEqual(self._ids(listing(created_after="2026-02-10")), [str(c.id), str(b.id)])  # inclusive
        self.assertEqual(self._ids(listing(created_before="2026-02-10")), [str(b.id), str(a.id)])
        self.assertEqual(self._ids(listing(created_after="2026-02-01", created_before="2026-02-28")), [str(b.id)])
        for bad in ({"kind": "nonsense"}, {"created_after": "yesterday"}, {"created_before": "2026-13-45"}, {"created_after": "2026-1-1"}):
            self.assertEqual(listing(**bad).status_code, 400, bad)

        page = listing(page_size=2)
        self.assertEqual((page.data["count"], len(page.data["results"])), (3, 2))
        self.assertIsNotNone(page.data["next"])
        self.assertEqual(len(listing(page_size=1000).data["results"]), 3)  # capped at 100, here only 3 exist

    def test_query_count_does_not_grow_with_the_number_of_rows(self):
        viewer = self._as(self.viewer)
        for i in range(3):
            self._send(key=f"q:{i}")
        with CaptureQueriesContext(connection) as small:
            self._req(viewer, "get", LOG_URL)
        for i in range(3, 12):
            self._send(key=f"q:{i}")
        with CaptureQueriesContext(connection) as large:
            resp = self._req(viewer, "get", LOG_URL)
        self.assertEqual(len(resp.data["results"]), 12)
        self.assertEqual(len(small), len(large))

    def test_log_is_tenant_isolated(self):
        self._send(key="in-a")
        with tenant_context(self.school_b):
            profile = Profile.objects.create(first_name="B", last_name="Child")
            student_b = Student.objects.create(profile=profile, enrollment_id="ENR-B-1", status="active")
        self._send(key="in-b", student=student_b, school=self.school_b)
        viewer_b = self._user("alf_viewer_b", school=self.school_b, codenames=["view_notification_log"])

        resp_a = self._req(self._as(self.viewer), "get", LOG_URL)
        self.assertEqual([r["enrollment_id"] for r in resp_a.data["results"]], ["ENR-ALF-1"])
        resp_b = self._req(self._as(viewer_b), "get", LOG_URL, host=self.DOMAIN_B)
        self.assertEqual([r["enrollment_id"] for r in resp_b.data["results"]], ["ENR-B-1"])
        # A viewer of school A has no standing in school B.
        self.assertEqual(self._req(self._as(self.viewer), "get", LOG_URL, host=self.DOMAIN_B).status_code, 403)


class MaskingTests(SimpleTestCase):
    def test_mask_email_never_reveals_the_address(self):
        self.assertEqual(alerts.mask_email("jane.doe@example.com"), "j***@e***.com")
        self.assertEqual(alerts.mask_email("a@b.co.uk"), "a***@b***.uk")
        for value in (None, "", "no-at-sign", "@nolocal.com", "nodomain@"):
            self.assertEqual(alerts.mask_email(value), alerts.NO_EMAIL_HINT, value)
        masked = alerts.mask_email("jane.doe@example.com")
        self.assertNotIn("jane", masked)
        self.assertNotIn("example", masked)


class RecipientResolutionTests(AlertFoundationFixture):
    def setUp(self):
        super().setUp()
        connection.set_schema_to_public()
        self.child_user = User.objects.create_user(username="alf_child", email="alf_child@alertfound.test", password=PASSWORD)
        self.mum_user = User.objects.create_user(username="alf_mum", email="alf_mum@alertfound.test", password=PASSWORD)
        self.dad_user = User.objects.create_user(username="alf_dad", email="alf_dad@alertfound.test", password=PASSWORD, is_active=False)
        self.noemail_user = User.objects.create_user(username="alf_noemail", password=PASSWORD)  # email stays NULL
        self.other_user = User.objects.create_user(username="alf_otherparent", email="alf_otherparent@alertfound.test", password=PASSWORD)
        with tenant_context(self.school_a):
            self.student = Student.objects.create(
                profile=Profile.objects.create(user_id=self.child_user.id, first_name="Kid", last_name="One"),
                enrollment_id="ENR-RR-1", status="active",
            )
            self.sibling = Student.objects.create(
                profile=Profile.objects.create(first_name="Kid", last_name="Two"), enrollment_id="ENR-RR-2", status="active"
            )

            def parent(user, name, student):
                p = Parent.objects.create(profile=Profile.objects.create(user_id=user.id if user else None, first_name=name, last_name="P"))
                StudentParentRelation.objects.create(student=student, parent=p, relation_type="guardian")
                return p

            parent(self.mum_user, "Mum", self.student)
            parent(self.dad_user, "Dad", self.student)          # linked, but the account is inactive
            parent(None, "NoAccount", self.student)             # linked, no portal account
            parent(self.noemail_user, "NoEmail", self.student)  # linked, active, no email address
            parent(self.other_user, "Other", self.sibling)      # an active account, linked to a different child only

    def test_only_active_linked_accounts_of_this_student_are_eligible(self):
        with tenant_context(self.school_a):
            recipients = alerts.resolve_alert_recipients(self.student)
        by_id = {r.user_id: r.email for r in recipients}
        self.assertEqual(
            set(by_id),
            {self.child_user.id, self.mum_user.id, self.noemail_user.id},
        )
        self.assertEqual(recipients[0].user_id, self.child_user.id)  # the student's own account comes first
        self.assertEqual(by_id[self.mum_user.id], "alf_mum@alertfound.test")
        self.assertIsNone(by_id[self.noemail_user.id])
        for excluded in (self.dad_user.id, self.other_user.id):
            self.assertNotIn(excluded, by_id)

        with tenant_context(self.school_a):
            sibling_recipients = alerts.resolve_alert_recipients(self.sibling)
        self.assertEqual({r.user_id for r in sibling_recipients}, {self.other_user.id})  # no mention of the other family

    def test_a_user_linked_twice_appears_once(self):
        with tenant_context(self.school_a):
            second = Parent.objects.create(profile=Profile.objects.create(user_id=self.mum_user.id, first_name="Mum2", last_name="P"))
            StudentParentRelation.objects.create(student=self.student, parent=second, relation_type="mother")
            recipients = alerts.resolve_alert_recipients(self.student)
        self.assertEqual([r.user_id for r in recipients].count(self.mum_user.id), 1)


class DispatchAlertTests(AlertFoundationFixture):
    def setUp(self):
        super().setUp()
        connection.set_schema_to_public()
        self.person = User.objects.create_user(username="alf_person", email="alf_person@alertfound.test", password=PASSWORD)
        with tenant_context(self.school_a):
            self.student = Student.objects.create(
                profile=Profile.objects.create(first_name="Dispatch", last_name="Child"), enrollment_id="ENR-DS-1", status="active"
            )
        self.recipient = alerts.AlertRecipient(user_id=self.person.id, email=self.person.email)
        self.kwargs = dict(
            kind="absence", dedupe_key=f"absence:{uuid.uuid4()}", recipient=self.recipient, student=self.student,
            title="Absent today", body="Please check the portal.", link="/dashboard/parent-portal/attendance",
        )

    def _counts(self):
        with tenant_context(self.school_a):
            return (AlertLog.objects.count(), Notification.objects.count(), EmailOutboxEvent.objects.count())

    def _dispatch(self, **overrides):
        with tenant_context(self.school_a):
            return alerts.dispatch_alert(**{**self.kwargs, **overrides})

    def test_first_call_creates_log_inbox_and_outbox_consistently_second_call_is_a_duplicate(self):
        mail.outbox.clear()
        first = self._dispatch()
        self.assertTrue(first.created)
        self.assertEqual(self._counts(), (1, 1, 1))
        with tenant_context(self.school_a):
            log = AlertLog.objects.get()
            notification = Notification.objects.get()
            event = EmailOutboxEvent.objects.get()
            self.assertEqual(log.notification_id, notification.id)
            self.assertEqual(log.outbox_event_id, event.id)
            self.assertEqual(notification.recipient_user_id, self.person.id)
            self.assertEqual((notification.category, notification.link), ("alert", "/dashboard/parent-portal/attendance"))
            self.assertEqual((log.enrollment_id, log.recipient_hint, log.student_id), ("ENR-DS-1", "a***@a***.test", self.student.id))
            self.assertEqual(event.to_email, "alf_person@alertfound.test")
            self.assertEqual(event.status, "sent")  # tasks run eagerly under test; delivered once
            self.assertEqual(log.delivery_status, "sent")
        self.assertEqual(len(mail.outbox), 1)

        second = self._dispatch()
        self.assertFalse(second.created)
        self.assertEqual(second.log.id, first.log.id)
        self.assertEqual(self._counts(), (1, 1, 1))  # no second log, inbox row or outbox row
        self.assertEqual(len(mail.outbox), 1)  # and no second email

    def test_different_key_or_recipient_or_kind_is_a_separate_alert(self):
        self._dispatch()
        self.assertTrue(self._dispatch(dedupe_key="absence:another").created)
        self.assertTrue(self._dispatch(kind="fee_overdue").created)
        connection.set_schema_to_public()
        other = User.objects.create_user(username="alf_person2", email="alf_person2@alertfound.test", password=PASSWORD)
        self.assertTrue(self._dispatch(recipient=alerts.AlertRecipient(user_id=other.id, email=other.email)).created)
        self.assertEqual(self._counts(), (4, 4, 4))

    def test_recipient_without_an_email_gets_the_inbox_notification_only(self):
        result = self._dispatch(recipient=alerts.AlertRecipient(user_id=self.person.id, email=None))
        self.assertTrue(result.created)
        self.assertEqual(self._counts(), (1, 1, 0))
        with tenant_context(self.school_a):
            log = AlertLog.objects.get()
            self.assertIsNone(log.outbox_event_id)
            self.assertEqual((log.recipient_hint, log.delivery_status), ("in-app only", "in_app_only"))

    def test_a_duplicate_does_not_poison_a_surrounding_transaction(self):
        self._dispatch()
        with tenant_context(self.school_a):
            with transaction.atomic():
                dup = alerts.dispatch_alert(**self.kwargs)
                self.assertFalse(dup.created)
                self.assertEqual(AlertLog.objects.count(), 1)  # the outer transaction is still usable
                new = alerts.dispatch_alert(**{**self.kwargs, "dedupe_key": "absence:inside-outer"})
                self.assertTrue(new.created)
        self.assertEqual(self._counts(), (2, 2, 2))

    def test_a_failure_after_the_claim_rolls_everything_back_and_a_retry_succeeds(self):
        with mock.patch.object(alerts, "queue_email", side_effect=RuntimeError("outbox down")):
            with self.assertRaises(RuntimeError):
                self._dispatch()
        self.assertEqual(self._counts(), (0, 0, 0))  # no orphan log, inbox row or outbox row
        with mock.patch.object(alerts, "notify", side_effect=RuntimeError("inbox down")):
            with self.assertRaises(RuntimeError):
                self._dispatch()
        self.assertEqual(self._counts(), (0, 0, 0))
        self.assertTrue(self._dispatch().created)
        self.assertEqual(self._counts(), (1, 1, 1))

    def test_an_unrelated_integrity_error_is_not_mistaken_for_a_duplicate(self):
        with mock.patch.object(AlertLog.objects, "create", side_effect=IntegrityError("some other constraint")):
            with self.assertRaises(IntegrityError):
                self._dispatch()
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_invalid_requests_are_refused_without_writing(self):
        invalid = [
            {"kind": "bogus"}, {"dedupe_key": ""}, {"dedupe_key": "k" * 121}, {"title": ""}, {"title": "t" * 201},
            {"body": "b" * 501}, {"recipient": None}, {"recipient": alerts.AlertRecipient(user_id=None, email="a@b.com")},
            {"email_subject": "s" * 256},
        ]
        for overrides in invalid:
            with self.assertRaises(alerts.AlertError, msg=overrides):
                self._dispatch(**overrides)
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_the_public_schema_is_refused(self):
        connection.set_schema_to_public()
        with self.assertRaises(alerts.AlertError):
            alerts.dispatch_alert(**self.kwargs)

    def test_a_failed_email_stays_failed_and_is_not_regenerated(self):
        self._dispatch()
        with tenant_context(self.school_a):
            EmailOutboxEvent.objects.update(status="failed", error_type="permanent", last_error="bad recipient")
        again = self._dispatch()
        self.assertFalse(again.created)
        self.assertEqual(self._counts(), (1, 1, 1))  # no replacement alert, inbox row or outbox row
        with tenant_context(self.school_a):
            self.assertEqual(AlertLog.objects.get().delivery_status, "failed")

    def test_concurrent_workers_send_one_alert(self):
        barrier = threading.Barrier(4)
        outcomes, errors = [], []

        def worker():
            try:
                with schema_context(self.SCHEMA_A):
                    student = Student.objects.get(pk=self.student.pk)
                    barrier.wait(timeout=30)
                    outcomes.append(alerts.dispatch_alert(**{**self.kwargs, "student": student}).created)
            except Exception as exc:  # noqa: BLE001 - reported below
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=90)

        self.assertEqual(errors, [])
        self.assertEqual(sorted(outcomes), [False, False, False, True])  # exactly one winner
        self.assertEqual(self._counts(), (1, 1, 1))
