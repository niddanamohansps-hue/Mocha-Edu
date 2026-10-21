import hashlib
import hmac
import base64
import re
from decimal import Decimal

from django.conf import settings

from fees.gateways import (
    PaymentConfigurationError as GatewayConfigurationError,
    REQUIRED_SIGNED_FIELDS,
    _decode_callback,
    _parse_amount,
    ensure_gateway_config_is_production_safe,
)

# Plain decimal, at most 2 places, matching Payment.amount (max_digits=10, decimal_places=2).
_AMOUNT_PATTERN = re.compile(r"\d+(\.\d{1,2})?")
_AMOUNT_LIMIT = Decimal("100000000")


class PaymentConfigurationError(Exception):
    """Raised when eSewa configuration is missing or invalid. The message is safe to log."""


def get_esewa_secret():
    secret = getattr(settings, "ESEWA_CLIENT_SECRET", None)
    if not secret:
        raise PaymentConfigurationError("eSewa payment secret is not configured.")
    return secret


def get_signup_payment_amount():
    """
    Returns the signup amount as the exact string that is both signed and sent
    to eSewa. Accepts only a positive plain decimal below the model limit, so
    empty, non-numeric, zero, negative, NaN/Infinity, and scientific-notation
    values are all rejected rather than producing a malformed payment request.
    """
    raw = getattr(settings, "ESEWA_SIGNUP_PAYMENT_AMOUNT", None)
    value = raw.strip() if isinstance(raw, str) else ""
    if not _AMOUNT_PATTERN.fullmatch(value) or not (0 < Decimal(value) < _AMOUNT_LIMIT):
        raise PaymentConfigurationError("eSewa signup payment amount is invalid.")
    return value


def ensure_signup_gateway_is_production_safe(product_code):
    """Refuse to take signup payments through eSewa's test merchant or test hosts in production."""
    try:
        ensure_gateway_config_is_production_safe(
            merchant_code=product_code, urls=[getattr(settings, "ESEWA_URL", "")]
        )
    except GatewayConfigurationError as exc:
        raise PaymentConfigurationError(str(exc)) from exc


def parse_callback_amount(value):
    """The callback amount as a finite Decimal, or None when it is not a plain number."""
    return _parse_amount(value)


def decode_and_verify_signup_callback(raw_data, secret_key):
    """
    Returns the decoded eSewa callback when it is authentic, otherwise None. Never raises.

    The same rules as the fee callbacks: size-bounded strict decoding, an HMAC-SHA256 signature
    over the fields the payload names, and a requirement that those fields include the ones that
    carry the payment's identity, amount and outcome. A caller must still check that the signed
    values match the stored payment.
    """
    decoded = _decode_callback(raw_data)
    if decoded is None:
        return None
    signed_field_names = decoded.get("signed_field_names")
    provided_signature = decoded.get("signature")
    if not isinstance(signed_field_names, str) or not isinstance(provided_signature, str):
        return None
    fields = [f.strip() for f in signed_field_names.split(",") if f.strip()]
    if not REQUIRED_SIGNED_FIELDS.issubset(fields) or any(f not in decoded for f in fields):
        return None
    message = ",".join(f"{field}={decoded.get(field)}" for field in fields)
    expected = generate_esewa_signature(secret_key, message)
    # Compared as bytes: str comparison raises TypeError for a non-ASCII signature.
    if not hmac.compare_digest(expected.encode("utf-8"), provided_signature.encode("utf-8")):
        return None
    return decoded


def generate_esewa_signature(secret_key, message):
    """
    Generates HMAC SHA256 signature for eSewa.
    Message format: "total_amount,transaction_uuid,product_code"
    """
    if not secret_key:
        raise PaymentConfigurationError("eSewa payment secret is not configured.")

    secret = bytes(secret_key, 'utf-8')
    message = bytes(message, 'utf-8')

    hash_object = hmac.new(secret, message, hashlib.sha256)
    signature = base64.b64encode(hash_object.digest()).decode('utf-8')
    return signature
