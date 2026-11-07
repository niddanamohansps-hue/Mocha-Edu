"""Absolute links into a school's own frontend, for messages that are read outside the app (email, WhatsApp)."""


def portal_link(path):
    """
    An absolute link to the tenant's frontend. There is no inbound request to read the host from in background
    jobs, so the tenant's own primary Domain row (already the source of truth for tenant routing) supplies it, with
    the protocol and port the password-reset links use. With no tenant or domain it falls back to the bare path.
    """
    from django.conf import settings
    from django.db import connection

    tenant = connection.tenant
    domain = tenant.domains.filter(is_primary=True).first() if tenant else None
    if domain is None and tenant is not None:
        domain = tenant.domains.first()
    if domain is None:
        return path

    port_suffix = (
        f":{settings.PASSWORD_RESET_FRONTEND_PORT}" if settings.PASSWORD_RESET_FRONTEND_PORT else ""
    )
    return f"{settings.PASSWORD_RESET_FRONTEND_PROTOCOL}://{domain.domain}{port_suffix}{path}"
