"""Read ?query parameters from a request without ever letting a malformed value become a server error.

A bad value is the caller's mistake, so it answers 400 and names the parameter, instead of a 500
(which looks like a fault on our side and sends someone hunting for a bug that is not there).

Prefer `model_param` when the value is matched against a model field: the expected type then comes from the
field itself (UUID primary key, integer id, date ...) instead of being guessed at each call site.
"""
import datetime
import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

# PostgreSQL bigint range: a bigger number cannot be compared with an integer column at all.
_BIGINT_MIN, _BIGINT_MAX = -(2**63), 2**63 - 1


def _raw(request, name):
    raw = request.query_params.get(name)
    return None if raw is None or str(raw).strip() == "" else str(raw).strip()


def uuid_param(request, name):
    """The parameter as a UUID, or None when it is absent or empty. A malformed value answers 400."""
    raw = _raw(request, name)
    if raw is None:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ValidationError({name: "Enter a valid UUID."})


def int_param(request, name, default=None, minimum=None, maximum=None):
    """The parameter as an int (clamped to minimum/maximum when given), or default when absent or empty."""
    raw = _raw(request, name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError({name: "Enter a whole number."})
    if minimum is None and not _BIGINT_MIN <= value <= _BIGINT_MAX:
        raise ValidationError({name: "Number is out of range."})
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def date_param(request, name, default=None):
    """The parameter as a date (YYYY-MM-DD), or default when absent or empty. A malformed value answers 400."""
    raw = _raw(request, name)
    if raw is None:
        return default
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        raise ValidationError({name: "Enter a valid date (YYYY-MM-DD)."})


def model_param(request, name, model, field="pk"):
    """The parameter converted by the model field it will be matched against, or None when absent or empty.

    `field` names a field of `model` ("pk" by default). For a foreign key the related model's key decides the
    type, so `model_param(request, "level", Student, "level")` accepts exactly what Student.level stores.
    """
    raw = _raw(request, name)
    if raw is None:
        return None
    target = model._meta.pk if field == "pk" else model._meta.get_field(field)
    target = getattr(target, "target_field", None) or target
    try:
        value = target.to_python(raw)
    except (DjangoValidationError, ValueError, TypeError):
        raise ValidationError({name: f"Enter a valid {_kind(target)}."})
    if isinstance(target, (models.IntegerField, models.AutoField)) and not _BIGINT_MIN <= value <= _BIGINT_MAX:
        raise ValidationError({name: "Number is out of range."})
    return value


def object_param(request, name, queryset, required=True):
    """The object whose primary key is the parameter: 400 for a malformed key, 404 when it does not exist.

    `queryset` may be a model or a queryset (to keep a select_related or a scope). Absent: 404 when
    required (what get_object_or_404(pk=None) always answered, kept so callers see no change), else None.
    """
    return object_or_404(queryset, request.query_params.get(name), name, required=required)


def object_or_404(queryset, raw, name, required=True, **filters):
    """Like get_object_or_404(queryset, pk=raw), but a malformed key answers 400 instead of a 500.

    For ids that come from anywhere (the query string or a request body). Extra `filters` narrow the lookup.
    """
    model = queryset if isinstance(queryset, type) else queryset.model
    if raw is None or str(raw).strip() == "":
        if required:
            raise Http404(f"No {model._meta.verbose_name} given.")
        return None
    target = model._meta.pk
    target = getattr(target, "target_field", None) or target   # a one-to-one primary key
    try:
        pk = target.to_python(str(raw).strip())
    except (DjangoValidationError, ValueError, TypeError):
        raise ValidationError({name: f"Enter a valid {_kind(target)}."})
    if isinstance(target, (models.IntegerField, models.AutoField)) and not _BIGINT_MIN <= pk <= _BIGINT_MAX:
        raise ValidationError({name: "Number is out of range."})
    return get_object_or_404(queryset, pk=pk, **filters)


def _kind(field):
    if isinstance(field, models.UUIDField):
        return "UUID"
    if isinstance(field, (models.IntegerField, models.AutoField)):
        return "whole number"
    if isinstance(field, models.DateField):
        return "date (YYYY-MM-DD)"
    return "value"
