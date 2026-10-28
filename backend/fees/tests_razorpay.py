"""
Razorpay: order creation, the browser's signed confirmation, the signed webhook, reconciliation,
and the school's gateway settings. Razorpay itself is replaced by FakeRazorpay: no network, no money.
"""
import hashlib
import hmac
import json
from decimal import Decimal
from unittest import mock

from django.test import TransactionTestCase
from django_tenants.utils import tenant_context

from .gateways import PaymentGatewayError
from .models import OnlinePaymentOrder, TenantPaymentGatewayConfig
from .razorpay import to_paise
from .services import (
    PaymentEvidenceRejected,
    assign_student_fee,
    initiate_online_payment_order,
    reconcile_online_payment_order,
    settle_online_payment_order,
)
from .tests import FeesFixtureMixin

KEY_ID = "rzp_test_EduSekai123"
SECRET = "rzp_secret_for_tests"
WEBHOOK_SECRET = "rzp_webhook_secret_for_tests"
WEBHOOK_URL = "/api/fees/online/webhook/razorpay/"


class FakeRazorpay:
    """Answers like the Razorpay API for the calls the adapter makes."""

    def __init__(self):
        self.orders, self.payments, self.down = {}, {}, False

    def __call__(self, method, path, *, key_id, key_secret, body=None, query=None):
        if self.down:
            raise PaymentGatewayError("Razorpay could not be reached (timeout)")
        if key_id != KEY_ID or key_secret != SECRET:
            raise PaymentGatewayError("Razorpay answered 401")
        if method == "POST" and path == "/orders":
            order_id = f"order_T{len(self.orders) + 1}"
            self.orders[order_id] = body
            return {"id": order_id, "amount": body["amount"], "currency": body["currency"], "status": "created"}
        if method == "GET" and path == "/orders":
            return {"items": []}
        if path.startswith("/payments/"):
            payment = self.payments.get(path.rsplit("/", 1)[-1])
            if payment is None:
                raise PaymentGatewayError("Razorpay answered 404")
            return payment
        if path.startswith("/orders/") and path.endswith("/payments"):
            order_id = path.split("/")[2]
            return {"items": [p for p in self.payments.values() if p["order_id"] == order_id]}
        raise AssertionError(f"unexpected call {method} {path}")

    def pay(self, order_id, status="captured", amount=None):
        payment_id = f"pay_T{len(self.payments) + 1}"
        self.payments[payment_id] = {
            "id": payment_id, "order_id": order_id, "status": status, "currency": "INR",
            "amount": amount if amount is not None else self.orders[order_id]["amount"],
        }
        return payment_id


def checkout_signature(order_id, payment_id, secret=SECRET):
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


class RazorpayTests(FeesFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.fake = FakeRazorpay()
        patcher = mock.patch("fees.razorpay.api_request", self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        with tenant_context(self.school):
            self.fee = assign_student_fee(
                student=self.student1, fee_head=self.fee_head, academic_year="2026", amount_due=Decimal("1250.50"),
            )
            config = TenantPaymentGatewayConfig(gateway="razorpay", merchant_code=KEY_ID, mode="test", is_active=True)
            config.set_secret(SECRET)
            config.set_webhook_secret(WEBHOOK_SECRET)
            config.save()

    def _initiate(self, amount=Decimal("1250.50")):
        with tenant_context(self.school):
            return initiate_online_payment_order(
                student=self.student1, amount=amount,
                allocations=[{"student_fee_id": self.fee.id, "amount": amount}],
                gateway="razorpay", created_by=self.parent1_user, callback_kind="parent_portal",
            )

    def _confirm(self, order, payment_id, signature=None, rz_order_id=None):
        rz_order_id = rz_order_id or order.gateway_session_id
        with tenant_context(self.school):
            return settle_online_payment_order(
                order_id_or_gateway_order_id=str(order.id),
                raw_callback_payload={
                    "razorpay_order_id": rz_order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature or checkout_signature(rz_order_id, payment_id),
                },
            )

    def _webhook(self, order, event="payment.captured", secret=WEBHOOK_SECRET, host=None):
        body = json.dumps({
            "event": event,
            "payload": {"payment": {"entity": {"order_id": order.gateway_session_id, "id": "pay_x"}}},
        }).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        from rest_framework.test import APIClient

        return APIClient().post(WEBHOOK_URL, data=body, content_type="application/json",
                                HTTP_HOST=host or self.DOMAIN, HTTP_X_RAZORPAY_SIGNATURE=signature)

    def _reload(self, order):
        with tenant_context(self.school):
            return OnlinePaymentOrder.objects.select_related("payment").get(id=order.id)

    # --- creating the order ---

    def test_amount_is_sent_in_paise(self):
        self.assertEqual(to_paise(Decimal("1250.50")), 125050)
        self.assertEqual(to_paise(Decimal("0.10")), 10)
        self.assertEqual(to_paise(Decimal("1")), 100)

    def test_initiation_creates_a_razorpay_order_for_checkout(self):
        order, payload = self._initiate()
        self.assertEqual(payload.method, "CHECKOUT")
        self.assertEqual(payload.form_parameters["key"], KEY_ID)
        self.assertEqual(payload.form_parameters["amount"], "125050")
        self.assertEqual(payload.form_parameters["order_id"], order.gateway_session_id)
        self.assertEqual(self.fake.orders[order.gateway_session_id]["amount"], 125050)
        self.assertEqual(self._reload(order).status, "pending")

    def test_checkout_shows_the_school_and_the_payers_details(self):
        _, payload = self._initiate()
        params = payload.form_parameters
        self.assertEqual(params["school_name"], self.school.name)
        self.assertEqual(params["prefill_name"], "Pat Guardian")  # the parent who started the payment
        for key in ("prefill_email", "prefill_contact"):
            self.assertIn(key, params)

    def test_initiation_fails_cleanly_when_razorpay_is_down(self):
        self.fake.down = True
        with self.assertRaises(PaymentGatewayError):
            self._initiate()
        with tenant_context(self.school):
            self.assertFalse(OnlinePaymentOrder.objects.exists())  # no orphan order

    # --- the browser's confirmation ---

    def test_a_captured_payment_settles_with_a_receipt(self):
        order, _ = self._initiate()
        payment_id = self.fake.pay(order.gateway_session_id)
        result = self._confirm(order, payment_id)
        self.assertEqual(result["status"], "success")
        order = self._reload(order)
        self.assertEqual(order.status, "success")
        self.assertEqual(order.gateway_reference, payment_id)
        self.assertEqual(order.payment.amount, Decimal("1250.50"))
        self.assertTrue(order.payment.receipt_number)

    def test_a_forged_signature_changes_nothing(self):
        order, _ = self._initiate()
        payment_id = self.fake.pay(order.gateway_session_id)
        with self.assertRaises(PaymentEvidenceRejected):
            self._confirm(order, payment_id, signature=checkout_signature(order.gateway_session_id, payment_id, "wrong"))
        self.assertEqual(self._reload(order).status, "pending")

    def test_a_payment_for_another_razorpay_order_is_rejected(self):
        order, _ = self._initiate()
        other, _ = self._initiate(amount=Decimal("100.00"))
        payment_id = self.fake.pay(other.gateway_session_id)
        with self.assertRaises(PaymentEvidenceRejected):
            self._confirm(order, payment_id, rz_order_id=other.gateway_session_id)
        self.assertEqual(self._reload(order).status, "pending")

    def test_a_smaller_captured_amount_is_rejected(self):
        order, _ = self._initiate()
        payment_id = self.fake.pay(order.gateway_session_id, amount=100)  # ₹1, not ₹1,250.50
        with self.assertRaises(PaymentEvidenceRejected):
            self._confirm(order, payment_id)
        self.assertIsNone(self._reload(order).payment)

    def test_an_authorized_but_uncaptured_payment_is_not_money_yet(self):
        order, _ = self._initiate()
        payment_id = self.fake.pay(order.gateway_session_id, status="authorized")
        self._confirm(order, payment_id)
        order = self._reload(order)
        self.assertEqual(order.status, "pending")
        self.assertIsNone(order.payment)

    # --- the webhook ---

    def test_webhook_settles_when_the_browser_never_came_back(self):
        order, _ = self._initiate()
        self.fake.pay(order.gateway_session_id)
        response = self._webhook(order)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._reload(order).status, "success")

    def test_razorpay_down_during_confirmation_then_webhook_settles(self):
        order, _ = self._initiate()
        payment_id = self.fake.pay(order.gateway_session_id)
        self.fake.down = True
        self._confirm(order, payment_id)
        self.assertEqual(self._reload(order).status, "pending")
        self.fake.down = False
        self._webhook(order)
        self.assertEqual(self._reload(order).status, "success")

    def test_webhook_is_retried_when_razorpay_cannot_be_asked(self):
        order, _ = self._initiate()
        self.fake.pay(order.gateway_session_id)
        self.fake.down = True
        self.assertEqual(self._webhook(order).status_code, 503)
        self.assertEqual(self._reload(order).status, "pending")

    def test_duplicate_webhooks_and_confirmation_settle_exactly_once(self):
        order, _ = self._initiate()
        payment_id = self.fake.pay(order.gateway_session_id)
        self._webhook(order)
        self._webhook(order, event="order.paid")
        result = self._confirm(order, payment_id)
        self.assertEqual(result["status"], "already_completed")
        with tenant_context(self.school):
            self.assertEqual(OnlinePaymentOrder.objects.filter(payment__isnull=False).count(), 1)
            from .models import Payment

            self.assertEqual(Payment.objects.count(), 1)

    def test_a_badly_signed_webhook_is_refused(self):
        order, _ = self._initiate()
        self.fake.pay(order.gateway_session_id)
        self.assertEqual(self._webhook(order, secret="not-the-secret").status_code, 400)
        self.assertEqual(self._reload(order).status, "pending")

    def test_another_schools_webhook_secret_is_refused(self):
        order, _ = self._initiate()
        self.fake.pay(order.gateway_session_id)
        # Same body, but signed with a secret this school does not have.
        response = self._webhook(order, secret="school-two-webhook-secret")
        self.assertEqual(response.status_code, 400)

    def test_other_events_are_acknowledged_and_ignored(self):
        order, _ = self._initiate()
        response = self._webhook(order, event="payment.failed")
        self.assertEqual(response.json()["status"], "ignored")
        self.assertEqual(self._reload(order).status, "pending")

    # --- reconciliation ---

    def test_reconciliation_settles_a_captured_payment(self):
        order, _ = self._initiate()
        self.fake.pay(order.gateway_session_id)
        with tenant_context(self.school):
            result = reconcile_online_payment_order(order)
        self.assertEqual(result["status"], "success")

    def test_reconciliation_leaves_an_unpaid_open_order_alone(self):
        order, _ = self._initiate()
        with tenant_context(self.school):
            result = reconcile_online_payment_order(order)
        self.assertEqual(result["status"], "pending")


class GatewaySettingsApiTests(FeesFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("fees.razorpay.api_request", FakeRazorpay())
        patcher.start()
        self.addCleanup(patcher.stop)

    def _save(self, client, **body):
        data = {"merchant_code": KEY_ID, "secret": SECRET, "webhook_secret": WEBHOOK_SECRET,
                "mode": "test", "is_active": True, **body}
        return client.put("/api/fees/gateways/razorpay/", data, format="json", HTTP_HOST=self.DOMAIN)

    def test_owner_saves_keys_and_secrets_never_come_back(self):
        client = self._client_as(self.owner_user)
        response = self._save(client)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["has_secret"])
        self.assertTrue(response.data["has_webhook_secret"])
        listing = client.get("/api/fees/gateways/", HTTP_HOST=self.DOMAIN)
        text = json.dumps(listing.data)
        self.assertNotIn(SECRET, text)
        self.assertNotIn(WEBHOOK_SECRET, text)
        razorpay = next(g for g in listing.data if g["gateway"] == "razorpay")
        self.assertTrue(razorpay["webhook_url"].endswith(WEBHOOK_URL))
        with tenant_context(self.school):
            config = TenantPaymentGatewayConfig.objects.get(gateway="razorpay")
            self.assertEqual(config.get_secret(), SECRET)
            self.assertNotEqual(config.encrypted_secret, SECRET)  # stored encrypted

    def test_a_blank_secret_keeps_the_saved_one(self):
        client = self._client_as(self.owner_user)
        self._save(client)
        self.assertEqual(self._save(client, secret="", webhook_secret="", is_active=False).status_code, 200)
        with tenant_context(self.school):
            config = TenantPaymentGatewayConfig.objects.get(gateway="razorpay")
            self.assertEqual(config.get_secret(), SECRET)
            self.assertFalse(config.is_active)

    def test_key_and_mode_must_agree(self):
        client = self._client_as(self.owner_user)
        self.assertEqual(self._save(client, mode="live").status_code, 400)
        self.assertEqual(self._save(client, merchant_code="not_a_key").status_code, 400)

    def test_connection_check_uses_the_gateway(self):
        client = self._client_as(self.owner_user)
        self._save(client)
        ok = client.post("/api/fees/gateways/razorpay/test/", HTTP_HOST=self.DOMAIN)
        self.assertTrue(ok.data["ok"])
        self._save(client, secret="wrong-secret")
        bad = client.post("/api/fees/gateways/razorpay/test/", HTTP_HOST=self.DOMAIN)
        self.assertFalse(bad.data["ok"])

    def test_needs_the_permission(self):
        client = self._client_as(self.random_staff_user)
        self.assertEqual(client.get("/api/fees/gateways/", HTTP_HOST=self.DOMAIN).status_code, 403)
        self.assertEqual(self._save(client).status_code, 403)

    def test_the_platform_esewa_fallback_is_not_offered_to_payers(self):
        parent = self._client_as(self.parent1_user)
        with self.settings(FEES_ALLOW_GLOBAL_GATEWAY_FALLBACK=True, ESEWA_CLIENT_SECRET="platform-secret"):
            self.assertEqual(parent.get("/api/fees/online/gateways/", HTTP_HOST=self.DOMAIN).data, [])

    def test_payers_see_only_enabled_gateways(self):
        owner = self._client_as(self.owner_user)
        parent = self._client_as(self.parent1_user)
        with self.settings(FEES_ALLOW_GLOBAL_GATEWAY_FALLBACK=False):
            self.assertEqual(parent.get("/api/fees/online/gateways/", HTTP_HOST=self.DOMAIN).data, [])
            self._save(owner)
            names = [g["gateway"] for g in parent.get("/api/fees/online/gateways/", HTTP_HOST=self.DOMAIN).data]
            self.assertEqual(names, ["razorpay"])
            self._save(owner, secret="", is_active=False)
            self.assertEqual(parent.get("/api/fees/online/gateways/", HTTP_HOST=self.DOMAIN).data, [])
