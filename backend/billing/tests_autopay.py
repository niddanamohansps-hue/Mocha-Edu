"""
Automatic renewal: the Razorpay plan is created once, a school authorises a mandate, and each signed
``subscription.charged`` notice becomes exactly one paid invoice that extends access. Razorpay is faked.
"""
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Domain, Organization
from roles.models import Role, UserRole

from .models import Invoice, Plan, Subscription

KEY, SECRET, HOOK = "rzp_test_Platform1", "platform_secret", "platform_webhook_secret"
WEBHOOK = "/api/billing/webhook/razorpay/"


class FakeRazorpay:
    def __init__(self):
        self.calls, self.orders, self.payments = [], {}, {}

    def __call__(self, method, path, *, key_id, key_secret, body=None, query=None):
        self.calls.append((method, path, body))
        if path == "/plans":
            return {"id": f"plan_R{len(self.calls)}"}
        if path == "/subscriptions":
            return {"id": "sub_R1", "status": "created"}
        if path.endswith("/cancel"):
            return {"id": "sub_R1", "status": "cancelled"}
        if method == "POST" and path == "/orders":
            order_id = f"order_P{len(self.orders) + 1}"
            self.orders[order_id] = body
            return {"id": order_id, "amount": body["amount"]}
        if path.startswith("/payments/"):
            return self.payments[path.rsplit("/", 1)[-1]]
        raise AssertionError(path)

    def pay(self, order_id, amount=None):
        payment_id = f"pay_P{len(self.payments) + 1}"
        self.payments[payment_id] = {"id": payment_id, "order_id": order_id, "currency": "INR", "status": "captured",
                                     "amount": amount if amount is not None else self.orders[order_id]["amount"]}
        return payment_id


@override_settings(PLATFORM_RAZORPAY_KEY_ID=KEY, PLATFORM_RAZORPAY_KEY_SECRET=SECRET,
                   PLATFORM_RAZORPAY_WEBHOOK_SECRET=HOOK)
class AutopayTests(TransactionTestCase):
    SCHEMA, DOMAIN = "autopay_school", "autopay.localhost"

    def setUp(self):
        connection.set_schema_to_public()
        public, _ = Organization.objects.get_or_create(schema_name="public", defaults={"name": "Public Schema"})
        Domain.objects.get_or_create(domain="testserver", tenant=public, defaults={"is_primary": True})
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Autopay School",
                                                  email="office@autopay.test")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.plan = Plan.objects.create(code="ap-plan", name="Autopay Plan", monthly_price=Decimal("1000.00"),
                                        yearly_price=Decimal("10000.00"))
        self.now = timezone.now()
        self.sub = Subscription.objects.create(organization=self.school, plan=self.plan, cycle="monthly",
                                               status=Subscription.ACTIVE, paid_until=self.now + timedelta(days=5))
        self.fake = FakeRazorpay()
        for target in ("billing.autopay.api_request", "fees.razorpay.api_request"):
            patcher = mock.patch(target, self.fake)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.owner = User.objects.create_user(username="ap_owner", email="ap_owner@ap.test", password="Pass1234!")
        self.clerk = User.objects.create_user(username="ap_clerk", email="ap_clerk@ap.test", password="Pass1234!")
        with tenant_context(self.school):
            owner_role, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            UserRole.objects.create(user=self.owner, role=owner_role)
            UserRole.objects.create(user=self.clerk, role=Role.objects.create(name="Clerk", slug="ap-clerk"))

    def tearDown(self):
        connection.set_schema_to_public()
        Invoice.objects.all().delete()
        Subscription.objects.all().delete()
        Plan.objects.filter(code="ap-plan").delete()
        for org in Organization.objects.filter(schema_name=self.SCHEMA):
            org.delete(force_drop=True)
        User.objects.filter(username__in=["ap_owner", "ap_clerk"]).delete()

    def _client(self, username):
        client = APIClient()
        assert client.post("/api/auth/login/", {"username": username, "password": "Pass1234!"},
                           HTTP_HOST=self.DOMAIN).status_code == 200
        return client

    def _webhook(self, event, payment=None, secret=HOOK, sub_id="sub_R1"):
        payload = {"subscription": {"entity": {"id": sub_id}}}
        if payment is not None:
            payload["payment"] = {"entity": payment}
        body = json.dumps({"event": event, "payload": payload}).encode()
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return APIClient().post(WEBHOOK, data=body, content_type="application/json",
                                HTTP_X_RAZORPAY_SIGNATURE=sig)

    def _charge(self, payment_id="pay_A1", amount=118000, status="captured"):
        return {"id": payment_id, "amount": amount, "currency": "INR", "status": status}

    def _start(self):
        response = self._client("ap_owner").post("/api/billing/my/autopay/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def test_owner_starts_autopay_and_the_plan_is_created_once(self):
        checkout = self._start().data["checkout"]
        self.assertEqual(checkout["subscription_id"], "sub_R1")
        self.assertEqual(checkout["key"], KEY)
        plan_calls = [c for c in self.fake.calls if c[1] == "/plans"]
        self.assertEqual(plan_calls[0][2]["item"]["amount"], 118000)  # ₹1,000 + 18% GST
        sub_call = next(c for c in self.fake.calls if c[1] == "/subscriptions")
        self.assertEqual(sub_call[2]["start_at"], int(self.sub.paid_until.timestamp()))  # charged when paid time ends
        self._start()
        self.assertEqual(len([c for c in self.fake.calls if c[1] == "/plans"]), 1)

    def test_a_renewal_charge_extends_access_by_one_period(self):
        self._start()
        response = self._webhook("subscription.charged", self._charge())
        self.assertEqual(response.data["status"], "renewed")
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.paid_until.replace(microsecond=0),
                         (self.now + timedelta(days=35)).replace(microsecond=0))
        invoice = Invoice.objects.get(subscription=self.sub)
        self.assertEqual((invoice.status, invoice.total, invoice.razorpay_payment_id),
                         (Invoice.PAID, Decimal("1180.00"), "pay_A1"))

    def test_the_same_charge_is_recorded_once(self):
        self._start()
        self._webhook("subscription.charged", self._charge())
        self.assertEqual(self._webhook("subscription.charged", self._charge()).data["status"], "already_recorded")
        self.assertEqual(Invoice.objects.filter(subscription=self.sub).count(), 1)

    def test_a_charge_of_the_wrong_amount_is_ignored(self):
        self._start()
        self.assertEqual(self._webhook("subscription.charged", self._charge(amount=100)).data["status"], "ignored")
        self.assertFalse(Invoice.objects.exists())

    def test_an_unsigned_or_unknown_notice_changes_nothing(self):
        self._start()
        self.assertEqual(self._webhook("subscription.charged", self._charge(), secret="wrong").status_code, 400)
        self.assertEqual(self._webhook("subscription.charged", self._charge(), sub_id="sub_other").data["status"],
                         "unknown_subscription")
        self.assertFalse(Invoice.objects.exists())

    def test_halted_keeps_access_until_the_paid_period_ends(self):
        self._start()
        self.assertEqual(self._webhook("subscription.halted").data["status"], "payment_failing")
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.can_write())
        self.assertFalse(self.sub.cancel_at_period_end)

    def test_owner_can_stop_renewal_at_period_end(self):
        self._start()
        response = self._client("ap_owner").post("/api/billing/my/autopay/cancel/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 200)
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.cancel_at_period_end)
        self.assertTrue(self.sub.can_write())  # still paid for 5 days
        self.assertTrue(any(c[1].endswith("/cancel") for c in self.fake.calls))

    def test_owner_sees_plan_status_and_invoices(self):
        self._start()
        self._webhook("subscription.charged", self._charge())
        data = self._client("ap_owner").get("/api/billing/my/", HTTP_HOST=self.DOMAIN).data
        self.assertEqual(data["subscription"]["plan"], "Autopay Plan")
        self.assertTrue(data["subscription"]["autopay"])
        self.assertEqual(len(data["invoices"]), 1)

    def test_billing_needs_the_permission(self):
        clerk = self._client("ap_clerk")
        self.assertEqual(clerk.get("/api/billing/my/", HTTP_HOST=self.DOMAIN).status_code, 403)
        self.assertEqual(clerk.post("/api/billing/my/autopay/", HTTP_HOST=self.DOMAIN).status_code, 403)

    def test_one_time_plans_cannot_autopay(self):
        self.plan.one_time_price = Decimal("50000.00")
        self.plan.save()
        self.sub.cycle = "one_time"
        self.sub.save()
        response = self._client("ap_owner").post("/api/billing/my/autopay/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 400)

    # --- paying now, and the invoice PDF ---

    def _pay_now(self, client, cycle=None, amount=None, signature_secret=SECRET):
        start = client.post("/api/billing/my/pay/", {"cycle": cycle} if cycle else {}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(start.status_code, 200, start.data)
        order_id = start.data["checkout"]["order_id"]
        payment_id = self.fake.pay(order_id, amount=amount)
        sig = hmac.new(signature_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        return start, client.post("/api/billing/my/pay/confirm/", {
            "razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": sig},
            format="json", HTTP_HOST=self.DOMAIN)

    def test_pay_now_extends_access_and_gives_a_pdf_invoice(self):
        client = self._client("ap_owner")
        start, confirm = self._pay_now(client)
        self.assertEqual(start.data["checkout"]["amount"], 118000)
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.paid_until.replace(microsecond=0), (self.now + timedelta(days=35)).replace(microsecond=0))
        invoice_id = confirm.data["invoice"]["id"]
        pdf = client.get(f"/api/billing/my/invoices/{invoice_id}/pdf/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_pay_now_one_time_for_life(self):
        self.plan.one_time_price = Decimal("50000.00")
        self.plan.save()
        _, confirm = self._pay_now(self._client("ap_owner"), cycle="one_time")
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.sub.refresh_from_db()
        self.assertIsNone(self.sub.paid_until)
        self.assertEqual(self.sub.cycle, "one_time")

    def test_pay_now_with_a_forged_signature_or_short_amount_is_refused(self):
        client = self._client("ap_owner")
        _, forged = self._pay_now(client, signature_secret="wrong")
        self.assertEqual(forged.status_code, 400)
        _, short = self._pay_now(client, amount=100)
        self.assertEqual(short.status_code, 400)
        self.assertFalse(Invoice.objects.filter(status=Invoice.PAID).exists())

    def test_another_schools_invoice_pdf_is_not_found(self):
        Organization.auto_create_schema = False  # only its billing rows are needed, not a school schema
        try:
            other = Organization.objects.create(schema_name="autopay_other", name="Other School")
        finally:
            Organization.auto_create_schema = True
        try:
            other_sub = Subscription.objects.create(organization=other, plan=self.plan, cycle="monthly",
                                                    status=Subscription.ACTIVE)
            invoice = Invoice.objects.create(subscription=other_sub, number="ES/2026-27/99999", status=Invoice.PAID,
                                             plan_name="x", cycle="monthly", period_start=self.now, amount=1,
                                             gst_percent=18, gst_amount=0, total=1, billed_name="Other")
            response = self._client("ap_owner").get(f"/api/billing/my/invoices/{invoice.id}/pdf/", HTTP_HOST=self.DOMAIN)
            self.assertEqual(response.status_code, 404)
        finally:
            Invoice.objects.filter(subscription__organization=other).delete()
            Subscription.objects.filter(organization=other).delete()
            connection.set_schema_to_public()
            Organization.objects.filter(pk=other.pk).delete()

    def test_owner_saves_gst_details_and_a_bad_gstin_is_refused(self):
        client = self._client("ap_owner")
        bad = client.put("/api/billing/my/gst/", {"gstin": "12345"}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(bad.status_code, 400)
        ok = client.put("/api/billing/my/gst/", {"gstin": "27abcde1234f1z5"}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual((ok.data["billing_state"], ok.data["state_name"]), ("27", "Maharashtra"))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.billing_gstin, "27ABCDE1234F1Z5")
