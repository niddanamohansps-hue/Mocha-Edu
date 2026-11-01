"""WhatsApp delivery through the Meta WhatsApp Business Cloud API, behind a small provider switch.

``WHATSAPP_PROVIDER`` is ``disabled`` (the default: nothing is queued), ``console`` (development: the message is
logged, never sent) or ``meta``. Only approved *template* messages are sent, which is what WhatsApp allows a
business to start a conversation with.
"""
import logging
import re
import uuid

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/{version}/{phone_number_id}/messages"
PARAM_MAX = 1000


class WhatsAppError(Exception):
    """A send failed. ``permanent`` means retrying cannot help (bad number, bad credentials, rejected template)."""

    def __init__(self, message, permanent=False):
        super().__init__(message)
        self.permanent = permanent


def provider_name():
    return (getattr(settings, "WHATSAPP_PROVIDER", "") or "disabled").strip().lower()


def whatsapp_enabled():
    return provider_name() in ("console", "meta")


def normalize_phone(raw):
    """A phone number as WhatsApp wants it: digits only, with the country code (no plus sign). A bare ten-digit
    or leading-zero number gets the school's default country code. Returns None for anything unusable."""
    if not raw:
        return None
    text = str(raw).strip()
    has_plus = text.startswith("+")
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    country = re.sub(r"\D", "", getattr(settings, "WHATSAPP_DEFAULT_COUNTRY_CODE", "") or "")
    if not has_plus:
        digits = digits.lstrip("0") if digits.startswith("0") else digits
        if country and len(digits) == 10:
            digits = country + digits
    return digits if 8 <= len(digits) <= 15 else None


def mask_phone(phone):
    """``919876543210`` -> ``+91******3210``; the full number is never put in a log or API response."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 8:
        return "whatsapp"
    return f"+{digits[:2]}{'*' * (len(digits) - 6)}{digits[-4:]}"


def _clean(value):
    # Template parameters cannot hold new lines, tabs or runs of spaces.
    return re.sub(r"\s+", " ", str(value)).strip()[:PARAM_MAX] or "-"


def send_template(to_phone, template, language, params):
    """Send one approved template message. Returns the provider's message id; raises WhatsAppError."""
    provider = provider_name()
    if provider == "console":
        logger.info("WhatsApp (console) to %s template=%s params=%s", mask_phone(to_phone), template, list(params))
        return f"console-{uuid.uuid4()}"
    if provider != "meta":
        raise WhatsAppError("WhatsApp is not enabled.", permanent=True)

    phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    if not phone_number_id or not token:
        raise WhatsAppError("WhatsApp credentials are not configured.", permanent=True)

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": language},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": _clean(p)} for p in params]}
            ],
        },
    }
    url = GRAPH_URL.format(version=getattr(settings, "WHATSAPP_API_VERSION", "v21.0"), phone_number_id=phone_number_id)
    try:
        response = requests.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    except requests.RequestException as exc:
        raise WhatsAppError(f"Could not reach WhatsApp: {exc.__class__.__name__}") from exc

    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        # Rate limits and server errors may clear on their own; everything else (bad number, expired token,
        # unapproved template) will fail the same way every time.
        retryable = response.status_code == 429 or response.status_code >= 500
        raise WhatsAppError(f"WhatsApp rejected the message ({response.status_code}): {detail}"[:500], permanent=not retryable)
    try:
        return response.json()["messages"][0]["id"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise WhatsAppError("WhatsApp gave an unexpected reply.", permanent=False)
