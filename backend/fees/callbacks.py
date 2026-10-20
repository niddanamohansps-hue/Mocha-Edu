"""
Server-built payment return URLs.

The URLs eSewa redirects the payer to are built here from the tenant's own stored primary
``Domain`` record and fixed frontend paths. Nothing the client sends (``return_url``,
``failure_url``) and nothing taken from the request ``Host`` header is used: the tenant was
resolved from the Host header by django-tenants, but the hostname written into the gateway
request comes from the database row, so a spoofed header cannot redirect a payer elsewhere.

Production safety (see ``gateways.is_production_environment``): the scheme must be https, and the
frontend port from ``PASSWORD_RESET_FRONTEND_PORT`` is ignored when it is the development default
("3555"), so a production deployment that never configured the port does not produce
``https://school.example.com:3555/...``. An explicitly empty port means "no port". A school that
genuinely serves its frontend on port 3555 in production must say so by serving it on a
different port or through the standard https port (a documented limitation).
"""

import re
from dataclasses import dataclass

from django.conf import settings
from django.db import connection

from .gateways import PaymentConfigurationError, is_production_environment

# One fixed callback page per workflow (the Next.js routes already exist).
CALLBACK_PATHS = {
    "fees": "/dashboard/fees/callback",
    "parent_portal": "/dashboard/parent-portal/fees/callback",
}
FAILURE_QUERY = "?status=failed"

DEVELOPMENT_FRONTEND_PORT = "3555"
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)


@dataclass(frozen=True)
class CallbackUrls:
    success_url: str
    failure_url: str


def _tenant_primary_host():
    tenant = getattr(connection, "tenant", None)
    if tenant is None or getattr(tenant, "schema_name", None) in (None, "public"):
        raise PaymentConfigurationError("No tenant is active for this payment.")
    domain = tenant.domains.filter(is_primary=True).first()
    if domain is None:
        raise PaymentConfigurationError("The school has no primary domain configured.")
    host = (domain.domain or "").strip().lower()
    if not _HOST_RE.match(host):
        raise PaymentConfigurationError("The school's primary domain is not a valid host name.")
    return host


def _frontend_port(production):
    port = str(getattr(settings, "PASSWORD_RESET_FRONTEND_PORT", "") or "").strip()
    if not port:
        return ""
    if production and port == DEVELOPMENT_FRONTEND_PORT:
        return ""
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        raise PaymentConfigurationError("The frontend port setting is invalid.")
    return port


def build_callback_urls(kind):
    """The success and failure URLs for a payment workflow (``"fees"`` or ``"parent_portal"``).

    Raises ``PaymentConfigurationError`` (never creates anything) when a safe URL cannot be built.
    """
    path = CALLBACK_PATHS.get(kind)
    if path is None:
        raise PaymentConfigurationError("Unknown payment callback workflow.")

    production = is_production_environment()
    protocol = str(getattr(settings, "PASSWORD_RESET_FRONTEND_PROTOCOL", "https")).strip().lower()
    if protocol not in ("http", "https"):
        raise PaymentConfigurationError("The frontend protocol setting is invalid.")
    if production and protocol != "https":
        raise PaymentConfigurationError("Payment callbacks must use https in production.")

    host = _tenant_primary_host()
    port = _frontend_port(production)
    base = f"{protocol}://{host}{':' + port if port else ''}{path}"
    return CallbackUrls(success_url=base, failure_url=f"{base}{FAILURE_QUERY}")
