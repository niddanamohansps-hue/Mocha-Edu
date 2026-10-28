"""
Razorpay (India: UPI, cards, netbanking, wallets) for online fee payments.

Flow:
1. ``initiate_payment`` creates a Razorpay order for the amount in paise and returns what the browser's
   Razorpay Checkout needs. The Razorpay order id is stored on our order (``gateway_session_id``).
2. When the parent pays, Checkout hands the browser ``razorpay_order_id``, ``razorpay_payment_id`` and
   ``razorpay_signature``. ``verify_callback`` checks the signature (HMAC-SHA256 of
   "order_id|payment_id" with the key secret) and then asks Razorpay for the payment itself: only a
   captured payment of exactly this amount, in INR, for this order counts as COMPLETE.
3. Razorpay also sends a signed webhook (``payment.captured`` / ``order.paid``) to the school's domain.
   ``verify_webhook`` checks it (HMAC-SHA256 of the raw body with the webhook secret); the view then
   reconciles the order through ``query_status``, so a webhook only ever triggers a server-side check.
4. ``query_status`` lists the payments of the Razorpay order (used by the webhook and by the periodic
   reconciliation): a captured payment of the exact amount settles the order.

All calls go to https://api.razorpay.com only, without following redirects, with bounded sizes.
"""
import base64
import hashlib
import hmac
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.conf import settings

from .gateways import (
    BasePaymentGatewayAdapter,
    GatewayInitiationPayload,
    GatewayStatusResult,
    GatewayVerificationResult,
    PaymentConfigurationError,
    PaymentGatewayError,
    _OPENER,
    _rejected,
    get_gateway_credentials,
)

logger = logging.getLogger(__name__)

API_HOST = "api.razorpay.com"
TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 262144
MAX_WEBHOOK_BYTES = 65536
CURRENCY = "INR"


def to_paise(amount) -> int:
    """₹1,250.50 -> 125050. Razorpay amounts are integers in the smallest unit."""
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _api_base():
    base = str(getattr(settings, "RAZORPAY_API_BASE", f"https://{API_HOST}/v1")).rstrip("/")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "https" or parsed.hostname != API_HOST:
        raise PaymentConfigurationError("The Razorpay API address must be https://api.razorpay.com.")
    return base


def key_mode(key_id: str) -> str:
    """'test' for rzp_test_..., 'live' for rzp_live_..., '' for anything else."""
    key_id = str(key_id or "")
    if key_id.startswith("rzp_test_"):
        return "test"
    if key_id.startswith("rzp_live_"):
        return "live"
    return ""


def _credentials():
    creds = get_gateway_credentials("razorpay")
    if not key_mode(creds["merchant_code"]):
        raise PaymentConfigurationError("The Razorpay key id must start with rzp_test_ or rzp_live_.")
    return creds


def api_request(method, path, *, key_id, key_secret, body=None, query=None):
    """One call to the Razorpay API. Returns the decoded JSON; raises PaymentGatewayError on failure."""
    url = f"{_api_base()}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    token = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "EduSekai/1.0"},
    )
    try:
        with _OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise PaymentGatewayError(f"Razorpay answered {exc.code}") from None
    except Exception as exc:  # noqa: BLE001 - network failure: "could not ask", never "not paid"
        raise PaymentGatewayError(f"Razorpay could not be reached ({type(exc).__name__})") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise PaymentGatewayError("Razorpay response too large")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        raise PaymentGatewayError("Razorpay response was not JSON") from None


def check_keys(key_id, key_secret):
    """True when Razorpay accepts the keys (a harmless read: the latest order, if any)."""
    try:
        api_request("GET", "/orders", key_id=key_id, key_secret=key_secret, query={"count": 1})
    except PaymentGatewayError:
        return False
    return True


def _hmac_hex(secret, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class RazorpayGatewayAdapter(BasePaymentGatewayAdapter):
    def initiate_payment(self, order, return_url: str, failure_url: str) -> GatewayInitiationPayload:
        creds = _credentials()
        rz_order = api_request(
            "POST", "/orders", key_id=creds["merchant_code"], key_secret=creds["secret_key"],
            body={
                "amount": to_paise(order.amount),
                "currency": CURRENCY,
                "receipt": order.gateway_order_id[:40],
                "notes": {"edusekai_order": str(order.id)},
            },
        )
        rz_order_id = str(rz_order.get("id") or "") if isinstance(rz_order, dict) else ""
        if not rz_order_id.startswith("order_") or rz_order.get("amount") != to_paise(order.amount):
            raise PaymentGatewayError("Razorpay did not create a matching order.")
        order.gateway_session_id = rz_order_id
        order.save(update_fields=["gateway_session_id", "updated_at"])
        name, email, phone = _payer_contact(order)
        return GatewayInitiationPayload(
            gateway="razorpay",
            gateway_url="",
            method="CHECKOUT",  # opened in the page by Razorpay Checkout, not a redirect
            form_parameters={
                "key": creds["merchant_code"],
                "order_id": rz_order_id,
                "amount": str(to_paise(order.amount)),
                "currency": CURRENCY,
                "callback_url": return_url,
                # Shown in the payment window: whom the parent pays, and their details filled in.
                "school_name": _school_name(),
                "prefill_name": name,
                "prefill_email": email,
                "prefill_contact": phone,
            },
            order_id=str(order.id),
            gateway_order_id=order.gateway_order_id,
        )

    def verify_callback(self, order, raw_payload: Any) -> GatewayVerificationResult:
        try:
            creds = _credentials()
        except PaymentConfigurationError as exc:
            logger.error("Razorpay confirmation cannot be checked for order %s: %s", order.gateway_order_id, exc)
            return _rejected("configuration")
        if not isinstance(raw_payload, dict):
            return _rejected("malformed")
        rz_order_id = str(raw_payload.get("razorpay_order_id") or "")
        payment_id = str(raw_payload.get("razorpay_payment_id") or "")
        signature = str(raw_payload.get("razorpay_signature") or "")
        if not (rz_order_id and payment_id and signature) or max(map(len, (rz_order_id, payment_id, signature))) > 100:
            return _rejected("malformed")
        if not order.gateway_session_id or rz_order_id != order.gateway_session_id:
            return _rejected("transaction_mismatch")
        expected = _hmac_hex(creds["secret_key"], f"{rz_order_id}|{payment_id}".encode())
        if not hmac.compare_digest(expected, signature):
            return _rejected("signature")

        # The signature proves Razorpay issued this payment id for this order. Whether money was
        # captured, and how much, comes from Razorpay itself.
        try:
            payment = api_request("GET", f"/payments/{urllib.parse.quote(payment_id)}",
                                  key_id=creds["merchant_code"], key_secret=creds["secret_key"])
        except PaymentGatewayError as exc:
            logger.warning("Razorpay payment lookup failed for order %s: %s", order.gateway_order_id, exc)
            # Authentic but not yet confirmed: the order stays open for the webhook / reconciliation.
            return GatewayVerificationResult(is_valid=True, gateway_status="PENDING")
        return _verified_from_payment(order, payment, expected_payment_id=payment_id)

    def query_status(self, order) -> GatewayStatusResult:
        try:
            creds = _credentials()
        except PaymentConfigurationError as exc:
            logger.error("Razorpay status check not possible for order %s: %s", order.gateway_order_id, exc)
            return GatewayStatusResult(status="ERROR", reason_code="configuration")
        if not order.gateway_session_id:
            return GatewayStatusResult(status="NOT_FOUND", reason_code="no_gateway_order")
        try:
            data = api_request("GET", f"/orders/{urllib.parse.quote(order.gateway_session_id)}/payments",
                               key_id=creds["merchant_code"], key_secret=creds["secret_key"])
        except PaymentGatewayError as exc:
            logger.warning("Razorpay status check failed for order %s: %s", order.gateway_order_id, exc)
            return GatewayStatusResult(status="ERROR", reason_code="transport")
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return GatewayStatusResult(status="ERROR", reason_code="malformed")
        for payment in items:
            result = _verified_from_payment(order, payment)
            if result.is_valid and result.gateway_status == "COMPLETE":
                return GatewayStatusResult(
                    status="COMPLETE",
                    gateway_reference=result.gateway_reference,
                    verified_amount=order.amount,
                    raw_data=result.raw_data,
                    transaction_uuid=order.gateway_order_id,
                    total_amount=order.amount,
                )
        if any(isinstance(p, dict) and p.get("status") == "refunded" for p in items):
            return GatewayStatusResult(status="FULL_REFUND")
        # No payment yet, or only failed attempts (the parent may still try again).
        return GatewayStatusResult(status="NOT_FOUND" if not items else "PENDING")

    @staticmethod
    def verify_webhook(raw_body: bytes, signature: str):
        """The parsed event when the X-Razorpay-Signature matches this school's webhook secret, else None."""
        if not raw_body or len(raw_body) > MAX_WEBHOOK_BYTES or not signature or len(signature) > 200:
            return None
        try:
            creds = _credentials()
        except PaymentConfigurationError:
            return None
        if not creds.get("webhook_secret"):
            return None
        if not hmac.compare_digest(_hmac_hex(creds["webhook_secret"], raw_body), signature):
            return None
        try:
            event = json.loads(raw_body.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None
        return event if isinstance(event, dict) else None


def _school_name():
    from django.db import connection

    tenant = getattr(connection, "tenant", None)
    return str(getattr(tenant, "name", "") or "")[:80]


def _payer_contact(order):
    """Name, email and phone of whoever started the payment, for the Checkout form ("" when unknown)."""
    if not order.created_by_user_id:
        return "", "", ""
    from profiles.models import Profile

    profile = Profile.objects.filter(user_id=order.created_by_user_id).first()
    if profile is None:
        return "", "", ""
    name = f"{profile.first_name} {profile.last_name}".strip()
    email = profile.email or (order.created_by.email if order.created_by else "") or ""
    digits = re.sub(r"\D", "", profile.phone or "")
    phone = digits[-10:] if len(digits) >= 10 else ""
    return name[:80], str(email)[:120], phone


def _verified_from_payment(order, payment, expected_payment_id=None) -> GatewayVerificationResult:
    """A Razorpay payment entity checked against our order. COMPLETE only for a captured exact match."""
    if not isinstance(payment, dict):
        return _rejected("malformed")
    if expected_payment_id and payment.get("id") != expected_payment_id:
        return _rejected("transaction_mismatch")
    if payment.get("order_id") != order.gateway_session_id:
        return _rejected("transaction_mismatch")
    if payment.get("currency") != CURRENCY or payment.get("amount") != to_paise(order.amount):
        return _rejected("amount_mismatch")
    status = str(payment.get("status") or "")
    kept = {
        "status": status[:30],
        "transaction_code": str(payment.get("id") or "")[:100],
        "total_amount": str(order.amount),
        "transaction_uuid": order.gateway_order_id,
        "product_code": "razorpay",
    }
    return GatewayVerificationResult(
        is_valid=True,
        gateway_reference=str(payment.get("id") or "")[:100],
        verified_amount=order.amount,
        raw_data=kept,
        # "authorized" is not money yet (it can still be voided); only "captured" is.
        gateway_status="COMPLETE" if status == "captured" else status.upper()[:30],
    )
