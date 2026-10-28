"""
Error and performance reporting to Sentry. Off unless SENTRY_DSN is set, and always off in tests.

What leaves the server is kept to what is needed to fix a problem: no personal data, no request bodies,
no cookies or auth headers, and secret-looking values are masked. Each event says which school it came
from (the schema name), so a fault can be traced to one school without naming a person.
"""
import re

SECRET_KEYS = re.compile(r"pass|secret|token|key|auth|cookie|session|csrf|otp|pin|card|cvv|signature", re.I)
MASK = "[removed]"


def _mask(value):
    if isinstance(value, dict):
        return {k: (MASK if SECRET_KEYS.search(str(k)) else _mask(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask(v) for v in value]
    return value


def _scrub(event, hint):
    request = event.get("request") or {}
    request.pop("data", None)  # bodies hold passwords, student records and payment details
    request.pop("cookies", None)
    if "headers" in request:
        request["headers"] = _mask(request["headers"])
    if "query_string" in request and SECRET_KEYS.search(str(request["query_string"])):
        request["query_string"] = MASK
    event.pop("user", None)
    for exception in (event.get("exception") or {}).get("values") or []:
        for frame in (exception.get("stacktrace") or {}).get("frames") or []:
            if "vars" in frame:
                frame["vars"] = _mask(frame["vars"])
    return event


def _tag_school(event, hint):
    try:
        from django.db import connection

        event.setdefault("tags", {})["school"] = connection.schema_name
    except Exception:
        pass
    return _scrub(event, hint)


def init_sentry(dsn, environment, traces_sample_rate, release=""):
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=environment or "production",
        release=release or None,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=traces_sample_rate,
        before_send=_tag_school,
        before_send_transaction=_tag_school,
    )
