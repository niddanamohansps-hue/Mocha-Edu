import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def captcha_enabled():
    return bool(getattr(settings, "TURNSTILE_SECRET_KEY", ""))


def verify_captcha(token, remote_ip=None):
    """Cloudflare Turnstile check. With no secret configured the check is off and everything passes; with one
    configured a missing token, a failed check or an unreachable verifier all refuse the request."""
    if not captcha_enabled():
        return True
    if not token:
        return False
    try:
        response = requests.post(
            VERIFY_URL,
            data={"secret": settings.TURNSTILE_SECRET_KEY, "response": token, "remoteip": remote_ip or ""},
            timeout=5,
        )
        return bool(response.json().get("success"))
    except (requests.RequestException, ValueError):
        logger.warning("Turnstile verification could not be completed", exc_info=True)
        return False
