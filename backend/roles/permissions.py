from rest_framework import permissions


class HasPermission(permissions.BasePermission):
    """
    Checks if the user has the required permission 'codename'.
    Usage: permission_classes = [HasPermission('edit_grade')]
    """

    def __init__(self, required_permission):
        self.required_permission = required_permission

    def __call__(self):
        return self

    def has_permission(self, request, view):
        user = request.user
        tenant = getattr(request, "tenant", None)

        if not tenant or tenant.schema_name == "public":
            return False

        # 1. Allow superusers to bypass role checks inside a valid tenant context
        if request.user.is_superuser:
            return True

        # Get Active Role Slug
        # In a real request flow, 'request.GET' may not be the robust place if used in mutations
        # We really need a consistent way. For now, let's check query_params or header.
        # But wait! Permission checks happen BEFORE the view.
        # Let's rely on the user's role in the DB.

        requested_active_role = request.query_params.get("active_role")

        from roles.cache import OWNER, role_permissions

        # {role_slug: codenames} for every role the user holds in this school, computed once per
        # request and cached across requests (invalidated whenever roles or grants change).
        granted = role_permissions(request)
        if not granted:
            return False

        # A role named in the request is checked alone; owner passes everything.
        if requested_active_role in granted:
            if requested_active_role == OWNER:
                return True
            return self.required_permission in granted[requested_active_role]

        # Otherwise any of the user's roles may grant it.
        if OWNER in granted:
            return True
        return any(self.required_permission in codes for codes in granted.values())
