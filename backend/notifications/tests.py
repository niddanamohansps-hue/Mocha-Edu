import smtplib
import uuid as uuid_module
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.db import connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Role, UserRole
from staff.models import Instructor, StaffMember
from students.models import Student

from .models import Notification, EmailOutboxEvent
from .services import notify, notify_many, queue_email
from .tasks import _backoff_seconds, recover_stale_outbox_events, send_outbox_email


class NotificationFixtureMixin:
    """Mirrors students/fees/parent_portal tests.py exactly."""

    SCHEMA_NAME = "notif_test_school"
    DOMAIN = "notiftest.localhost"

    def _build_school(self, schema_name=None, domain=None, name="Notifications Test School"):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user_with_profile(self, username, role_slug, first_name="Test", last_name="User"):
        """
        Builds a User directly (never via a shared "_build_user + UserRole"
        helper followed by a manual Profile.create()) so the Profile is
        linked BEFORE the UserRole is created. profiles.signals.
        create_profile_for_role fires on UserRole post_save and
        auto-creates a Profile for any role NOT in its
        ["student", "instructor"] skip list - creating the UserRole before
        a real Profile exists (or creating a second Profile afterward)
        produces a duplicate Profile.MultipleObjectsReturned, exactly the
        mistake already found and fixed twice this session (fees/tests.py,
        students/tests.py).
        """
        user = User.objects.create_user(
            username=username, email=f"{username}@notiftest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            Profile.objects.create(user_id=user.id, first_name=first_name, last_name=last_name)
            role, _ = Role.objects.get_or_create(
                slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=role)
        return user

    def _client_as(self, user, password="Pass1234!"):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"username": user.username, "password": password}, HTTP_HOST=self.DOMAIN
        )
        assert resp.status_code == 200, resp.data
        return client

    def setUp(self):
        self.school = self._build_school()

        self.owner_user = self._build_user_with_profile("notif_owner", "owner", "Own", "Er")
        self.staff_user = self._build_user_with_profile("notif_staff", "staff", "Sta", "Ff")

        # Instructor - "instructor" IS in profiles.signals' skip list, so a
        # student_record/staff_record-style manual Profile is safe here too,
        # but we use the same safe helper for consistency.
        self.instructor_user = self._build_user_with_profile("notif_instructor", "instructor", "Ins", "Tructor")
        with tenant_context(self.school):
            instr_profile = Profile.objects.filter(user_id=self.instructor_user.id).first()
            instr_staff = StaffMember.objects.create(
                profile=instr_profile, employee_id="EMP-NOTIF-1", designation="Teacher"
            )
            self.instructor = Instructor.objects.create(staff_member=instr_staff, specialization="Math")

        self.student_user = self._build_user_with_profile("notif_student", "student", "Stu", "Dent")
        with tenant_context(self.school):
            student_profile = Profile.objects.filter(user_id=self.student_user.id).first()
            self.student = Student.objects.create(
                profile=student_profile, enrollment_id="ENR-NOTIF-1", status="active"
            )

        self.parent_user = self._build_user_with_profile("notif_parent", "parent", "Par", "Ent")
        with tenant_context(self.school):
            parent_profile = Profile.objects.filter(user_id=self.parent_user.id).first()
            self.parent = Parent.objects.create(profile=parent_profile, occupation="Engineer")
            StudentParentRelation.objects.create(
                student=self.student, parent=self.parent, relation_type="mother", is_primary_contact=True
            )

        # A second user with no notifications, used as "User B" for IDOR tests.
        self.other_user = self._build_user_with_profile("notif_other", "staff", "Oth", "Er")

        # A second, separate tenant to prove cross-tenant isolation.
        self.school2 = self._build_school(
            schema_name="notif_test_school2", domain="notiftest2.localhost", name="Notifications Test School 2"
        )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        self.school2.delete(force_drop=True)


class NotificationModelTests(NotificationFixtureMixin, TransactionTestCase):
    def test_notification_created(self):
        with tenant_context(self.school):
            n = Notification.objects.create(recipient_user_id=self.staff_user.id, title="Hello")
            self.assertIsNotNone(n.id)

    def test_uuid_primary_key(self):
        with tenant_context(self.school):
            n = Notification.objects.create(recipient_user_id=self.staff_user.id, title="Hello")
            self.assertIsInstance(n.id, uuid_module.UUID)

    def test_unread_by_default(self):
        with tenant_context(self.school):
            n = Notification.objects.create(recipient_user_id=self.staff_user.id, title="Hello")
            self.assertFalse(n.is_read)

    def test_read_at_nullable(self):
        with tenant_context(self.school):
            n = Notification.objects.create(recipient_user_id=self.staff_user.id, title="Hello")
            self.assertIsNone(n.read_at)

    def test_index_exists(self):
        with tenant_context(self.school):
            index_names = {idx.name for idx in Notification._meta.indexes}
            self.assertIn("notif_recipient_unread_idx", index_names)

    def test_duplicates_allowed(self):
        with tenant_context(self.school):
            Notification.objects.create(recipient_user_id=self.staff_user.id, title="Same")
            Notification.objects.create(recipient_user_id=self.staff_user.id, title="Same")
            self.assertEqual(
                Notification.objects.filter(recipient_user_id=self.staff_user.id, title="Same").count(), 2
            )

    def test_no_table_in_public_schema(self):
        connection.set_schema_to_public()
        self.assertNotIn("notifications_notification", connection.introspection.table_names())


class NotificationServiceTests(NotificationFixtureMixin, TransactionTestCase):
    def test_notify_creates_one_notification(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="Fee due", body="Rs 500 due", category="fee", link="/dashboard/fees")
            self.assertEqual(n.title, "Fee due")
            self.assertEqual(n.category, "fee")
            self.assertEqual(n.link, "/dashboard/fees")

    def test_notify_requires_title(self):
        with tenant_context(self.school):
            with self.assertRaises(ValueError):
                notify(recipient_user_id=self.staff_user.id, title="")

    def test_notify_requires_recipient(self):
        with tenant_context(self.school):
            with self.assertRaises(ValueError):
                notify(recipient_user_id=None, title="Hello")

    def test_notify_optional_body_category_link(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="System notice")
            self.assertEqual(n.body, "")
            self.assertEqual(n.category, "")
            self.assertEqual(n.link, "")

    def test_notify_many_creates_one_per_recipient(self):
        with tenant_context(self.school):
            created = notify_many(
                recipient_user_ids=[self.staff_user.id, self.student_user.id, self.parent_user.id],
                title="Broadcast",
            )
            self.assertEqual(len(created), 3)
            self.assertEqual(Notification.objects.filter(title="Broadcast").count(), 3)

    def test_notify_many_uses_bulk_create_no_duplicate_restriction(self):
        with tenant_context(self.school):
            created = notify_many(
                recipient_user_ids=[self.staff_user.id, self.staff_user.id], title="Twice"
            )
            self.assertEqual(len(created), 2)
            self.assertEqual(Notification.objects.filter(recipient_user_id=self.staff_user.id, title="Twice").count(), 2)

    def test_notify_many_requires_recipients(self):
        with tenant_context(self.school):
            with self.assertRaises(ValueError):
                notify_many(recipient_user_ids=[], title="Hello")

    def test_notify_many_returns_saved_instances_with_pks(self):
        with tenant_context(self.school):
            created = notify_many(recipient_user_ids=[self.staff_user.id], title="Has PK")
            self.assertIsNotNone(created[0].id)


class NotificationAPITests(NotificationFixtureMixin, TransactionTestCase):
    def test_list_own_notifications(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="Mine")
            notify(recipient_user_id=self.other_user.id, title="Not mine")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        titles = [n["title"] for n in resp.data["results"]]
        self.assertIn("Mine", titles)
        self.assertNotIn("Not mine", titles)

    def test_newest_first(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="First")
            notify(recipient_user_id=self.staff_user.id, title="Second")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.data["results"][0]["title"], "Second")

    def test_pagination_present(self):
        with tenant_context(self.school):
            for i in range(25):
                notify(recipient_user_id=self.staff_user.id, title=f"N{i}")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("count", resp.data)
        self.assertIn("next", resp.data)
        self.assertEqual(resp.data["count"], 25)
        self.assertEqual(len(resp.data["results"]), 20)  # page_size

    def test_unread_count(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="A")
            notify(recipient_user_id=self.staff_user.id, title="B")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/unread-count/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["unread_count"], 2)

    def test_mark_one_read(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        resp = client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["is_read"])

    def test_mark_one_read_sets_read_at(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            n.refresh_from_db()
            self.assertIsNotNone(n.read_at)

    def test_mark_all_read(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="A")
            notify(recipient_user_id=self.staff_user.id, title="B")
            notify(recipient_user_id=self.staff_user.id, title="C")
        client = self._client_as(self.staff_user)
        resp = client.post("/api/notifications/mark-all-read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["updated_count"], 3)
        with tenant_context(self.school):
            self.assertEqual(
                Notification.objects.filter(recipient_user_id=self.staff_user.id, is_read=False).count(), 0
            )

    def test_already_read_mark_read_is_idempotent(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        first = client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        second = client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["is_read"])

    def test_mark_all_read_when_none_unread(self):
        client = self._client_as(self.staff_user)
        resp = client.post("/api/notifications/mark-all-read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["updated_count"], 0)

    def test_nonexistent_notification_returns_404(self):
        client = self._client_as(self.staff_user)
        resp = client.post(f"/api/notifications/{uuid_module.uuid4()}/read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)

    def test_client_cannot_create_notification_via_api(self):
        client = self._client_as(self.staff_user)
        # No POST /api/notifications/ (create) endpoint exists at all.
        resp = client.post("/api/notifications/", {"title": "Injected", "recipient_user_id": str(self.other_user.id)}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 405)


class NotificationSecurityTests(NotificationFixtureMixin, TransactionTestCase):
    def test_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertIn(resp.status_code, (401, 403))

    def test_user_a_lists_only_user_a_notifications(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="A's notification")
            notify(recipient_user_id=self.other_user.id, title="B's notification")
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        titles = [n["title"] for n in resp.data["results"]]
        self.assertEqual(titles, ["A's notification"])

    def test_user_b_lists_only_user_b_notifications(self):
        with tenant_context(self.school):
            notify(recipient_user_id=self.staff_user.id, title="A's notification")
            notify(recipient_user_id=self.other_user.id, title="B's notification")
        client = self._client_as(self.other_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        titles = [n["title"] for n in resp.data["results"]]
        self.assertEqual(titles, ["B's notification"])

    def test_user_a_cannot_mark_user_b_notification_read(self):
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.other_user.id, title="B's notification")
        client = self._client_as(self.staff_user)
        resp = client.post(f"/api/notifications/{n.id}/read/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)
        with tenant_context(self.school):
            n.refresh_from_db()
            self.assertFalse(n.is_read)

    def test_mark_all_read_does_not_affect_other_users(self):
        with tenant_context(self.school):
            b_notification = notify(recipient_user_id=self.other_user.id, title="B's")
            notify(recipient_user_id=self.staff_user.id, title="A's")
        client = self._client_as(self.staff_user)
        client.post("/api/notifications/mark-all-read/", {}, HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            b_notification.refresh_from_db()
            self.assertFalse(b_notification.is_read)

    def test_cross_tenant_notification_id_not_accessible(self):
        with tenant_context(self.school2):
            cross_tenant_notification = Notification.objects.create(
                recipient_user_id=self.staff_user.id, title="Other tenant"
            )
        client = self._client_as(self.staff_user)
        resp = client.post(
            f"/api/notifications/{cross_tenant_notification.id}/read/", {}, HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 404)

    def test_client_cannot_modify_recipient_user_id(self):
        """The serializer never accepts recipient_user_id as input, and
        there is no write endpoint besides the read-marking ones, which
        never touch recipient_user_id."""
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        client.post(
            f"/api/notifications/{n.id}/read/",
            {"recipient_user_id": str(self.other_user.id)},
            HTTP_HOST=self.DOMAIN,
        )
        with tenant_context(self.school):
            n.refresh_from_db()
            self.assertEqual(n.recipient_user_id, self.staff_user.id)

    def test_client_cannot_modify_is_read_via_update_api(self):
        """No PATCH/PUT endpoint exists at all for Notification."""
        with tenant_context(self.school):
            n = notify(recipient_user_id=self.staff_user.id, title="A")
        client = self._client_as(self.staff_user)
        resp = client.patch(f"/api/notifications/{n.id}/", {"is_read": True}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)

    def test_owner_can_access_own_inbox(self):
        client = self._client_as(self.owner_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_staff_can_access_own_inbox(self):
        client = self._client_as(self.staff_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_instructor_can_access_own_inbox(self):
        client = self._client_as(self.instructor_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_student_can_access_own_inbox(self):
        client = self._client_as(self.student_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_parent_can_access_own_inbox(self):
        client = self._client_as(self.parent_user)
        resp = client.get("/api/notifications/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_no_permission_required_for_any_role(self):
        """Confirms zero notification permissions exist and none are
        needed - every role above succeeded with only IsAuthenticated."""
        with tenant_context(self.school):
            from roles.models import Permission

            notif_permissions = Permission.objects.filter(module__icontains="notification")
            self.assertEqual(notif_permissions.count(), 0)


class EmailOutboxTest(TransactionTestCase):
    """
    Focused tests for the transactional email outbox itself
    (EmailOutboxEvent + queue_email + tasks.send_outbox_email), as opposed
    to accounts.tests.PasswordResetFlowTest, which already exercises the
    full integration (a real request ending in a delivered email) end to
    end. CELERY_TASK_ALWAYS_EAGER=True during tests (see config/settings.py)
    means .delay() runs the task synchronously in-process - no real worker
    or Redis connection is exercised by these tests.
    """

    SCHEMA_NAME = "outbox_test_school"
    DOMAIN = "outboxtest.localhost"

    OTHER_SCHEMA_NAME = "outbox_other_school"
    OTHER_DOMAIN = "outboxother.localhost"

    def setUp(self):
        connection.set_schema_to_public()
        mail.outbox = []
        self.school = Organization.objects.create(
            schema_name=self.SCHEMA_NAME, name="Outbox Test School"
        )
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)

        self.other_school = Organization.objects.create(
            schema_name=self.OTHER_SCHEMA_NAME, name="Outbox Other School"
        )
        Domain.objects.create(
            domain=self.OTHER_DOMAIN, tenant=self.other_school, is_primary=True
        )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        self.other_school.delete(force_drop=True)

    def test_queue_email_defers_dispatch_until_transaction_commits(self):
        """
        The core transactional-outbox guarantee: inside a still-open
        transaction.atomic() block, the event exists but has NOT been
        dispatched yet (still PENDING, no email sent). Only once that
        block exits (commits) does on_commit() fire the Celery task -
        which, in eager test mode, runs synchronously at that point.
        """
        with tenant_context(self.school):
            with transaction.atomic():
                event = queue_email(
                    to_email="someone@example.com", subject="Test", body="Body"
                )
                event.refresh_from_db()
                self.assertEqual(event.status, EmailOutboxEvent.Status.PENDING)
                self.assertEqual(len(mail.outbox), 0)

            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.SENT)
            self.assertIsNotNone(event.sent_at)
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].to, ["someone@example.com"])

    def test_outbox_event_not_dispatched_if_transaction_rolls_back(self):
        """
        If the surrounding transaction rolls back, the EmailOutboxEvent
        row itself must never have been committed either - there is
        nothing left to send, and nothing for a worker to ever pick up.
        """
        with tenant_context(self.school):
            try:
                with transaction.atomic():
                    queue_email(to_email="x@example.com", subject="Test", body="Body")
                    raise RuntimeError("simulated failure after queuing")
            except RuntimeError:
                pass

            self.assertEqual(EmailOutboxEvent.objects.count(), 0)
            self.assertEqual(len(mail.outbox), 0)

    def test_send_outbox_email_marks_failed_after_max_attempts(self):
        """
        A persistently-failing send (e.g. SMTP down) must not retry
        forever - once attempts reaches max_attempts, the task stops
        retrying and the event is marked FAILED for operator visibility
        (see EmailOutboxEventAdmin), rather than disappearing silently.

        self.retry() raises celery.exceptions.Retry straight out of
        .apply() in eager mode - a real worker consuming from Redis would
        reschedule the task automatically on that signal; a bare .apply()
        call has no broker to do that, so the retry loop is simulated
        explicitly here (the standard way to unit-test Celery retry logic
        without a running broker).
        """
        from celery.exceptions import Retry

        with tenant_context(self.school):
            event = EmailOutboxEvent.objects.create(
                to_email="fails@example.com", subject="Test", body="Body", max_attempts=2
            )

        with mock.patch(
            "notifications.tasks.send_mail", side_effect=Exception("smtp down")
        ):
            for _ in range(event.max_attempts):
                try:
                    send_outbox_email.apply(args=[self.SCHEMA_NAME, str(event.id)])
                except Retry:
                    continue

        with tenant_context(self.school):
            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.FAILED)
            self.assertEqual(event.attempts, 2)
            self.assertIn("smtp down", event.last_error)
        self.assertEqual(len(mail.outbox), 0)

    def test_send_outbox_email_is_idempotent_once_sent(self):
        """Re-running the task against an already-SENT event (e.g. a
        duplicate/late dispatch) must not send a second email."""
        with tenant_context(self.school):
            event = queue_email(to_email="once@example.com", subject="Test", body="Body")
        self.assertEqual(len(mail.outbox), 1)

        send_outbox_email.apply(args=[self.SCHEMA_NAME, str(event.id)])
        self.assertEqual(len(mail.outbox), 1, "Event was sent a second time")

    def test_send_outbox_email_is_tenant_scoped(self):
        """
        An event created in one tenant schema must not be reachable by
        the task when (incorrectly) pointed at a different tenant's
        schema_name - the task must enter the correct schema, never
        search across schemas or fall back to another one.
        """
        with tenant_context(self.school):
            event = EmailOutboxEvent.objects.create(
                to_email="isolated@example.com", subject="Test", body="Body"
            )

        # Deliberately pass the OTHER school's schema name - the event
        # does not exist there, so the task must log and return quietly
        # rather than erroring or finding a same-ID row in another tenant.
        send_outbox_email.apply(args=[self.OTHER_SCHEMA_NAME, str(event.id)])
        self.assertEqual(len(mail.outbox), 0)

        with tenant_context(self.school):
            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.PENDING)

    def test_queue_email_normal_dispatch_creates_exactly_one_pending_then_sent_event(self):
        """
        Baseline (TEST 1): a normal queue_email() call creates exactly one
        EmailOutboxEvent, PENDING at creation, and normal dispatch still
        transitions it to SENT once the transaction commits - the
        centralized post-commit error handling must not change this
        happy path at all.
        """
        with tenant_context(self.school):
            with transaction.atomic():
                event = queue_email(to_email="normal@example.com", subject="Test", body="Body")
                self.assertEqual(EmailOutboxEvent.objects.count(), 1)
                event.refresh_from_db()
                self.assertEqual(event.status, EmailOutboxEvent.Status.PENDING)

            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_queue_email_post_commit_celery_dispatch_failure_does_not_escape(self):
        """
        TEST 2 (the core fix): simulate a Celery-side dispatch failure (as
        celery.exceptions.Retry - a CeleryError subclass - genuinely does
        under CELERY_TASK_ALWAYS_EAGER, which is exactly what surfaced
        this bug via the examination-publication feature) from the
        on_commit callback. The transaction must still commit cleanly, no
        exception may escape queue_email()/the caller, and the event must
        remain exactly as created: PENDING, never SENT or FAILED - the
        task body that would transition it never ran at all.
        """
        from celery.exceptions import CeleryError

        with tenant_context(self.school):
            with mock.patch(
                "notifications.tasks.send_outbox_email.delay",
                side_effect=CeleryError("broker unavailable"),
            ):
                with transaction.atomic():
                    event = queue_email(to_email="dispatchfail@example.com", subject="Test", body="Body")
                # No exception escaped the transaction.atomic() block above.

            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.PENDING)
            self.assertEqual(event.attempts, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_queue_email_post_commit_broker_connection_failure_does_not_escape(self):
        """
        Same as above but for a transport/broker-level failure (e.g. Redis
        briefly unreachable at the moment of dispatch) rather than a
        Celery task-level one - kombu.exceptions.KombuError is the
        realistic exception type for that case, distinct from CeleryError.
        """
        from kombu.exceptions import KombuError

        with tenant_context(self.school):
            with mock.patch(
                "notifications.tasks.send_outbox_email.delay",
                side_effect=KombuError("connection refused"),
            ):
                with transaction.atomic():
                    event = queue_email(to_email="brokerdown@example.com", subject="Test", body="Body")

            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.PENDING)
        self.assertEqual(len(mail.outbox), 0)

    def test_queue_email_outbox_creation_failure_still_propagates(self):
        """
        TEST 3: a genuine database error creating the EmailOutboxEvent row
        itself (as opposed to a dispatch failure afterward) must still
        propagate normally - proving the centralized handling added for
        TEST 2 does not broadly swallow exceptions. Nothing is created.
        """
        from django.db import IntegrityError

        with tenant_context(self.school):
            with mock.patch(
                "notifications.models.EmailOutboxEvent.objects.create",
                side_effect=IntegrityError("simulated db failure"),
            ):
                with self.assertRaises(IntegrityError):
                    queue_email(to_email="dbfail@example.com", subject="Test", body="Body")

            self.assertEqual(EmailOutboxEvent.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_dispatch_failed_event_is_recoverable_by_stale_recovery(self):
        """
        TEST 4: a PENDING event whose Celery dispatch failed post-commit
        must still be eligible for the existing recover_stale_outbox_events
        safety net once it's old enough - proving the centralized handling
        doesn't create a dead-end event that nothing will ever retry.
        """
        from celery.exceptions import CeleryError

        with tenant_context(self.school):
            with mock.patch(
                "notifications.tasks.send_outbox_email.delay",
                side_effect=CeleryError("broker unavailable"),
            ):
                event = queue_email(to_email="recoverme@example.com", subject="Test", body="Body")

            EmailOutboxEvent.objects.filter(id=event.id).update(
                updated_at=timezone.now() - timedelta(minutes=20)
            )

        recovered = recover_stale_outbox_events.apply().get()

        self.assertEqual(recovered, 1)
        self.assertEqual(len(mail.outbox), 1)
        with tenant_context(self.school):
            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.SENT)

    def test_temporary_failure_transitions_to_retrying_with_backoff(self):
        """
        A transient error (connection refused, timeout, ...) must not go
        straight to FAILED - it moves to RETRYING with next_attempt_at set
        in the future, so an operator (or recover_stale_outbox_events)
        can see a retry is scheduled rather than the event looking stuck.
        """
        from celery.exceptions import Retry

        with tenant_context(self.school):
            event = EmailOutboxEvent.objects.create(
                to_email="flaky@example.com", subject="Test", body="Body", max_attempts=3
            )

        with mock.patch(
            "notifications.tasks.send_mail", side_effect=Exception("connection refused")
        ):
            try:
                send_outbox_email.apply(args=[self.SCHEMA_NAME, str(event.id)])
            except Retry:
                pass

        with tenant_context(self.school):
            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.RETRYING)
            self.assertEqual(event.attempts, 1)
            self.assertEqual(event.error_type, EmailOutboxEvent.ErrorType.TEMPORARY)
            self.assertIn("connection refused", event.last_error)
            self.assertIsNotNone(event.next_attempt_at)
            self.assertGreater(event.next_attempt_at, timezone.now())
        self.assertEqual(len(mail.outbox), 0)

    def test_permanent_failure_skips_retry_and_fails_immediately(self):
        """
        A permanent error (bad recipient address) must go straight to
        FAILED on the first attempt - retrying it would just waste
        max_attempts on an error that can never succeed."""
        with tenant_context(self.school):
            event = EmailOutboxEvent.objects.create(
                to_email="bad@example.com", subject="Test", body="Body", max_attempts=3
            )

        with mock.patch(
            "notifications.tasks.send_mail",
            side_effect=smtplib.SMTPRecipientsRefused({"bad@example.com": (550, b"User unknown")}),
        ):
            send_outbox_email.apply(args=[self.SCHEMA_NAME, str(event.id)])

        with tenant_context(self.school):
            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.FAILED)
            self.assertEqual(event.attempts, 1)
            self.assertEqual(event.error_type, EmailOutboxEvent.ErrorType.PERMANENT)
            self.assertIsNone(event.next_attempt_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_exponential_backoff_increases_each_retry(self):
        self.assertEqual(_backoff_seconds(1), 60)
        self.assertEqual(_backoff_seconds(2), 120)
        self.assertEqual(_backoff_seconds(3), 240)
        self.assertEqual(_backoff_seconds(4), 480)
        self.assertEqual(_backoff_seconds(10), 900)  # capped at MAX_RETRY_DELAY_SECONDS

    def test_send_outbox_email_is_idempotent_once_failed(self):
        """Re-running the task against an already-FAILED event (e.g. a
        duplicate/late dispatch after acks_late redelivery) must not
        re-send or re-count an attempt."""
        with tenant_context(self.school):
            event = EmailOutboxEvent.objects.create(
                to_email="dead@example.com",
                subject="Test",
                body="Body",
                status=EmailOutboxEvent.Status.FAILED,
                attempts=3,
                max_attempts=3,
            )

        send_outbox_email.apply(args=[self.SCHEMA_NAME, str(event.id)])

        self.assertEqual(len(mail.outbox), 0)
        with tenant_context(self.school):
            event.refresh_from_db()
            self.assertEqual(event.attempts, 3)
            self.assertEqual(event.status, EmailOutboxEvent.Status.FAILED)

    def test_task_is_configured_for_safe_redelivery(self):
        """acks_late + reject_on_worker_lost: if a worker dies mid-send,
        the broker redelivers this task to another worker instead of
        silently losing it."""
        self.assertTrue(send_outbox_email.acks_late)
        self.assertTrue(send_outbox_email.reject_on_worker_lost)

    def test_recover_stale_outbox_events_requeues_old_pending(self):
        """An event that has sat in PENDING/RETRYING with no progress
        past the stale threshold (queued but never picked up by any
        worker) gets re-dispatched."""
        with tenant_context(self.school):
            event = EmailOutboxEvent.objects.create(
                to_email="stale@example.com", subject="Test", body="Body"
            )
            EmailOutboxEvent.objects.filter(id=event.id).update(
                updated_at=timezone.now() - timedelta(minutes=20)
            )

        recovered = recover_stale_outbox_events.apply().get()

        self.assertEqual(recovered, 1)
        self.assertEqual(len(mail.outbox), 1)
        with tenant_context(self.school):
            event.refresh_from_db()
            self.assertEqual(event.status, EmailOutboxEvent.Status.SENT)

    def test_recover_stale_outbox_events_ignores_recent_events(self):
        """An event still well within the stale threshold must be left
        alone - it may simply be mid-flight or scheduled for a near-
        future retry, not stuck."""
        with tenant_context(self.school):
            EmailOutboxEvent.objects.create(
                to_email="fresh@example.com", subject="Test", body="Body"
            )

        recovered = recover_stale_outbox_events.apply().get()

        self.assertEqual(recovered, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_recover_stale_outbox_events_ignores_terminal_events(self):
        """A SENT or FAILED event is terminal - it must never be
        re-dispatched, no matter how old updated_at is."""
        with tenant_context(self.school):
            sent_event = queue_email(to_email="done@example.com", subject="Test", body="Body")
            EmailOutboxEvent.objects.filter(id=sent_event.id).update(
                updated_at=timezone.now() - timedelta(minutes=20)
            )
        mail.outbox = []  # clear the send queue_email() itself triggered

        recovered = recover_stale_outbox_events.apply().get()

        self.assertEqual(recovered, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_recover_stale_outbox_events_is_tenant_scoped(self):
        """A stale event must be recovered independently per tenant -
        one tenant's backlog must not be skipped because of another's,
        and each must be re-dispatched into its own schema."""
        with tenant_context(self.school):
            event_a = EmailOutboxEvent.objects.create(
                to_email="a@example.com", subject="Test", body="Body"
            )
            EmailOutboxEvent.objects.filter(id=event_a.id).update(
                updated_at=timezone.now() - timedelta(minutes=20)
            )
        with tenant_context(self.other_school):
            event_b = EmailOutboxEvent.objects.create(
                to_email="b@example.com", subject="Test", body="Body"
            )
            EmailOutboxEvent.objects.filter(id=event_b.id).update(
                updated_at=timezone.now() - timedelta(minutes=20)
            )

        recovered = recover_stale_outbox_events.apply().get()

        self.assertEqual(recovered, 2)
        with tenant_context(self.school):
            event_a.refresh_from_db()
            self.assertEqual(event_a.status, EmailOutboxEvent.Status.SENT)
        with tenant_context(self.other_school):
            event_b.refresh_from_db()
            self.assertEqual(event_b.status, EmailOutboxEvent.Status.SENT)
