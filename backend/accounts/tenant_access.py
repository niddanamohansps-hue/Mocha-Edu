"""Tenant-membership authorization helpers.

A global ``accounts.User`` is not tied to a tenant, and the JWT carries only the user id, so a
valid token from one school would otherwise authenticate on every other school's host. These
helpers apply the same membership rule the login backend uses
(``accounts.backends.TenantUsernameBackend``): a user belongs to the current tenant if they have a
tenant ``Profile`` or any ``UserRole`` there. Superusers keep their existing cross-tenant access.

The public schema has no ``Profile``/``UserRole`` tables, so it is never queried there; a request
on the public host is not subject to tenant membership.
"""

from django.db import connection
from django_tenants.utils import get_public_schema_name
from rest_framework.permissions import BasePermission


def _on_public_schema():
    return connection.schema_name == get_public_schema_name()


def is_tenant_member(user):
    """True if ``user`` may act inside the current tenant schema.

    Keep this rule identical to the fallback branch of ``TenantUsernameBackend.authenticate``.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if _on_public_schema():
        return True
    if getattr(user, "is_superuser", False):
        return True

    # Lazy imports: both apps are tenant apps and importing them at module load would
    # create an import cycle through settings / authentication.
    from profiles.models import Profile
    from roles.models import UserRole

    return (
        Profile.objects.filter(user_id=user.id).exists()
        or UserRole.objects.filter(user=user).exists()
    )


class IsTenantMember(BasePermission):
    """Authenticated and a member of the current tenant (see ``is_tenant_member``)."""

    message = "You are not a member of this organization."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and is_tenant_member(user))


class HasAnyPermission(BasePermission):
    """Passes when the user holds at least one of the given permission codenames.

    Each codename is evaluated with the existing ``roles.permissions.HasPermission`` so owner,
    superuser, active-role and public-schema handling stay in one place. Like ``HasPermission`` it
    is used as an instance (``HasAnyPermission("a", "b")``) and returns itself when called, so it
    works inside ``permission_classes`` and ``get_permissions``.
    """

    def __init__(self, *codenames):
        self.codenames = tuple(codenames)

    def __call__(self):
        return self

    def has_permission(self, request, view):
        if not self.codenames:
            return False

        from roles.permissions import HasPermission

        return any(
            HasPermission(codename).has_permission(request, view)
            for codename in self.codenames
        )
