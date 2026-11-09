"""Read ?query parameters from a request without ever letting a malformed value become a server error.

A bad value is the caller's mistake, so it answers 400 and names the parameter, instead of a 500
(which looks like a fault on our side and sends someone hunting for a bug that is not there).
"""
import uuid

from rest_framework.exceptions import ValidationError


def uuid_param(request, name):
    """The parameter as a UUID, or None when it is absent or empty. A malformed value answers 400."""
    raw = request.query_params.get(name)
    if raw in (None, ""):
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        raise ValidationError({name: "Enter a valid UUID."})


def int_param(request, name, default=None, minimum=None, maximum=None):
    """The parameter as an int (clamped to minimum/maximum when given), or default when absent or empty."""
    raw = request.query_params.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(str(raw))
    except ValueError:
        raise ValidationError({name: "Enter a whole number."})
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value
