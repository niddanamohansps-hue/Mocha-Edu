import datetime
import uuid
from types import SimpleNamespace
from unittest import mock

import requests
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django_tenants.utils import tenant_context

from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from students.models import Student

from . import alerts, whatsapp
from .models import AlertLog, WhatsAppOutboxEvent
from .tasks import send_whatsapp_event


class PhoneTests(SimpleTestCase):
    @override_settings(WHATSAPP_DEFAULT_COUNTRY_CODE="91")
    def test_numbers_are_normalised_to_the_form_whatsapp_expects(self):
        n = whatsapp.normalize_phone
        self.assertEqual(n("9876543210"), "919876543210")
        self.assertEqual(n("09876543210"), "919876543210")
        self.assertEqual(n("+91 98765-43210"), "919876543210")
        self.assertEqual(n("91 9876543210"), "919876543210")
        self.assertEqual(n("+977 9812345678"), "9779812345678")  # an explicit country code is kept
        for unusable in ("", None, "abc", "12345", "1" * 20):
            self.assertIsNone(n(unusable), unusable)

    def test_masking_never_shows_the_whole_number(self):
        masked = whatsapp.mask_phone("919876543210")
        self.assertEqual(masked, "+91******3210")
        self.assertNotIn("98765", masked)

    @override_settings(WHATSAPP_PROVIDER="meta", WHATSAPP_PHONE_NUMBER_ID="123", WHATSAPP_ACCESS_TOKEN="tok")
    def test_the_meta_request_carries_a_clean_template_payload(self):
        with mock.patch("notifications.whatsapp.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"messages": [{"id": "wamid.X"}]}
            message_id = whatsapp.send_template("919876543210", "absence_alert", "en", ["Asha\nRao", "2027-01-05"])
        self.assertEqual(message_id, "wamid.X")
        args, kwargs = post.call_args
        self.assertIn("/123/messages", args[0])
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer tok"})
        body = kwargs["json"]
        self.assertEqual((body["to"], body["type"], body["template"]["name"]), ("919876543210", "template", "absence_alert"))
        texts = [p["text"] for p in body["template"]["components"][0]["parameters"]]
        self.assertEqual(texts, ["Asha Rao", "2027-01-05"])  # a new line is not allowed inside a parameter

    @override_settings(WHATSAPP_PROVIDER="meta", WHATSAPP_PHONE_NUMBER_ID="123", WHATSAPP_ACCESS_TOKEN="tok")
    def test_provider_errors_are_split_into_retryable_and_permanent(self):
        def attempt(status):
            with mock.patch("notifications.whatsapp.requests.post") as post:
                post.return_value.status_code = status
                post.return_value.json.return_value = {"error": {"message": "nope"}}
                with self.assertRaises(whatsapp.WhatsAppError) as caught:
                    whatsapp.send_template("919876543210", "t", "en", [])
            return caught.exception.permanent

        self.assertTrue(attempt(400))
        self.assertTrue(attempt(401))
        self.assertFalse(attempt(429))
        self.assertFalse(attempt(503))
        with mock.patch("notifications.whatsapp.requests.post", side_effect=requests.ConnectionError("down")):
            with self.assertRaises(whatsapp.WhatsAppError) as caught:
                whatsapp.send_template("919876543210", "t", "en", [])
        self.assertFalse(caught.exception.permanent)

    @override_settings(WHATSAPP_PROVIDER="meta", WHATSAPP_PHONE_NUMBER_ID="", WHATSAPP_ACCESS_TOKEN="")
    def test_meta_without_credentials_fails_permanently_and_never_calls_out(self):
        with mock.patch("notifications.whatsapp.requests.post") as post:
            with self.assertRaises(whatsapp.WhatsAppError) as caught:
                whatsapp.send_template("919876543210", "t", "en", [])
        self.assertTrue(caught.exception.permanent)
        post.assert_not_called()


class WhatsAppFlowTests(TransactionTestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8]
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=f"wa_{suffix}", name="WhatsApp Test School")
        Domain.objects.create(domain=f"wa-{suffix}.localhost", tenant=self.school, is_primary=True)
        with tenant_context(self.school):
            self.student = Student.objects.create(
                profile=Profile.objects.create(first_name="Asha", last_name="Rao"), enrollment_id="ENR-WA-1", status="active"
            )
            self.opted = self._parent("Mum", "98765 43210", opt_in=True)
            self.silent = self._parent("Dad", "9123456789", opt_in=False)
            self.nophone = self._parent("Gran", "", opt_in=True)

    def _parent(self, name, phone, opt_in):
        parent = Parent.objects.create(
            profile=Profile.objects.create(first_name=name, last_name="P", phone=phone), whatsapp_opt_in=opt_in
        )
        StudentParentRelation.objects.create(student=self.student, parent=parent, relation_type="guardian")
        return parent

    def _dispatch(self, key="absence:x", recipient=None):
        recipient = recipient or alerts.resolve_whatsapp_recipients(self.student)[0]
        return alerts.dispatch_whatsapp_alert(
            kind=AlertLog.Kind.ABSENCE, dedupe_key=key, recipient=recipient, student=self.student,
            template="absence_alert", params=["Asha Rao", "5 Jan"],
        )

    def test_nothing_is_queued_while_whatsapp_is_not_enabled(self):
        with tenant_context(self.school):
            self.assertEqual(alerts.resolve_whatsapp_recipients(self.student), [])  # the default provider is disabled
            with override_settings(WHATSAPP_PROVIDER="disabled"):
                self.assertEqual(alerts.resolve_whatsapp_recipients(self.student), [])

    @override_settings(WHATSAPP_PROVIDER="console")
    def test_only_opted_in_parents_with_a_usable_number_are_messaged(self):
        with tenant_context(self.school):
            recipients = alerts.resolve_whatsapp_recipients(self.student)
            self.assertEqual([(r.parent_id, r.phone) for r in recipients], [(self.opted.id, "919876543210")])

    def test_opting_in_is_timestamped_and_opting_out_clears_it(self):
        with tenant_context(self.school):
            self.assertIsNotNone(self.opted.whatsapp_opt_in_at)
            self.assertIsNone(self.silent.whatsapp_opt_in_at)
            self.opted.whatsapp_opt_in = False
            self.opted.save()
            self.opted.refresh_from_db()
            self.assertIsNone(self.opted.whatsapp_opt_in_at)

    @override_settings(WHATSAPP_PROVIDER="console")
    def test_an_alert_is_delivered_once_and_logged_with_a_masked_number(self):
        with tenant_context(self.school):
            first = self._dispatch()
            again = self._dispatch()
            self.assertTrue(first.created)
            self.assertFalse(again.created)
            self.assertEqual(WhatsAppOutboxEvent.objects.count(), 1)

            log = AlertLog.objects.get()
            self.assertEqual(log.recipient_user_id, self.opted.id)
            self.assertEqual(log.recipient_hint, "+91******3210")
            # Celery runs eagerly in tests, so the queued message has already been "sent" by the console provider.
            event = WhatsAppOutboxEvent.objects.get()
            self.assertEqual((event.status, event.to_phone, event.template), ("sent", "919876543210", "absence_alert"))
            self.assertTrue(event.provider_message_id.startswith("console-"))
            self.assertEqual(log.delivery_status, "sent")

    @override_settings(WHATSAPP_PROVIDER="meta", WHATSAPP_PHONE_NUMBER_ID="1", WHATSAPP_ACCESS_TOKEN="t")
    def test_a_rejected_message_fails_at_once_and_a_flaky_one_is_retried_then_fails(self):
        with tenant_context(self.school):
            with mock.patch("notifications.whatsapp.requests.post") as post:
                post.return_value.status_code = 400
                post.return_value.json.return_value = {"error": {"message": "template not approved"}}
                self._dispatch(key="a")
            rejected = WhatsAppOutboxEvent.objects.get()
            self.assertEqual((rejected.status, rejected.attempts, rejected.error_type), ("failed", 1, "permanent"))
            self.assertIn("template not approved", rejected.last_error)
            self.assertEqual(post.call_count, 1)  # a permanent error is not retried

            # A temporary failure leaves the message waiting for its retry, not failed.
            WhatsAppOutboxEvent.objects.all().delete()
            with mock.patch("notifications.whatsapp.requests.post", side_effect=requests.ConnectionError("down")):
                self._dispatch(key="b")
            flaky = WhatsAppOutboxEvent.objects.get()
            self.assertEqual((flaky.status, flaky.attempts, flaky.error_type), ("retrying", 1, "temporary"))
            self.assertIsNotNone(flaky.next_attempt_at)

            # The last allowed attempt turns the failure into a final one.
            flaky.attempts = flaky.max_attempts - 1
            flaky.save()
            with mock.patch("notifications.whatsapp.requests.post", side_effect=requests.ConnectionError("down")):
                send_whatsapp_event.apply(args=[self.school.schema_name, str(flaky.id)])
            flaky.refresh_from_db()
            self.assertEqual((flaky.status, flaky.attempts), ("failed", flaky.max_attempts))

    @override_settings(WHATSAPP_PROVIDER="console")
    def test_the_recovery_task_requeues_a_stuck_whatsapp_message(self):
        from datetime import timedelta

        from django.utils import timezone

        from .tasks import recover_stale_outbox_events

        with tenant_context(self.school):
            stuck = WhatsAppOutboxEvent.objects.create(to_phone="919876543210", template="absence_alert", params=["a", "b"])
            WhatsAppOutboxEvent.objects.filter(pk=stuck.pk).update(updated_at=timezone.now() - timedelta(minutes=60))
        self.assertGreaterEqual(recover_stale_outbox_events(), 1)
        with tenant_context(self.school):
            stuck.refresh_from_db()
            self.assertEqual(stuck.status, "sent")

    @override_settings(WHATSAPP_PROVIDER="console")
    def test_a_finished_message_is_never_sent_twice(self):
        with tenant_context(self.school):
            self._dispatch()
            event = WhatsAppOutboxEvent.objects.get()
            first_id = event.provider_message_id
            send_whatsapp_event.apply(args=[self.school.schema_name, str(event.id)])
            event.refresh_from_db()
            self.assertEqual(event.provider_message_id, first_id)

    @override_settings(WHATSAPP_PROVIDER="console")
    def test_absence_alerts_also_go_to_opted_in_parents_without_a_login(self):
        from attendance.alerts import _send_whatsapp_absence

        with tenant_context(self.school):
            day = datetime.date(2027, 1, 5)
            _send_whatsapp_absence(self.student, day, "5 Jan 2027")
            _send_whatsapp_absence(self.student, day, "5 Jan 2027")  # saving the register again
            event = WhatsAppOutboxEvent.objects.get()
            self.assertEqual(event.params, ["Asha Rao", "5 Jan 2027"])
            self.assertEqual(event.template, "absence_alert")

    @override_settings(WHATSAPP_PROVIDER="console")
    def test_fee_reminders_use_the_due_soon_and_overdue_templates(self):
        from fees.reminders import _send_whatsapp_reminders

        fee = SimpleNamespace(
            id=uuid.uuid4(), _outstanding=2500, due_date=datetime.date(2027, 2, 1), fee_head=SimpleNamespace(name="Tuition")
        )
        with tenant_context(self.school):
            _send_whatsapp_reminders(fee, self.student, AlertLog.Kind.FEE_DUE_SOON, "fee_due_soon:1")
            _send_whatsapp_reminders(fee, self.student, AlertLog.Kind.FEE_OVERDUE, "fee_overdue:1:0")
            events = {e.template: e for e in WhatsAppOutboxEvent.objects.all()}
            self.assertEqual(set(events), {"fee_due_reminder", "fee_overdue_reminder"})
            params = events["fee_due_reminder"].params
            self.assertEqual((params[0], params[1], params[3]), ("Asha Rao", "Tuition", "2027-02-01"))
            self.assertIn("2,500", params[2])

    @override_settings(WHATSAPP_PROVIDER="console")
    def test_a_failure_in_the_whatsapp_step_never_breaks_the_reminder_run(self):
        from fees.reminders import _send_whatsapp_reminders

        broken = SimpleNamespace(id=uuid.uuid4())  # missing everything a real fee has
        with tenant_context(self.school):
            _send_whatsapp_reminders(broken, self.student, AlertLog.Kind.FEE_DUE_SOON, "k")  # must not raise
            self.assertEqual(WhatsAppOutboxEvent.objects.count(), 0)
