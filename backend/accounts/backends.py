from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db import connection
from profiles.models import Profile
from roles.models import UserRole

User = get_user_model()


class TenantUsernameBackend(ModelBackend):
    """
    Allows authentication using the 'local_username' stored in the tenant's profile.
    This enables school-wide unique usernames instead of globally unique ones.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        # 1. Get current context
        schema_name = connection.schema_name

        # Helper to find user by global identifiers (username or email)
        def get_global_user(identifier):
            try:
                if "@" in identifier:
                    return User.objects.get(email=identifier)
                return User.objects.get(username=identifier)
            except User.DoesNotExist:
                return None

        # 2. PUBLIC SCHEMA: Only check global identifiers
        if schema_name == "public":
            user = get_global_user(username)
            if user and user.check_password(password):
                return user
            return None

        # 3. TENANT SCHEMA: Check local identity, then fallback
        # First check local_username in the current tenant's Profile table
        try:
            profile = Profile.objects.filter(local_username=username).first()
            if profile and profile.user_id:
                user = User.objects.filter(id=profile.user_id).first()
                if user and user.check_password(password):
                    return user
        except Exception:
            # Table might not exist in this context or other DB error
            pass

        # Fallback to global identifier - only allowed if user has a valid tenant association
        user = get_global_user(username)
        if user and user.check_password(password):
            if user.is_superuser:
                return user
            if Profile.objects.filter(user_id=user.id).exists() or UserRole.objects.filter(user=user).exists():
                return user
            return None

        return None
