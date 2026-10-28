"""
Cached lookup of what a user's roles grant in the current school.

HasPermission used to run one query for the user's roles and one more per role on every check, and many
views check several permissions per request. role_permissions() answers all of them from:

1. the request itself (computed at most once per request), then
2. the shared cache for PERMISSION_CACHE_SECONDS, keyed by school, a per-school version and the user.

Any change to roles, role grants or role assignments bumps the school's version (see the signals below),
so a revoked permission stops working on the very next request. If the cache is unavailable, the answer is
computed from the database as before: a cache failure never grants anything.
"""
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models.signals import m2m_changed, post_delete, post_save

logger = logging.getLogger(__name__)

OWNER = "owner"
_REQUEST_ATTR = "_edusekai_role_permissions"


def _seconds():
    return getattr(settings, "PERMISSION_CACHE_SECONDS", 0)


def _version_key(schema):
    return f"permver:{schema}"


def _from_database(user):
    """{role_slug: frozenset(codenames)} for every role the user holds in the current school."""
    from .models import Role, UserRole

    slugs = list(UserRole.objects.filter(user=user).values_list("role__slug", flat=True).distinct())
    granted = {slug: set() for slug in slugs}
    for slug, codename in Role.objects.filter(slug__in=slugs, permissions__isnull=False).values_list(
        "slug", "permissions__codename"
    ):
        granted[slug].add(codename)
    return {slug: frozenset(codes) for slug, codes in granted.items()}


def role_permissions(request):
    """What each of the request user's roles grants here. Empty when the user holds no role."""
    holder = getattr(request, "_request", request)  # the same answer for the DRF and the Django request
    memo = getattr(holder, _REQUEST_ATTR, None)
    schema = connection.schema_name
    if memo is not None and memo[0] == schema:
        return memo[1]

    user = request.user
    seconds = _seconds()
    result = None
    key = None
    if seconds > 0:
        try:
            version = cache.get(_version_key(schema), 0)
            key = f"perm:{schema}:{version}:{user.pk}"
            cached = cache.get(key)
            if cached is not None:
                result = {slug: frozenset(codes) for slug, codes in cached}
        except Exception:  # a broken cache must never block or grant access
            logger.warning("Permission cache unavailable; reading from the database.", exc_info=True)
            key = None
    if result is None:
        result = _from_database(user)
        if key is not None:
            try:
                cache.set(key, [(slug, sorted(codes)) for slug, codes in result.items()], seconds)
            except Exception:
                logger.warning("Could not store permissions in the cache.", exc_info=True)

    setattr(holder, _REQUEST_ATTR, (schema, result))
    return result


def forget_school_permissions(schema=None):
    """Make every cached answer for this school stale (the version moves on; old keys simply expire)."""
    if _seconds() <= 0:
        return
    key = _version_key(schema or connection.schema_name)
    try:
        if not cache.add(key, 1, None):
            cache.incr(key)
    except Exception:
        logger.warning("Could not invalidate cached permissions.", exc_info=True)


def _connect_signals():
    from .models import Permission, Role, UserRole

    def changed(**kwargs):
        forget_school_permissions()

    for model in (Role, UserRole, Permission):
        post_save.connect(changed, sender=model, dispatch_uid=f"perm-cache-save-{model.__name__}", weak=False)
        post_delete.connect(changed, sender=model, dispatch_uid=f"perm-cache-delete-{model.__name__}", weak=False)
    m2m_changed.connect(changed, sender=Role.permissions.through, dispatch_uid="perm-cache-grants", weak=False)


_connect_signals()
