"""Stage F2c: reconciliation of paid signups (gateway check, retries, attention alerts, data
discard, admin retry, schedule). No test creates a tenant schema: provisioning is patched.
"""
import time
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import override_settings
from django.utils import timezone

from fees.gateways import GatewayStatusResult
from . import services, tasks
from .admin import PaymentAdmin
from .models import Payment
from .tests_security import PROVISION, SECRET, SignupPaymentTestBase
from .tests_state_machine import fake_provision

ASK = "payments.services._ask_gateway"
COMPLETE = GatewayStatusResult(status="COMPLETE", gateway_reference="REF-1")


class ReconBase(SignupPaymentTestBase):
    """Never lets a test reach the real gateway: by default every status query answers ERROR."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch(ASK, return_value=GatewayStatusResult(status="ERROR"))
        patcher.start()
        self.addCleanup(patcher.stop)


def age(payment, **fields):
    """Move a payment's timestamps into the past (created_at is auto_now_add, so use update)."""
    Payment.objects.filter(pk=payment.pk).update(**fields)
    payment.refresh_from_db()
    return payment


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class GatewayReconciliationTests(ReconBase):
    def pending(self, name="rec_one", minutes_old=30, **extra):
        payment = self.make_payment(subdomain=name, username=name, email=f"{name}@rec.example")
        return age(payment, created_at=timezone.now() - timedelta(minutes=minutes_old), **extra)

    def run_task(self):
        return tasks.reconcile_signup_payments()

    def test_a_payment_found_complete_is_recorded_and_provisioned(self):
        payment = self.pending()
        with mock.patch(ASK, return_value=COMPLETE), mock.patch(PROVISION, side_effect=fake_provision()):
            summary = self.run_task()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.PROVISIONED)
        self.assertEqual(payment.gateway_reference, "REF-1")
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(summary["gateway"]["paid_found"], 1)
        self.assertEqual(payment.password, "")

    def test_answers_other_than_complete_change_nothing_but_the_check_time(self):
        for status in ("PENDING", "AMBIGUOUS", "NOT_FOUND", "CANCELED", "ERROR", "INVALID", "UNKNOWN"):
            with self.subTest(status):
                Payment.objects.all().delete()
                payment = self.pending()
                with mock.patch(ASK, return_value=GatewayStatusResult(status=status)), mock.patch(PROVISION) as provision:
                    self.run_task()
                payment.refresh_from_db()
                self.assertEqual(payment.status, Payment.PENDING)
                self.assertIsNone(payment.paid_at)
                self.assertIsNotNone(payment.gateway_checked_at)
                provision.assert_not_called()

    def test_a_recent_signup_is_left_alone_until_the_grace_period_passes(self):
        self.pending(minutes_old=2)
        with mock.patch(ASK) as ask:
            self.run_task()
        ask.assert_not_called()

    def test_a_checked_signup_is_not_asked_again_before_the_recheck_interval(self):
        payment = self.pending()
        with mock.patch(ASK, return_value=GatewayStatusResult(status="PENDING")) as ask:
            self.run_task()
            self.run_task()
        self.assertEqual(ask.call_count, 1)
        age(payment, gateway_checked_at=timezone.now() - timedelta(minutes=11))
        with mock.patch(ASK, return_value=GatewayStatusResult(status="PENDING")) as ask:
            self.run_task()
        self.assertEqual(ask.call_count, 1)

    def test_an_expired_signup_whose_data_is_still_held_is_checked_and_honoured(self):
        payment = self.pending()
        age(payment, status=Payment.EXPIRED, expires_at=timezone.now() - timedelta(hours=2))
        with mock.patch(ASK, return_value=COMPLETE), mock.patch(PROVISION, side_effect=fake_provision()):
            self.run_task()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.PROVISIONED)

    def test_expired_signups_without_data_or_already_flagged_are_not_asked(self):
        no_data = self.pending("rec_nodata")
        age(no_data, status=Payment.EXPIRED, password="")
        flagged = self.pending("rec_flagged")
        age(flagged, status=Payment.EXPIRED, paid_at=timezone.now())
        with mock.patch(ASK) as ask:
            self.run_task()
        ask.assert_not_called()

    def test_the_time_budget_defers_the_rest(self):
        for index in range(3):
            self.pending(f"rec_b{index}")
        with mock.patch(ASK, return_value=GatewayStatusResult(status="PENDING")) as ask:
            summary, _ = services.reconcile_with_gateway(batch_size=10, deadline=time.monotonic() - 1)
        ask.assert_not_called()
        self.assertEqual(summary["deferred"], 3)

    def test_the_batch_size_bounds_the_work(self):
        for index in range(4):
            self.pending(f"rec_c{index}")
        with mock.patch(ASK, return_value=GatewayStatusResult(status="PENDING")) as ask:
            tasks.reconcile_signup_payments(batch_size=2)
        self.assertEqual(ask.call_count, 2)

    def test_unpaid_signups_past_their_reservation_expire(self):
        payment = self.pending(minutes_old=1)
        age(payment, expires_at=timezone.now() - timedelta(minutes=1))
        summary = self.run_task()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.EXPIRED)
        self.assertEqual(summary["expired"], 1)


@override_settings(ESEWA_CLIENT_SECRET=SECRET, ESEWA_PRODUCT_CODE="EPAYTEST")
class StatusQueryIdentityTests(SignupPaymentTestBase):
    """The real status query (network patched): identity must match the stored payment."""

    def setUp(self):
        super().setUp()
        self.payment = age(
            self.make_payment(), created_at=timezone.now() - timedelta(minutes=30)
        )

    def response(self, **overrides):
        data = {
            "status": "COMPLETE", "ref_id": "R-9", "total_amount": "500.0",
            "transaction_uuid": self.payment.transaction_uuid.hex, "product_code": "EPAYTEST",
        }
        data.update(overrides)
        return data

    def run_with(self, data):
        with mock.patch("fees.gateways._fetch_status_json", return_value=data), mock.patch(PROVISION, side_effect=fake_provision()):
            tasks.reconcile_signup_payments()
        self.payment.refresh_from_db()
        return self.payment.status

    def test_a_matching_complete_response_is_accepted(self):
        self.assertEqual(self.run_with(self.response()), Payment.PROVISIONED)

    def test_mismatched_or_incomplete_identity_is_rejected(self):
        cases = {
            "other transaction": self.response(transaction_uuid="f" * 32),
            "other merchant": self.response(product_code="OTHER"),
            "other amount": self.response(total_amount="1.00"),
            "no transaction": {k: v for k, v in self.response().items() if k != "transaction_uuid"},
            "no amount": {k: v for k, v in self.response().items() if k != "total_amount"},
            "not an object": ["COMPLETE"],
        }
        for label, data in cases.items():
            with self.subTest(label):
                Payment.objects.filter(pk=self.payment.pk).update(status=Payment.PENDING, gateway_checked_at=None)
                self.assertEqual(self.run_with(data), Payment.PENDING)

    def test_a_transport_failure_says_nothing_about_the_payment(self):
        with mock.patch("fees.gateways._fetch_status_json", side_effect=OSError("down")):
            tasks.reconcile_signup_payments()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PENDING)

    def test_the_test_merchant_is_refused_in_production(self):
        with override_settings(DEBUG=False, EDUSEKAI_ALLOW_DERIVED_TEST_DB=False):
            with mock.patch("fees.gateways._fetch_status_json") as fetch:
                tasks.reconcile_signup_payments()
        fetch.assert_not_called()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.PENDING)


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class ProvisioningRetryTests(ReconBase):
    def failed(self, name="retry_one", attempts=1, code="unexpected_error", minutes=10, **extra):
        payment = self.make_payment(subdomain=name, username=name, email=f"{name}@r.example")
        return age(
            payment, status=Payment.PROVISIONING_FAILED, paid_at=timezone.now(), provisioning_attempts=attempts,
            failure_code=code, updated_at=timezone.now() - timedelta(minutes=minutes), **extra,
        )

    def test_a_failed_setup_is_retried_automatically(self):
        payment = self.failed()
        with mock.patch(PROVISION, side_effect=fake_provision()):
            summary = tasks.reconcile_signup_payments()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.PROVISIONED)
        self.assertEqual(payment.provisioning_attempts, 2)
        self.assertEqual(summary["provisioning_queued"], 1)

    def test_a_paid_signup_that_never_started_setup_is_picked_up(self):
        payment = self.failed(attempts=0, code="")
        age(payment, status=Payment.PAID)
        with mock.patch(PROVISION, side_effect=fake_provision()):
            tasks.reconcile_signup_payments()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.PROVISIONED)

    def test_retries_wait_for_the_backoff(self):
        self.failed(minutes=1)
        with mock.patch(PROVISION) as provision:
            tasks.reconcile_signup_payments()
        provision.assert_not_called()

    def test_retries_stop_at_the_maximum_and_a_person_is_alerted(self):
        payment = self.failed(attempts=3)
        with mock.patch(PROVISION) as provision, self.assertLogs("payments.services", level="ERROR") as captured:
            summary = tasks.reconcile_signup_payments()
        provision.assert_not_called()
        self.assertEqual(summary["attention_notified"], 1)
        self.assertIn(str(payment.transaction_uuid), "\n".join(captured.output))

    def test_failures_that_need_a_person_are_not_retried_automatically(self):
        for code in ("subdomain_taken", "username_taken", "password_mismatch", "domain_conflict",
                     "data_discarded", "legacy_no_institution"):
            with self.subTest(code):
                Payment.objects.all().delete()
                self.failed(code=code)
                with mock.patch(PROVISION) as provision:
                    tasks.reconcile_signup_payments()
                provision.assert_not_called()

    def test_the_setup_task_can_be_queued_twice_but_works_once(self):
        payment = self.failed()
        with mock.patch(PROVISION, side_effect=fake_provision()) as provision:
            self.assertEqual(tasks.provision_signup_payment(payment.pk), services.PROVISIONED)
            self.assertEqual(tasks.provision_signup_payment(payment.pk), services.ALREADY_PROVISIONED)
        self.assertEqual(provision.call_count, 1)

    def test_the_setup_task_has_its_own_longer_time_limit(self):
        self.assertGreater(tasks.provision_signup_payment.time_limit, 30)
        self.assertIsNone(tasks.reconcile_signup_payments.time_limit)

    def test_a_crashed_attempt_is_released_and_retried_in_the_same_run(self):
        payment = self.failed(code="")
        age(payment, status=Payment.PROVISIONING, updated_at=timezone.now() - timedelta(hours=1))
        with mock.patch(PROVISION, side_effect=fake_provision()):
            summary = tasks.reconcile_signup_payments()
        payment.refresh_from_db()
        self.assertEqual(summary["stalled_released"], 1)
        self.assertEqual(payment.status, Payment.PROVISIONED)


@override_settings(ESEWA_CLIENT_SECRET=SECRET, SIGNUP_PAYMENT_ALERT_EMAILS="ops@example.com, boss@example.com")
class AttentionAlertTests(ReconBase):
    def stuck(self, **extra):
        payment = self.make_payment()
        return age(
            payment, status=Payment.PROVISIONING_FAILED, paid_at=timezone.now(), provisioning_attempts=3,
            failure_code="subdomain_taken", **extra,
        )

    def test_operators_are_emailed_once_without_customer_details(self):
        payment = self.stuck()
        self.assertEqual(services.notify_attention(), 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(sorted(message.to), ["boss@example.com", "ops@example.com"])
        self.assertIn(str(payment.transaction_uuid), message.body)
        self.assertIn("subdomain_taken", message.body)
        for private in (payment.email, payment.phone, payment.username, "OwnerPass123!", payment.password):
            self.assertNotIn(private, message.subject + message.body)
        self.assertEqual(services.notify_attention(), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_failed_email_is_retried_on_the_next_run(self):
        payment = self.stuck()
        with mock.patch("django.core.mail.send_mail", side_effect=OSError("smtp down")):
            self.assertEqual(services.notify_attention(), 0)
        payment.refresh_from_db()
        self.assertIsNone(payment.attention_notified_at)
        self.assertEqual(services.notify_attention(), 1)

    @override_settings(SIGNUP_PAYMENT_ALERT_EMAILS="")
    def test_without_recipients_it_is_logged_loudly_and_marked(self):
        payment = self.stuck()
        with self.assertLogs("payments.services", level="ERROR") as captured:
            self.assertEqual(services.notify_attention(), 1)
        self.assertIn(str(payment.transaction_uuid), "\n".join(captured.output))
        self.assertEqual(len(mail.outbox), 0)
        payment.refresh_from_db()
        self.assertIsNotNone(payment.attention_notified_at)

    def test_paid_but_unusable_signups_are_flagged(self):
        for status in (Payment.EXPIRED, Payment.FAILED):
            with self.subTest(status):
                Payment.objects.all().delete()
                payment = self.make_payment()
                age(payment, status=status, paid_at=timezone.now(), failure_code="data_discarded")
                self.assertEqual(services.notify_attention(), 1)

    def test_healthy_and_unpaid_signups_are_never_flagged(self):
        payment = self.make_payment()
        for status in (Payment.PENDING, Payment.EXPIRED, Payment.PROVISIONED, Payment.PROVISIONING):
            age(payment, status=status)
            self.assertEqual(services.notify_attention(), 0, status)

    def test_a_paid_signup_still_within_its_retries_is_not_flagged(self):
        payment = self.make_payment()
        age(payment, status=Payment.PROVISIONING_FAILED, paid_at=timezone.now(), provisioning_attempts=1,
            failure_code="unexpected_error")
        self.assertEqual(services.notify_attention(), 0)


@override_settings(ESEWA_CLIENT_SECRET=SECRET, SIGNUP_PAYMENT_DATA_RETENTION_DAYS=7)
class DataDiscardTests(ReconBase):
    def expired(self, name, days_ago, **extra):
        payment = self.make_payment(subdomain=name, username=name, email=f"{name}@d.example")
        return age(payment, status=Payment.EXPIRED, expires_at=timezone.now() - timedelta(days=days_ago), **extra)

    def test_old_unpaid_data_is_discarded_and_recent_data_is_kept(self):
        old = self.expired("disc_old", 8)
        recent = self.expired("disc_recent", 6)
        self.assertEqual(services.discard_expired_signup_data(), 1)
        old.refresh_from_db()
        recent.refresh_from_db()
        self.assertEqual(old.password, "")
        self.assertNotEqual(recent.password, "")

    def test_paid_signups_keep_their_data_whatever_their_age(self):
        paid = self.expired("disc_paid", 30, paid_at=timezone.now())
        self.assertEqual(services.discard_expired_signup_data(), 0)
        paid.refresh_from_db()
        self.assertNotEqual(paid.password, "")

    def test_only_expired_or_failed_signups_are_touched(self):
        for status in (Payment.PENDING, Payment.PAID, Payment.PROVISIONING_FAILED, Payment.PROVISIONED):
            payment = self.make_payment(subdomain=f"disc_{status.lower()}", username=status.lower(),
                                        email=f"{status.lower()}@d.example")
            age(payment, status=status, expires_at=timezone.now() - timedelta(days=30))
        # PROVISIONED rows already hold no password in real life; here we only prove they are untouched.
        self.assertEqual(services.discard_expired_signup_data(), 0)

    def test_the_task_discards_as_part_of_its_run(self):
        self.expired("disc_task", 9)
        summary = tasks.reconcile_signup_payments()
        self.assertEqual(summary["data_discarded"], 1)


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class AdminRetryAndScheduleTests(ReconBase):
    def test_the_admin_retry_action_queues_only_paid_signups_without_an_institution(self):
        stuck = age(self.make_payment(), status=Payment.PROVISIONING_FAILED, paid_at=timezone.now(),
                    provisioning_attempts=3, failure_code="legacy_no_institution")
        unpaid = self.make_payment(subdomain="admin_unpaid", username="adminunpaid", email="au@a.example")
        admin_instance = PaymentAdmin(Payment, mock.MagicMock())
        request = mock.MagicMock()
        with mock.patch(PROVISION, side_effect=fake_provision()) as provision, \
                mock.patch.object(admin_instance, "message_user") as message:
            admin_instance.retry_provisioning(request, Payment.objects.all())
        stuck.refresh_from_db()
        unpaid.refresh_from_db()
        self.assertEqual(stuck.status, Payment.PROVISIONED)
        self.assertEqual(unpaid.status, Payment.PENDING)
        self.assertEqual(provision.call_count, 1)
        self.assertIn("Queued 1", message.call_args.args[1])

    def test_the_task_is_scheduled_and_registered(self):
        from django.conf import settings
        from config.celery import app

        entry = settings.CELERY_BEAT_SCHEDULE["reconcile-signup-payments"]
        self.assertEqual(entry["task"], "payments.tasks.reconcile_signup_payments")
        self.assertIn(entry["task"], app.tasks)
        self.assertIn("payments.tasks.provision_signup_payment", app.tasks)

    def test_the_summary_is_json_serialisable(self):
        import json
        json.dumps(tasks.reconcile_signup_payments())
        self.assertIsInstance(Decimal("1"), Decimal)
