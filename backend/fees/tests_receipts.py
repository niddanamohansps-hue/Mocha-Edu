"""Alerts Stage 4: payment receipt alerts (``fees.receipts``).

Creates tenant schemas and commits real transactions (the alert runs on commit), so it needs a
disposable PostgreSQL database.
"""
from decimal import Decimal
from unittest import mock

from django.db import transaction
from django_tenants.utils import tenant_context

from notifications.models import AlertLog, EmailOutboxEvent, Notification, NotificationSettings

from . import receipts
from .models import Payment, StudentFee
from .services import record_payment, reverse_payment
from .tests_reminders import ReminderFixture


class ReceiptFixture(ReminderFixture):
    def _enable_receipts(self, on=True):
        with tenant_context(self.school):
            NotificationSettings.objects.update_or_create(singleton=True, defaults={"payment_receipts_enabled": on})

    def _record(self, amount="500.00", fee=None):
        with tenant_context(self.school):
            fee = StudentFee.objects.get(pk=(fee or self.fee).pk)
            return record_payment(
                student=fee.student, amount=Decimal(amount), method="cash",
                allocations=[{"student_fee_id": fee.id, "amount": Decimal(amount)}], recorded_by=None,
            )

    def _receipts(self):
        return self._alerts(self.school, AlertLog.Kind.PAYMENT_RECEIPT)


class ReceiptTests(ReceiptFixture):
    def test_nothing_is_sent_until_the_school_switches_it_on(self):
        self._record()
        self.assertEqual(self._receipts(), [])
        with tenant_context(self.school):
            self.assertEqual(Notification.objects.count(), 0)

    def test_the_student_and_the_linked_parent_both_get_the_receipt(self):
        self._enable_receipts()
        payment = self._record("500.00")
        found = self._receipts()
        self.assertEqual({a.recipient_user_id for a in found}, {self.student_user.id, self.parent_user.id})
        with tenant_context(self.school):
            note = Notification.objects.filter(recipient_user_id=self.parent_user.id).get()
            self.assertIn(payment.receipt_number, note.title)
            self.assertIn("500.00", note.body)
            self.assertIn("Tuition", note.body)
            self.assertEqual(EmailOutboxEvent.objects.count(), 2)

    def test_each_payment_gets_its_own_receipt(self):
        self._enable_receipts()
        self._record("500.00")
        self._record("250.00")
        self.assertEqual(len(self._receipts()), 4)

    def test_repeating_the_send_for_one_payment_sends_nothing_more(self):
        self._enable_receipts()
        payment = self._record()
        with tenant_context(self.school):
            again = receipts.send_payment_receipt(payment.id)
        self.assertEqual((again["sent"], again["already_sent"]), (0, 2))
        self.assertEqual(len(self._receipts()), 2)

    def test_a_reversal_is_not_announced_as_a_receipt(self):
        self._enable_receipts()
        payment = self._record()
        with tenant_context(self.school):
            reverse_payment(payment=Payment.objects.get(pk=payment.pk), recorded_by=None, reason="mistake")
        self.assertEqual(len(self._receipts()), 2)

    def test_a_student_with_no_account_and_no_parent_is_counted_not_alerted(self):
        self._enable_receipts()
        lonely = self._student(self.school, "ENR-R-7")
        fee = self._fee(self.school, lonely)
        with tenant_context(self.school):
            payment = self._record("100.00", fee=fee)
            summary = receipts.send_payment_receipt(payment.id)
        self.assertEqual((summary["no_recipient"], summary["sent"]), (1, 0))

    def test_a_failing_alert_never_breaks_recording_the_payment(self):
        self._enable_receipts()
        with mock.patch("fees.receipts.send_payment_receipt", side_effect=RuntimeError("boom")):
            payment = self._record()
        with tenant_context(self.school):
            self.assertTrue(Payment.objects.filter(pk=payment.pk, status="completed").exists())

    def test_a_payment_that_is_rolled_back_sends_nothing(self):
        self._enable_receipts()
        with tenant_context(self.school):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    fee = StudentFee.objects.get(pk=self.fee.pk)
                    record_payment(
                        student=fee.student, amount=Decimal("500.00"), method="cash",
                        allocations=[{"student_fee_id": fee.id, "amount": Decimal("500.00")}], recorded_by=None,
                    )
                    raise RuntimeError("later step failed")
            self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(self._receipts(), [])

    def test_a_school_that_never_enabled_receipts_stays_silent_even_if_others_did(self):
        other = self._school(self.SCHEMA_B)
        self._enable_receipts()
        student = self._student(other, "ENR-R-8", user=self._user("other_student"))
        fee = self._fee(other, student)
        self._pay(other, fee, "100.00")
        self.assertEqual(self._alerts(other), [])


class ReceiptDateTests(ReceiptFixture):
    def test_the_receipt_uses_the_schools_day_not_utcs(self):
        from datetime import datetime, timezone as dt_timezone

        from django.test import override_settings

        self._enable_receipts()
        payment = self._record("300.00")
        # 5 Nov 01:30 in India is still 4 Nov in UTC.
        with tenant_context(self.school):
            Payment.objects.filter(pk=payment.pk).update(created_at=datetime(2026, 11, 4, 20, 0, tzinfo=dt_timezone.utc))
            AlertLog.objects.filter(kind=AlertLog.Kind.PAYMENT_RECEIPT).delete()
            Notification.objects.all().delete()
            with override_settings(ALERT_TIME_ZONE="Asia/Kolkata"):
                receipts.send_payment_receipt(payment.id)
            body = Notification.objects.filter(recipient_user_id=self.parent_user.id).get().body
        self.assertIn("05 Nov 2026", body)
