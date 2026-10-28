from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase

from organizations.models import Organization

from .models import MONTHLY, ONE_TIME, YEARLY, Invoice, Plan, Subscription
from .services import (
    BillingError,
    financial_year,
    gst_for,
    issue_invoice,
    mark_invoice_paid,
    refresh_status,
    start_subscription,
)

T0 = datetime(2026, 10, 28, 10, 0, tzinfo=dt_timezone.utc)


class PureRulesTests(SimpleTestCase):
    def test_gst_is_rounded_to_paise(self):
        self.assertEqual(gst_for(Decimal("999.00"), Decimal("18")), Decimal("179.82"))
        self.assertEqual(gst_for(Decimal("0.05"), Decimal("18")), Decimal("0.01"))

    def test_indian_financial_year(self):
        self.assertEqual(financial_year(datetime(2026, 4, 1, 6, tzinfo=dt_timezone.utc)), "2026-27")
        self.assertEqual(financial_year(datetime(2027, 3, 31, 6, tzinfo=dt_timezone.utc)), "2026-27")
        self.assertEqual(financial_year(datetime(2026, 3, 31, 6, tzinfo=dt_timezone.utc)), "2025-26")


class SubscriptionLifecycleTests(TransactionTestCase):
    def setUp(self):
        connection.set_schema_to_public()
        Organization.auto_create_schema = False  # billing lives in the public schema; no school schema needed
        self.addCleanup(setattr, Organization, "auto_create_schema", True)
        self.school = Organization.objects.create(schema_name="billing_school", name="Billing School",
                                                  email="office@billing.test", address="1 MG Road")
        self.plan = Plan.objects.create(code="pro", name="Professional", monthly_price=Decimal("999.00"),
                                        yearly_price=Decimal("9990.00"), one_time_price=Decimal("25000.00"),
                                        one_time_validity_days=None, trial_days=14)
        self.no_trial = Plan.objects.create(code="basic", name="Basic", monthly_price=Decimal("499.00"))

    def tearDown(self):
        Invoice.objects.all().delete()
        Subscription.objects.all().delete()
        Plan.objects.all().delete()
        Organization.objects.filter(schema_name="billing_school").delete()

    def _paid(self, subscription, cycle, when, payment_id):
        invoice = issue_invoice(subscription, now=when, cycle=cycle)
        return mark_invoice_paid(invoice.id, payment_id=payment_id, now=when)[0]

    def test_trial_then_grace_then_read_only(self):
        sub = start_subscription(self.school, self.plan, MONTHLY, now=T0)
        self.assertEqual(sub.status, Subscription.TRIAL)
        self.assertTrue(sub.can_write(T0 + timedelta(days=13)))
        refresh_status(sub, now=T0 + timedelta(days=14))
        self.assertEqual(sub.status, Subscription.PAST_DUE)
        self.assertTrue(sub.can_write(T0 + timedelta(days=20)))  # 7 grace days
        refresh_status(sub, now=T0 + timedelta(days=21))
        self.assertEqual(sub.status, Subscription.READ_ONLY)
        self.assertFalse(sub.can_write(T0 + timedelta(days=21)))

    def test_a_plan_without_trial_waits_for_payment(self):
        sub = start_subscription(self.school, self.no_trial, MONTHLY, now=T0)
        self.assertEqual(sub.status, Subscription.PENDING)
        self.assertFalse(sub.can_write(T0))

    def test_a_cycle_the_plan_does_not_offer_is_refused(self):
        with self.assertRaises(BillingError):
            start_subscription(self.school, self.no_trial, YEARLY, now=T0)

    def test_paying_monthly_gives_30_days_with_gst_and_a_number(self):
        sub = start_subscription(self.school, self.no_trial, MONTHLY, now=T0)
        invoice = self._paid(sub, MONTHLY, T0, "pay_1")
        sub.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("588.82"))  # 499 + 18% GST
        self.assertEqual(invoice.number, "ES/2026-27/00001")
        self.assertEqual(invoice.billed_name, "Billing School")
        self.assertEqual(sub.status, Subscription.ACTIVE)
        self.assertEqual(sub.paid_until, T0 + timedelta(days=30))

    def test_invoice_numbers_run_in_order(self):
        sub = start_subscription(self.school, self.no_trial, MONTHLY, now=T0)
        first = self._paid(sub, MONTHLY, T0, "pay_1")
        second = self._paid(sub, MONTHLY, T0 + timedelta(days=29), "pay_2")
        self.assertEqual([first.number, second.number], ["ES/2026-27/00001", "ES/2026-27/00002"])

    def test_paying_early_keeps_the_remaining_days(self):
        sub = start_subscription(self.school, self.no_trial, MONTHLY, now=T0)
        self._paid(sub, MONTHLY, T0, "pay_1")
        self._paid(sub, MONTHLY, T0 + timedelta(days=25), "pay_2")
        sub.refresh_from_db()
        self.assertEqual(sub.paid_until, T0 + timedelta(days=60))

    def test_paying_late_starts_from_the_payment(self):
        sub = start_subscription(self.school, self.no_trial, MONTHLY, now=T0)
        self._paid(sub, MONTHLY, T0, "pay_1")
        sub.refresh_from_db()  # paying updated the stored subscription
        late = T0 + timedelta(days=50)
        refresh_status(sub, now=late)
        self.assertEqual(sub.status, Subscription.READ_ONLY)
        self._paid(sub, MONTHLY, late, "pay_2")
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.ACTIVE)
        self.assertEqual(sub.paid_until, late + timedelta(days=30))
        self.assertTrue(sub.can_write(late))

    def test_yearly_and_lifetime_one_time(self):
        sub = start_subscription(self.school, self.plan, YEARLY, now=T0)
        self._paid(sub, YEARLY, T0, "pay_y")
        sub.refresh_from_db()
        self.assertEqual(sub.paid_until, T0 + timedelta(days=365))
        self._paid(sub, ONE_TIME, T0 + timedelta(days=1), "pay_life")
        sub.refresh_from_db()
        self.assertIsNone(sub.paid_until)  # for life
        self.assertEqual(sub.cycle, ONE_TIME)
        self.assertTrue(sub.can_write(T0 + timedelta(days=5000)))
        self.assertFalse(refresh_status(sub, now=T0 + timedelta(days=5000)))

    def test_one_time_for_a_fixed_term(self):
        self.plan.one_time_validity_days = 3 * 365
        self.plan.save()
        sub = start_subscription(self.school, self.plan, ONE_TIME, now=T0)
        self._paid(sub, ONE_TIME, T0, "pay_3y")
        sub.refresh_from_db()
        self.assertEqual(sub.paid_until, T0 + timedelta(days=3 * 365))

    def test_the_same_payment_is_recorded_once(self):
        sub = start_subscription(self.school, self.no_trial, MONTHLY, now=T0)
        invoice = issue_invoice(sub, now=T0)
        _, first = mark_invoice_paid(invoice.id, payment_id="pay_1", now=T0)
        _, again = mark_invoice_paid(invoice.id, payment_id="pay_1", now=T0)
        sub.refresh_from_db()
        self.assertTrue(first)
        self.assertFalse(again)
        self.assertEqual(sub.paid_until, T0 + timedelta(days=30))
        other = issue_invoice(sub, now=T0)
        with self.assertRaises(BillingError):
            mark_invoice_paid(other.id, payment_id="pay_1", now=T0)

    def test_a_wrong_amount_is_refused(self):
        sub = start_subscription(self.school, self.no_trial, MONTHLY, now=T0)
        invoice = issue_invoice(sub, now=T0)
        with self.assertRaises(BillingError):
            mark_invoice_paid(invoice.id, payment_id="pay_1", paid_amount_paise=100, now=T0)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.DRAFT)

    def test_legacy_schools_always_have_access(self):
        sub = Subscription.objects.create(organization=self.school, plan=self.plan, cycle=YEARLY,
                                          status=Subscription.ACTIVE, is_legacy=True)
        self.assertTrue(sub.can_write(T0 + timedelta(days=10000)))
        self.assertFalse(refresh_status(sub, now=T0 + timedelta(days=10000)))

    def test_cancel_at_period_end(self):
        sub = start_subscription(self.school, self.no_trial, MONTHLY, now=T0)
        self._paid(sub, MONTHLY, T0, "pay_1")
        sub.refresh_from_db()
        sub.cancel_at_period_end = True
        sub.save()
        self.assertTrue(sub.can_write(T0 + timedelta(days=29)))
        refresh_status(sub, now=T0 + timedelta(days=30))
        self.assertEqual(sub.status, Subscription.CANCELLED)
        self.assertFalse(sub.can_write(T0 + timedelta(days=30)))
