"""
Signing up on a plan: trial schools are created at once; paid ones only after Razorpay confirms a captured
payment of the exact amount. Razorpay is faked (no network, no money).
"""
import hashlib
import hmac
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from fees.gateways import PaymentGatewayError
from organizations.models import Domain, Organization
from payments.models import Payment

from .models import Invoice, Plan, Subscription

KEY, SECRET = "rzp_test_Platform1", "platform_secret_for_tests"
SCHOOL = "plan_signup_school"


class FakeRazorpay:
    def __init__(self):
        self.orders, self.payments, self.down = {}, {}, False

    def __call__(self, method, path, *, key_id, key_secret, body=None, query=None):
        if self.down:
            raise PaymentGatewayError("timeout")
        assert (key_id, key_secret) == (KEY, SECRET), "the platform's own keys must be used"
        if method == "POST" and path == "/orders":
            order_id = f"order_S{len(self.orders) + 1}"
            self.orders[order_id] = body
            return {"id": order_id, "amount": body["amount"], "currency": "INR"}
        if path.startswith("/payments/"):
            return self.payments[path.rsplit("/", 1)[-1]]
        raise AssertionError(path)

    def pay(self, order_id, amount=None, status="captured"):
        payment_id = f"pay_S{len(self.payments) + 1}"
        self.payments[payment_id] = {"id": payment_id, "order_id": order_id, "currency": "INR", "status": status,
                                     "amount": amount if amount is not None else self.orders[order_id]["amount"]}
        return payment_id


def signature(order_id, payment_id, secret=SECRET):
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


@override_settings(PLATFORM_RAZORPAY_KEY_ID=KEY, PLATFORM_RAZORPAY_KEY_SECRET=SECRET)
class PlanSignupTests(TransactionTestCase):
    def setUp(self):
        connection.set_schema_to_public()
        public, _ = Organization.objects.get_or_create(schema_name="public", defaults={"name": "Public Schema"})
        Domain.objects.get_or_create(domain="testserver", tenant=public, defaults={"is_primary": True})
        self.paid = Plan.objects.create(code="t-paid", name="Paid Plan", monthly_price=Decimal("1000.00"),
                                        yearly_price=Decimal("10000.00"))
        self.trial = Plan.objects.create(code="t-trial", name="Trial Plan", monthly_price=Decimal("500.00"), trial_days=14)
        self.fake = FakeRazorpay()
        patcher = mock.patch("billing.signup.api_request", self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = APIClient()

    def tearDown(self):
        connection.set_schema_to_public()
        Invoice.objects.all().delete()
        Subscription.objects.filter(organization__schema_name=SCHOOL).delete()
        Payment.objects.filter(subdomain=SCHOOL).delete()
        for org in Organization.objects.filter(schema_name=SCHOOL):
            org.delete(force_drop=True)
        Plan.objects.filter(code__startswith="t-").delete()

    def _signup(self, plan, cycle="monthly", **extra):
        body = {"plan": plan, "cycle": cycle, "organization_name": "Plan Signup School", "subdomain": SCHOOL,
                "username": "plansignupowner", "email": "owner@plansignup.test", "phone": "9876543210",
                "password": "OwnerPass123!", **extra}
        return self.client.post("/api/billing/signup/", body, format="json")

    def _confirm(self, order_id, payment_id, sig=None):
        return self.client.post("/api/billing/signup/confirm/", {
            "razorpay_order_id": order_id, "razorpay_payment_id": payment_id,
            "razorpay_signature": sig or signature(order_id, payment_id)}, format="json")

    def test_plans_are_listed_publicly(self):
        codes = [p["code"] for p in self.client.get("/api/billing/plans/").data]
        self.assertIn("t-paid", codes)
        self.assertIn("t-trial", codes)

    def test_trial_school_is_created_at_once(self):
        response = self._signup("t-trial")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "ready")
        sub = Subscription.objects.get(organization__schema_name=SCHOOL)
        self.assertEqual(sub.status, Subscription.TRIAL)
        self.assertFalse(Invoice.objects.filter(subscription=sub).exists())
        self.assertEqual(self.fake.orders, {})  # no payment asked for

    def test_paid_signup_charges_price_plus_gst_then_creates_the_school(self):
        response = self._signup("t-paid")
        self.assertEqual(response.data["status"], "pay")
        checkout = response.data["checkout"]
        self.assertEqual(checkout["amount"], 118000)  # ₹1,000 + 18% GST, in paise
        self.assertEqual(checkout["key"], KEY)
        self.assertFalse(Organization.objects.filter(schema_name=SCHOOL).exists())  # not before payment

        payment_id = self.fake.pay(checkout["order_id"])
        confirmed = self._confirm(checkout["order_id"], payment_id)
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.assertEqual(confirmed.data["status"], "ready")
        sub = Subscription.objects.get(organization__schema_name=SCHOOL)
        self.assertEqual(sub.status, Subscription.ACTIVE)
        invoice = Invoice.objects.get(subscription=sub)
        self.assertEqual(invoice.status, Invoice.PAID)
        self.assertEqual(invoice.total, Decimal("1180.00"))
        self.assertEqual(invoice.razorpay_payment_id, payment_id)
        self.assertTrue(invoice.number)

    def test_yearly_signup_buys_a_year(self):
        checkout = self._signup("t-paid", cycle="yearly").data["checkout"]
        self.assertEqual(checkout["amount"], 1180000)
        self._confirm(checkout["order_id"], self.fake.pay(checkout["order_id"]))
        sub = Subscription.objects.get(organization__schema_name=SCHOOL)
        self.assertEqual(sub.cycle, "yearly")
        self.assertEqual((sub.paid_until - Invoice.objects.get(subscription=sub).period_start).days, 365)

    def test_a_forged_confirmation_creates_nothing(self):
        checkout = self._signup("t-paid").data["checkout"]
        payment_id = self.fake.pay(checkout["order_id"])
        response = self._confirm(checkout["order_id"], payment_id, sig=signature(checkout["order_id"], payment_id, "x"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Organization.objects.filter(schema_name=SCHOOL).exists())

    def test_an_underpayment_creates_nothing(self):
        checkout = self._signup("t-paid").data["checkout"]
        payment_id = self.fake.pay(checkout["order_id"], amount=100)
        self.assertEqual(self._confirm(checkout["order_id"], payment_id).status_code, 400)
        self.assertFalse(Organization.objects.filter(schema_name=SCHOOL).exists())

    def test_confirming_twice_creates_one_school_and_one_invoice(self):
        checkout = self._signup("t-paid").data["checkout"]
        payment_id = self.fake.pay(checkout["order_id"])
        self._confirm(checkout["order_id"], payment_id)
        again = self._confirm(checkout["order_id"], payment_id)
        self.assertEqual(again.data["status"], "ready")
        self.assertEqual(Organization.objects.filter(schema_name=SCHOOL).count(), 1)
        self.assertEqual(Invoice.objects.filter(subscription__organization__schema_name=SCHOOL).count(), 1)

    def test_razorpay_unreachable_while_confirming_waits(self):
        checkout = self._signup("t-paid").data["checkout"]
        payment_id = self.fake.pay(checkout["order_id"])
        self.fake.down = True
        response = self._confirm(checkout["order_id"], payment_id)
        self.assertEqual(response.status_code, 202)
        self.assertFalse(Organization.objects.filter(schema_name=SCHOOL).exists())

    def test_a_cycle_the_plan_does_not_offer_is_refused(self):
        response = self._signup("t-paid", cycle="one_time")
        self.assertEqual(response.status_code, 400)
        self.assertIn("plan", response.data)

    def test_bad_school_details_are_refused_before_payment(self):
        response = self._signup("t-paid", email="not-an-email")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.fake.orders, {})

    @override_settings(PLATFORM_RAZORPAY_KEY_ID="", PLATFORM_RAZORPAY_KEY_SECRET="")
    def test_without_platform_keys_signup_says_payment_is_unavailable(self):
        self.assertEqual(self._signup("t-paid").status_code, 503)
