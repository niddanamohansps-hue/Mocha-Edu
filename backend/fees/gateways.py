"""
Payment Gateway Adapters for EduSekai Tenant Fees.

Provides decoupled, multi-merchant payment gateway integration.
Supports tenant-specific credentials with controlled global environment fallback,
compatible with the eSewa v2 EPAY protocol and extensible to Khalti.
"""

import base64
from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import hmac
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    """Base error for payment gateway operations."""


class PaymentConfigurationError(PaymentGatewayError):
    """Raised when payment gateway credentials or settings are missing or invalid."""


class GatewaySignatureVerificationError(PaymentGatewayError):
    """Raised when gateway HMAC signature verification fails or payload is tampered."""


@dataclass
class GatewayInitiationPayload:
    gateway: str
    gateway_url: str
    method: str
    form_parameters: Dict[str, str]
    order_id: str
    gateway_order_id: str


@dataclass
class GatewayVerificationResult:
    """Outcome of verifying a browser callback (evidence tier T1).

    ``is_valid`` means the callback is authentic and matches the order (HMAC over the required
    fields, merchant, transaction id and amount all verified). It says nothing about the payment
    outcome: read ``gateway_status`` for that. ``raw_data`` only ever holds the whitelisted,
    verified fields, never the caller's original payload. ``reason_code`` explains a rejection
    (for logs; it is never shown to the public).
    """

    is_valid: bool
    gateway_reference: str = ""
    verified_amount: Decimal = Decimal("0")
    raw_data: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    gateway_status: str = ""
    reason_code: str = ""


@dataclass
class GatewayStatusResult:
    """Outcome of a server-to-server status query (evidence tier T2), built only by an adapter.

    Statuses: COMPLETE, PENDING, AMBIGUOUS, NOT_FOUND, CANCELED, FULL_REFUND, PARTIAL_REFUND
    (the names eSewa documents; their exact meaning could not be confirmed against the official
    contract) plus ERROR (the query itself failed, which says nothing about the payment),
    INVALID (a response that does not match the order) and UNKNOWN (an unrecognized status).
    For COMPLETE the identity fields were checked against the order by the adapter.
    """

    status: str
    gateway_reference: str = ""
    verified_amount: Optional[Decimal] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    evidence: str = "status_api"
    transaction_uuid: str = ""
    product_code: str = ""
    total_amount: Optional[Decimal] = None
    reason_code: str = ""


def get_gateway_credentials(gateway: str = "esewa") -> Dict[str, Any]:
    """
    Resolves gateway credentials for the active tenant schema.

    Precedence:
    1. Active TenantPaymentGatewayConfig for the tenant.
    2. Inactive TenantPaymentGatewayConfig with allow_global_fallback=False fails closed.
    3. Global settings (settings.ESEWA_*) if settings.FEES_ALLOW_GLOBAL_GATEWAY_FALLBACK is True.
    """
    from .models import TenantPaymentGatewayConfig

    tenant_config = TenantPaymentGatewayConfig.objects.filter(gateway=gateway, is_active=True).first()
    if tenant_config:
        secret = tenant_config.get_secret()
        if not secret:
            raise PaymentConfigurationError(f"Tenant gateway secret for '{gateway}' is empty.")
        return {
            "merchant_code": tenant_config.merchant_code,
            "secret_key": secret,
            "is_tenant_custom": True,
        }

    # If an inactive tenant config exists with allow_global_fallback=False, fail closed
    inactive_config = TenantPaymentGatewayConfig.objects.filter(gateway=gateway, is_active=False).first()
    if inactive_config and not inactive_config.allow_global_fallback:
        raise PaymentConfigurationError(f"Payment gateway '{gateway}' is disabled for this tenant.")

    allow_global = getattr(settings, "FEES_ALLOW_GLOBAL_GATEWAY_FALLBACK", True)
    if not allow_global:
        raise PaymentConfigurationError(
            f"No active tenant payment gateway configuration found for '{gateway}' and global fallback is disabled."
        )

    if gateway == "esewa":
        secret = getattr(settings, "ESEWA_CLIENT_SECRET", None)
        if not secret:
            raise PaymentConfigurationError("eSewa payment secret is not configured in settings.")
        merchant_code = getattr(settings, "ESEWA_PRODUCT_CODE", "EPAYTEST")
        return {
            "merchant_code": merchant_code,
            "secret_key": secret,
            "is_tenant_custom": False,
        }

    raise PaymentConfigurationError(f"Unsupported payment gateway: '{gateway}'")


# --- Transport and evidence helpers --------------------------------------------------------

# Statuses eSewa documents besides COMPLETE. Their precise meaning could not be confirmed against
# the official contract, so none of them is treated as proof that a payment failed.
NON_COMPLETE_GATEWAY_STATUSES = frozenset(
    {"PENDING", "AMBIGUOUS", "NOT_FOUND", "CANCELED", "FULL_REFUND", "PARTIAL_REFUND"}
)
# A browser callback must be signed over at least these fields (they carry the payment's identity,
# amount and outcome). Provisional: the exact signed-field list is part of the eSewa contract we
# could not read in full; the existing valid callbacks sign all five.
REQUIRED_SIGNED_FIELDS = frozenset(
    {"status", "total_amount", "transaction_uuid", "product_code", "transaction_code"}
)
MAX_CALLBACK_CHARS = 8192  # encoded callback data; real ones are a few hundred bytes
MAX_STATUS_RESPONSE_BYTES = 65536
STATUS_TIMEOUT_SECONDS = 10
_TEST_HOST_LABELS = frozenset({"rc", "rc-epay", "uat", "uat-epay", "test", "dev", "sandbox"})
_TEST_MERCHANT_CODES = frozenset({"EPAYTEST"})


def is_production_environment():
    """True when payment safety checks must be strict.

    ``DEBUG`` alone is not enough: Django's test runner forces ``DEBUG=False``, and the project's
    test flag (``EDUSEKAI_ALLOW_DERIVED_TEST_DB``, true only under ``manage.py test``) identifies
    that case. Tests that exercise the production rules override both settings.
    """
    return not getattr(settings, "DEBUG", False) and not getattr(
        settings, "EDUSEKAI_ALLOW_DERIVED_TEST_DB", False
    )


def ensure_gateway_config_is_production_safe(*, merchant_code, urls):
    """Refuse to run against eSewa's test merchant or test hosts in production.

    A deployment that forgot to configure ESEWA_PRODUCT_CODE / ESEWA_URL / ESEWA_STATUS_URL would
    otherwise silently use the built-in test defaults. Raises ``PaymentConfigurationError``.
    """
    if not is_production_environment():
        return
    if str(merchant_code or "").upper() in _TEST_MERCHANT_CODES:
        raise PaymentConfigurationError("The payment gateway is using a test merchant code.")
    for url in urls:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        if host.split(".")[0] in _TEST_HOST_LABELS:
            raise PaymentConfigurationError("The payment gateway is configured with a test endpoint.")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: a 3xx from the status host surfaces as an HTTPError instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def _validated_status_url():
    """The configured eSewa status URL, if it is safe to call; otherwise PaymentConfigurationError."""
    url = str(getattr(settings, "ESEWA_STATUS_URL", "") or "")
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    production = is_production_environment()
    if parsed.username or parsed.password or not host:
        raise PaymentConfigurationError("The eSewa status URL is invalid.")
    if parsed.scheme != "https" and (production or parsed.scheme != "http"):
        raise PaymentConfigurationError("The eSewa status URL must use https.")
    on_esewa = host == "esewa.com.np" or host.endswith(".esewa.com.np")
    local_dev = (not production) and host in ("localhost", "127.0.0.1")
    if not (on_esewa or local_dev):
        raise PaymentConfigurationError("The eSewa status URL points at an unexpected host.")
    ensure_gateway_config_is_production_safe(merchant_code="", urls=[url])
    return url


def _fetch_status_json(url):
    """GET ``url`` (no redirects, bounded size) and return the decoded JSON. Raises on any problem."""
    request = urllib.request.Request(url, headers={"User-Agent": "EduSekai/1.0", "Accept": "application/json"})
    with _OPENER.open(request, timeout=STATUS_TIMEOUT_SECONDS) as response:
        body = response.read(MAX_STATUS_RESPONSE_BYTES + 1)
    if len(body) > MAX_STATUS_RESPONSE_BYTES:
        raise ValueError("status response too large")
    return json.loads(body.decode("utf-8"))


def _parse_amount(value):
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except Exception:  # noqa: BLE001 - InvalidOperation, TypeError, ...
        return None
    return amount if amount.is_finite() else None


def _decode_callback(raw_payload):
    """The callback as a dict, or None. Strict, size-bounded; never raises."""
    try:
        if isinstance(raw_payload, dict):
            for key in ("data", "encoded_data"):
                if key in raw_payload:
                    raw_payload = raw_payload[key]
                    break
            else:
                if len(json.dumps(raw_payload, default=str)) > MAX_CALLBACK_CHARS:
                    return None
                return raw_payload
        if not isinstance(raw_payload, str) or not raw_payload or len(raw_payload) > MAX_CALLBACK_CHARS:
            return None
        # A '+' in a query-string value arrives as a space; restore it, then decode strictly.
        encoded = raw_payload.replace(" ", "+")
        encoded += "=" * ((4 - len(encoded) % 4) % 4)
        decoded = json.loads(base64.b64decode(encoded, validate=True).decode("utf-8"))
    except Exception:  # noqa: BLE001 - any malformed input is simply "not valid evidence"
        return None
    return decoded if isinstance(decoded, dict) else None


_REJECTION_MESSAGES = {
    "configuration": "Gateway configuration is unusable.",
    "malformed": "Callback payload is missing, oversized or not valid.",
    "unsigned": "Callback has no signature or signed_field_names.",
    "required_fields_not_signed": "Callback does not sign all required fields.",
    "signature": "eSewa HMAC-SHA256 signature verification failed.",
    "transaction_mismatch": "Transaction UUID does not match the order.",
    "merchant_mismatch": "Merchant product code does not match.",
    "amount_mismatch": "Amount does not match the order.",
}


def _rejected(reason_code):
    """A rejection that carries nothing from the caller's payload.

    ``error_message`` is for logs and tests only; services never return it to a caller.
    """
    return GatewayVerificationResult(
        is_valid=False,
        error_message=_REJECTION_MESSAGES.get(reason_code, "Gateway callback could not be verified."),
        reason_code=reason_code,
    )


class BasePaymentGatewayAdapter:
    """Abstract base class for payment gateway adapters."""

    def initiate_payment(self, order, return_url: str, failure_url: str) -> GatewayInitiationPayload:
        raise NotImplementedError

    def verify_callback(self, order, raw_payload: Any) -> GatewayVerificationResult:
        raise NotImplementedError

    def query_status(self, order) -> GatewayStatusResult:
        raise NotImplementedError


class EsewaGatewayAdapter(BasePaymentGatewayAdapter):
    """
    eSewa v2 EPAY Gateway Adapter.
    Implements SHA-256 HMAC signature generation, form parameter assembly,
    Base64 callback verification with signed_field_names, and transaction status lookup.
    """

    @staticmethod
    def generate_signature(secret_key: str, message: str) -> str:
        if not secret_key:
            raise PaymentConfigurationError("Secret key is required to generate eSewa signature.")
        secret = bytes(secret_key, "utf-8")
        msg_bytes = bytes(message, "utf-8")
        hash_object = hmac.new(secret, msg_bytes, hashlib.sha256)
        return base64.b64encode(hash_object.digest()).decode("utf-8")

    def initiate_payment(self, order, return_url: str, failure_url: str) -> GatewayInitiationPayload:
        creds = get_gateway_credentials("esewa")
        merchant_code = creds["merchant_code"]
        secret_key = creds["secret_key"]

        # eSewa requires plain decimal with at most 2 decimal places
        amount_str = f"{order.amount:.2f}"
        gateway_url = getattr(settings, "ESEWA_URL", "https://rc-epay.esewa.com.np/api/epay/main/v2/form")
        ensure_gateway_config_is_production_safe(merchant_code=merchant_code, urls=[gateway_url])

        # eSewa v2 signature format: total_amount,transaction_uuid,product_code
        message = f"total_amount={amount_str},transaction_uuid={order.gateway_order_id},product_code={merchant_code}"
        signature = self.generate_signature(secret_key, message)

        params = {
            "amount": amount_str,
            "tax_amount": "0",
            "total_amount": amount_str,
            "transaction_uuid": order.gateway_order_id,
            "product_code": merchant_code,
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "success_url": return_url,
            "failure_url": failure_url,
            "signed_field_names": "total_amount,transaction_uuid,product_code",
            "signature": signature,
        }

        return GatewayInitiationPayload(
            gateway="esewa",
            gateway_url=gateway_url,
            method="POST",
            form_parameters=params,
            order_id=str(order.id),
            gateway_order_id=order.gateway_order_id,
        )

    def verify_callback(self, order, raw_payload: Any) -> GatewayVerificationResult:
        """
        Verifies the browser callback (evidence tier T1) without trusting any of it:
        size-bounded strict decoding, an HMAC-SHA256 signature over the fields the payload names,
        a requirement that those fields include the ones that carry the payment's identity and
        outcome, and then merchant, transaction id and amount checks against the stored order.
        Anything that fails is rejected and nothing from the payload is carried back. A valid
        callback with a status other than COMPLETE is authentic but is not a payment, and is
        returned with ``gateway_status`` so the caller can leave the order alone.
        """
        try:
            creds = get_gateway_credentials("esewa")
            merchant_code = creds["merchant_code"]
            secret_key = creds["secret_key"]
            ensure_gateway_config_is_production_safe(merchant_code=merchant_code, urls=[])
        except PaymentConfigurationError as exc:
            logger.error("eSewa callback cannot be verified for order %s: %s", order.gateway_order_id, exc)
            return _rejected("configuration")

        decoded = _decode_callback(raw_payload)
        if decoded is None:
            return _rejected("malformed")

        signed_field_names = decoded.get("signed_field_names")
        provided_signature = decoded.get("signature")
        if not isinstance(signed_field_names, str) or not isinstance(provided_signature, str):
            return _rejected("unsigned")

        fields = [f.strip() for f in signed_field_names.split(",") if f.strip()]
        if not REQUIRED_SIGNED_FIELDS.issubset(fields) or any(f not in decoded for f in fields):
            return _rejected("required_fields_not_signed")

        message = ",".join(f"{field}={decoded.get(field)}" for field in fields)
        expected_signature = self.generate_signature(secret_key, message)
        if not hmac.compare_digest(expected_signature, provided_signature):
            return _rejected("signature")

        if decoded.get("transaction_uuid") != order.gateway_order_id:
            return _rejected("transaction_mismatch")
        if decoded.get("product_code") != merchant_code:
            return _rejected("merchant_mismatch")
        payload_amount = _parse_amount(decoded.get("total_amount"))
        if payload_amount is None or payload_amount != order.amount:
            return _rejected("amount_mismatch")

        return GatewayVerificationResult(
            is_valid=True,
            gateway_reference=str(decoded.get("transaction_code") or "")[:100],
            verified_amount=payload_amount,
            raw_data={
                key: str(decoded[key])[:100]
                for key in ("status", "transaction_code", "total_amount", "transaction_uuid", "product_code")
                if decoded.get(key) is not None
            },
            gateway_status=str(decoded.get("status") or "")[:30],
        )

    def query_status(self, order) -> GatewayStatusResult:
        """
        Asks eSewa for the status of ``order`` (evidence tier T2).

        Safety rules: the status URL must pass ``_validated_status_url`` (https and an esewa.com.np
        host in production, no redirects ever followed); the response is size-bounded; and its
        transaction id, product code and amount must match the stored order. A network or parse
        failure is reported as ERROR, which says nothing about the payment. The response is not
        assumed to be signed (the documentation we could read shows none), so a COMPLETE is only
        believed when every identity field is present and equal to the order's.
        """
        try:
            creds = get_gateway_credentials("esewa")
            merchant_code = creds["merchant_code"]
            ensure_gateway_config_is_production_safe(merchant_code=merchant_code, urls=[])
            status_base_url = _validated_status_url()
        except PaymentConfigurationError as exc:
            logger.error("eSewa status check not possible for order %s: %s", order.gateway_order_id, exc)
            return GatewayStatusResult(status="ERROR", reason_code="configuration")

        query_params = urllib.parse.urlencode({
            "product_code": merchant_code,
            "total_amount": f"{order.amount:.2f}",
            "transaction_uuid": order.gateway_order_id,
        })
        try:
            data = _fetch_status_json(f"{status_base_url}?{query_params}")
        except Exception as exc:  # noqa: BLE001 - any transport/parse failure is "could not ask", not "not paid"
            logger.warning(
                "eSewa status check failed for order %s: %s", order.gateway_order_id, type(exc).__name__
            )
            return GatewayStatusResult(status="ERROR", reason_code="transport")

        if not isinstance(data, dict):
            return GatewayStatusResult(status="ERROR", reason_code="malformed")

        # Identity fields, when present, must belong to this order.
        response_uuid = data.get("transaction_uuid")
        response_code = data.get("product_code")
        response_amount = _parse_amount(data.get("total_amount")) if data.get("total_amount") is not None else None
        mismatch = (
            (response_uuid is not None and response_uuid != order.gateway_order_id)
            or (response_code is not None and response_code != merchant_code)
            or (data.get("total_amount") is not None and response_amount != order.amount)
        )
        if mismatch:
            logger.warning("eSewa status response does not match order %s.", order.gateway_order_id)
            return GatewayStatusResult(status="INVALID", reason_code="identity_mismatch")

        raw_status = data.get("status")
        kept = {
            key: str(data[key])[:100]
            for key in ("status", "ref_id", "transaction_code", "total_amount", "transaction_uuid", "product_code")
            if data.get(key) is not None
        }
        if raw_status == "COMPLETE":
            if response_uuid is None or response_code is None or response_amount is None:
                return GatewayStatusResult(status="INVALID", reason_code="incomplete_identity")
            return GatewayStatusResult(
                status="COMPLETE",
                gateway_reference=str(data.get("ref_id") or data.get("transaction_code") or "")[:100],
                verified_amount=response_amount,
                raw_data=kept,
                transaction_uuid=response_uuid,
                product_code=response_code,
                total_amount=response_amount,
            )
        if raw_status in NON_COMPLETE_GATEWAY_STATUSES:
            return GatewayStatusResult(status=raw_status, raw_data=kept)
        return GatewayStatusResult(status="UNKNOWN", reason_code="unknown_status")


class MockGatewayAdapter(BasePaymentGatewayAdapter):
    """
    Mock gateway adapter for testing and offline environments.
    """

    def __init__(self, should_succeed: bool = True, ref_id: str = "MOCK-TX-12345"):
        self.should_succeed = should_succeed
        self.ref_id = ref_id

    def initiate_payment(self, order, return_url: str, failure_url: str) -> GatewayInitiationPayload:
        return GatewayInitiationPayload(
            gateway="mock",
            gateway_url="https://mock-gateway.localhost/pay",
            method="POST",
            form_parameters={
                "order_id": str(order.id),
                "gateway_order_id": order.gateway_order_id,
                "amount": str(order.amount),
                "return_url": return_url,
                "failure_url": failure_url,
            },
            order_id=str(order.id),
            gateway_order_id=order.gateway_order_id,
        )

    def verify_callback(self, order, raw_payload: Any) -> GatewayVerificationResult:
        if not self.should_succeed:
            return GatewayVerificationResult(
                is_valid=False,
                error_message="Mock gateway simulated transaction failure.",
                reason_code="mock_failure",
            )
        return GatewayVerificationResult(
            is_valid=True,
            gateway_reference=self.ref_id,
            verified_amount=order.amount,
            raw_data={"status": "COMPLETE", "ref_id": self.ref_id, "total_amount": str(order.amount)},
            gateway_status="COMPLETE",
        )

    def query_status(self, order) -> GatewayStatusResult:
        if not self.should_succeed:
            return GatewayStatusResult(status="FAILED", error_message="Mock failed")
        return GatewayStatusResult(
            status="COMPLETE",
            gateway_reference=self.ref_id,
            verified_amount=order.amount,
            raw_data={"status": "COMPLETE"},
            transaction_uuid=order.gateway_order_id,
            total_amount=order.amount,
        )


_ADAPTER_REGISTRY = {
    "esewa": EsewaGatewayAdapter,
    "mock": MockGatewayAdapter,
}


def get_gateway_adapter(gateway: str = "esewa", **kwargs) -> BasePaymentGatewayAdapter:
    adapter_cls = _ADAPTER_REGISTRY.get(gateway)
    if not adapter_cls:
        raise PaymentConfigurationError(f"No gateway adapter registered for '{gateway}'.")
    return adapter_cls(**kwargs)

