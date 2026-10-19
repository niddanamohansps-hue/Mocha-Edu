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
    is_valid: bool
    gateway_reference: str = ""
    verified_amount: Decimal = Decimal("0")
    raw_data: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


@dataclass
class GatewayStatusResult:
    status: str  # "COMPLETE", "PENDING", "FAILED", "NOT_FOUND", "ERROR"
    gateway_reference: str = ""
    verified_amount: Optional[Decimal] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


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
        creds = get_gateway_credentials("esewa")
        merchant_code = creds["merchant_code"]
        secret_key = creds["secret_key"]

        # Parse raw payload: can be dict, base64 string, or dict with 'data'/'encoded_data'
        decoded_json = None
        if isinstance(raw_payload, dict):
            if "data" in raw_payload:
                raw_payload = raw_payload["data"]
            elif "encoded_data" in raw_payload:
                raw_payload = raw_payload["encoded_data"]
            else:
                decoded_json = raw_payload

        if decoded_json is None:
            if not isinstance(raw_payload, str):
                return GatewayVerificationResult(
                    is_valid=False, error_message="Invalid callback payload format."
                )
            try:
                # Add padding if needed
                padded = raw_payload + "=" * ((4 - len(raw_payload) % 4) % 4)
                decoded_bytes = base64.b64decode(padded)
                decoded_json = json.loads(decoded_bytes.decode("utf-8"))
            except Exception as exc:
                return GatewayVerificationResult(
                    is_valid=False, error_message=f"Failed to decode Base64 gateway data: {exc}"
                )

        if not isinstance(decoded_json, dict):
            return GatewayVerificationResult(
                is_valid=False, error_message="Decoded gateway payload is not a valid JSON object."
            )

        # 1. Status check
        status = decoded_json.get("status")
        if status != "COMPLETE":
            return GatewayVerificationResult(
                is_valid=False,
                raw_data=decoded_json,
                error_message=f"eSewa payment not complete (status='{status}').",
            )

        # 2. Transaction UUID check
        tx_uuid = decoded_json.get("transaction_uuid")
        if tx_uuid != order.gateway_order_id:
            return GatewayVerificationResult(
                is_valid=False,
                raw_data=decoded_json,
                error_message=f"Transaction UUID mismatch: expected '{order.gateway_order_id}', got '{tx_uuid}'.",
            )

        # 3. Product code check
        product_code = decoded_json.get("product_code")
        if product_code != merchant_code:
            return GatewayVerificationResult(
                is_valid=False,
                raw_data=decoded_json,
                error_message=f"Merchant product code mismatch: expected '{merchant_code}', got '{product_code}'.",
            )

        # 4. Amount check
        try:
            total_amount_str = str(decoded_json.get("total_amount", "0")).replace(",", "")
            payload_amount = Decimal(total_amount_str)
        except Exception:
            return GatewayVerificationResult(
                is_valid=False,
                raw_data=decoded_json,
                error_message="Invalid total_amount format in gateway payload.",
            )

        if payload_amount != order.amount:
            return GatewayVerificationResult(
                is_valid=False,
                raw_data=decoded_json,
                error_message=f"Amount mismatch: order requires {order.amount}, gateway returned {payload_amount}.",
            )

        # 5. HMAC-SHA256 Signature verification
        signed_field_names = decoded_json.get("signed_field_names")
        provided_signature = decoded_json.get("signature")
        if not signed_field_names or not provided_signature:
            return GatewayVerificationResult(
                is_valid=False,
                raw_data=decoded_json,
                error_message="Missing signature or signed_field_names in gateway payload.",
            )

        fields = [f.strip() for f in signed_field_names.split(",") if f.strip()]
        try:
            message = ",".join(f"{field}={decoded_json.get(field, '')}" for field in fields)
        except Exception as exc:
            return GatewayVerificationResult(
                is_valid=False,
                raw_data=decoded_json,
                error_message=f"Could not reconstruct signed message: {exc}",
            )

        expected_signature = self.generate_signature(secret_key, message)
        if not hmac.compare_digest(expected_signature, provided_signature):
            return GatewayVerificationResult(
                is_valid=False,
                raw_data=decoded_json,
                error_message="eSewa HMAC-SHA256 signature verification failed.",
            )

        gateway_reference = decoded_json.get("transaction_code") or decoded_json.get("ref_id") or ""
        return GatewayVerificationResult(
            is_valid=True,
            gateway_reference=gateway_reference,
            verified_amount=payload_amount,
            raw_data=decoded_json,
        )

    def query_status(self, order) -> GatewayStatusResult:
        creds = get_gateway_credentials("esewa")
        merchant_code = creds["merchant_code"]
        amount_str = f"{order.amount:.2f}"

        status_base_url = getattr(
            settings, "ESEWA_STATUS_URL", "https://rc.esewa.com.np/api/epay/transaction/status/"
        )
        query_params = urllib.parse.urlencode({
            "product_code": merchant_code,
            "total_amount": amount_str,
            "transaction_uuid": order.gateway_order_id,
        })
        url = f"{status_base_url}?{query_params}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EduSekai/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body)
        except Exception as exc:
            logger.warning("eSewa status check failed for order %s: %s", order.gateway_order_id, exc)
            return GatewayStatusResult(
                status="ERROR",
                error_message=f"Network inquiry error: {exc}",
            )

        raw_status = data.get("status")
        if raw_status == "COMPLETE":
            ref_id = data.get("ref_id") or data.get("transaction_code") or ""
            return GatewayStatusResult(
                status="COMPLETE",
                gateway_reference=ref_id,
                verified_amount=order.amount,
                raw_data=data,
            )
        elif raw_status in ("PENDING", "NOT_FOUND", "FAILED"):
            return GatewayStatusResult(
                status=raw_status,
                raw_data=data,
            )
        return GatewayStatusResult(
            status="UNKNOWN",
            raw_data=data,
            error_message=f"Unknown gateway status '{raw_status}'",
        )


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
            )
        return GatewayVerificationResult(
            is_valid=True,
            gateway_reference=self.ref_id,
            verified_amount=order.amount,
            raw_data={"status": "COMPLETE", "ref_id": self.ref_id, "amount": str(order.amount)},
        )

    def query_status(self, order) -> GatewayStatusResult:
        if not self.should_succeed:
            return GatewayStatusResult(status="FAILED", error_message="Mock failed")
        return GatewayStatusResult(
            status="COMPLETE",
            gateway_reference=self.ref_id,
            verified_amount=order.amount,
            raw_data={"status": "COMPLETE"},
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

