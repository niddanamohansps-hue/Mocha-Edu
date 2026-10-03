import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """
    Builds a Fernet cipher for encrypting transient secrets at rest
    (e.g. temporary passwords shown once to an admin for distribution).

    Uses FIELD_ENCRYPTION_KEY from the environment if set. settings.py
    requires this to be set whenever DEBUG=False, so the SECRET_KEY-derived
    fallback below only ever runs in local/dev - it exists purely so this
    works out of the box there without requiring a new .env value.
    """
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if not key:
        digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    elif isinstance(key, str):
        key = key.encode("utf-8")
    return Fernet(key)


def encrypt_secret(raw_value: str) -> str:
    """Encrypts a plaintext secret (e.g. a temporary password) for storage at rest."""
    if raw_value is None:
        return raw_value
    token = _get_fernet().encrypt(raw_value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(stored_value: str) -> str:
    """
    Decrypts a value previously stored via encrypt_secret().

    Falls back to returning the stored value unchanged if it isn't a valid
    Fernet token - this covers records written before encryption was added
    (e.g. existing seeded/test data), so old rows keep displaying correctly
    instead of raising an error.
    """
    if not stored_value:
        return stored_value
    try:
        return _get_fernet().decrypt(stored_value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError):
        logger.warning("decrypt_secret: value is not an encrypted token, returning as-is (legacy plaintext)")
        return stored_value
