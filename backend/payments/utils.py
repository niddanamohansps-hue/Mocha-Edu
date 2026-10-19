import hashlib
import hmac
import base64
import re
from decimal import Decimal

from django.conf import settings

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
