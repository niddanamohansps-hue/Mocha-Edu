"""System check: does the configured database match the one the environment declares?

Warning only (it never blocks a command) and it never opens a database
connection: it compares configuration values (settings.DATABASES["default"]
NAME/HOST/PORT against EDUSEKAI_EXPECTED_DATABASE), nothing more. The logic
lives in config/db_identity.py so it can be tested without Django settings.

It is registered under the "edusekai" tag, not the "database" tag, because
Django skips database-tagged checks unless explicitly asked and this one does
not need a database.
"""

from django.conf import settings
from django.core.checks import Warning, register

from config.db_identity import evaluate


def messages_from_settings(settings_obj):
    """Check messages for any object exposing the three relevant settings."""
    default_db = (getattr(settings_obj, "DATABASES", None) or {}).get("default", {})
    findings = evaluate(
        getattr(settings_obj, "EDUSEKAI_ENV", ""),
        getattr(settings_obj, "EDUSEKAI_EXPECTED_DATABASE", ""),
        default_db,
    )
    return [Warning(finding.message, hint=finding.hint, id=finding.code) for finding in findings]


@register("edusekai")
def check_database_identity(app_configs, **kwargs):
    return messages_from_settings(settings)
