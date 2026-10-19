"""Database identity guard: thin Django adapter (Stage 3C).

Wraps the pure policy ``config.db_identity.check_identity`` for use by Django code.
Nothing calls it yet: no model, view, serializer, command or script is hooked up in
this stage.

What it does
- Resolves the database alias (the one passed in, or the django-tenants tenant alias).
- Reads ``settings.EDUSEKAI_EXPECTED_DATABASE`` (default "") and ``settings.DATABASES[alias]``.
- Asks ``check_identity`` (derived test database allowed only as described below) and
  either returns "ok" or raises ``IdentityGuardError`` with a fixed code.

What it does not do
- It never opens a database connection (it does not touch ``django.db.connections``).
- It reads no setting other than ``EDUSEKAI_EXPECTED_DATABASE``, ``DATABASES`` and the
  test-only ``EDUSEKAI_ALLOW_DERIVED_TEST_DB`` (see below), and it logs nothing.
- It is fail-closed for both tiers when the expected identity is absent (no warning mode yet).

Derived test database (off by default)
- ``test_<expected name>`` on the same host and port is accepted only when BOTH
  ``settings.EDUSEKAI_ALLOW_DERIVED_TEST_DB is True`` AND Django's test environment is
  active (``django.test.utils._TestState`` has ``saved_data``, which Django's test runner
  sets before it creates the test databases and removes afterwards). The setting alone is
  argv based (``sys.argv[1] == "test"``), so it is not trusted without the second check.
  If the setting is not exactly True, ``django.test.utils`` is not even imported. If the
  second check fails or cannot be made, the exception is simply off (a mismatch stays a
  mismatch). Parallel test-database suffixes and a custom ``TEST["NAME"]`` are not accepted.
- It compares configuration values, not the connection that is actually opened (libpq
  environment variables, ``OPTIONS``, proxies or DNS can still lead elsewhere).

Import safety: only the standard library and ``config.db_identity`` are imported at module
load. Django settings and ``django_tenants.utils`` are imported lazily inside the function,
so importing this module needs no configured settings. No models are imported.

Errors never carry database names, hosts, ports, credentials, connection options or raw
exception text: only a fixed code, the validated operation label and the tier.
"""

import re
from collections.abc import Mapping

from config import db_identity

TIER_DESTRUCTIVE = "destructive"
TIER_PROVISIONING = "provisioning"
TIERS = (TIER_DESTRUCTIVE, TIER_PROVISIONING)

CODE_ABSENT = db_identity.IDENTITY_ABSENT
CODE_MALFORMED = db_identity.IDENTITY_MALFORMED
CODE_MISMATCH = db_identity.IDENTITY_MISMATCH
CODE_UNAVAILABLE = "unavailable"
GUARD_CODES = (CODE_ABSENT, CODE_MALFORMED, CODE_MISMATCH, CODE_UNAVAILABLE)

# Placeholder stored instead of an invalid operation label or tier (never echoed back).
INVALID = "invalid"

# A caller-supplied operation label: a short fixed identifier such as "create_tenant".
_OPERATION_LABEL = re.compile(r"[a-z][a-z0-9_.:-]{0,63}")


def _valid_operation(operation):
    return isinstance(operation, str) and _OPERATION_LABEL.fullmatch(operation) is not None


def _valid_tier(tier):
    return isinstance(tier, str) and tier in TIERS


class IdentityGuardError(Exception):
    """The database identity guard refused an operation.

    Attributes: ``code`` (one of GUARD_CODES), ``operation`` (the validated label, or
    "invalid"), ``tier`` (one of TIERS, or "invalid"). Values outside those sets are
    replaced, so the message can never contain caller-supplied or connection text.
    """

    def __init__(self, code, operation, tier):
        self.code = code if code in GUARD_CODES else CODE_UNAVAILABLE
        self.operation = operation if _valid_operation(operation) else INVALID
        self.tier = tier if _valid_tier(tier) else INVALID
        super().__init__(
            f"database identity guard refused operation '{self.operation}' "
            f"(tier: {self.tier}, code: {self.code})"
        )

    def __reduce__(self):
        return (type(self), (self.code, self.operation, self.tier))


def _test_environment_active():
    """True while Django's test runner has its test environment set up (django.test.utils)."""
    from django.test.utils import _TestState

    return hasattr(_TestState, "saved_data")


def _derived_test_database_allowed(settings):
    """True only for the explicit test-only setting AND an active Django test environment.

    Any problem checking the second condition means "not allowed", never an error.
    """
    if getattr(settings, "EDUSEKAI_ALLOW_DERIVED_TEST_DB", False) is not True:
        return False
    try:
        return _test_environment_active() is True
    except Exception:  # noqa: BLE001 - fail closed: the exception stays off
        return False


def _inspect(alias):
    """Return the check_identity result code for ``alias`` (None: the tenant alias).

    Any problem here (settings not configured, alias unresolvable or missing, settings
    entry not a mapping) raises; the caller turns every exception into "unavailable".
    """
    from django.conf import settings

    if alias is None:
        from django_tenants.utils import get_tenant_database_alias

        alias = get_tenant_database_alias()
    if not isinstance(alias, str) or not alias:
        raise LookupError("database alias")

    expected_value = getattr(settings, "EDUSEKAI_EXPECTED_DATABASE", "")
    db_settings = settings.DATABASES[alias]  # no fallback to "default" when the alias is missing
    if not isinstance(db_settings, Mapping):
        raise TypeError("database settings")
    return db_identity.check_identity(
        expected_value, db_settings, allow_derived_test=_derived_test_database_allowed(settings)
    )


def require_expected_database(operation, *, tier, alias=None):
    """Allow the operation only if the configured database is the expected one.

    ``operation``  a fixed label such as "create_tenant" (lowercase letters, digits and
                   ``_ . : -``, at most 64 characters); only used in the error
    ``tier``       TIER_DESTRUCTIVE or TIER_PROVISIONING. In this stage both tiers behave the
                   same: an absent expected identity is refused
    ``alias``      database alias to check; None means the django-tenants tenant alias

    Returns "ok" when the identity matches. Raises IdentityGuardError with code "absent",
    "malformed", "mismatch" or "unavailable" otherwise. An invalid ``tier`` or ``operation``
    is also refused ("unavailable") rather than treated as a default.
    """
    if not _valid_operation(operation) or not _valid_tier(tier):
        raise IdentityGuardError(CODE_UNAVAILABLE, operation, tier)

    try:
        result = _inspect(alias)
    except Exception:  # noqa: BLE001 - fail closed; the original message is deliberately dropped
        raise IdentityGuardError(CODE_UNAVAILABLE, operation, tier) from None

    if result == db_identity.IDENTITY_OK:
        return result
    if result in (CODE_ABSENT, CODE_MALFORMED, CODE_MISMATCH):
        raise IdentityGuardError(result, operation, tier)
    raise IdentityGuardError(CODE_UNAVAILABLE, operation, tier)
