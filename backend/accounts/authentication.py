from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from accounts.tenant_access import is_tenant_member


class JWTCookieAuthentication(JWTAuthentication):

    def authenticate(self, request):
        access_token = request.COOKIES.get("access_token")

        if not access_token:
            return None

        try:
            validated_token = self.get_validated_token(access_token)
            user = self.get_user(validated_token)
        except (InvalidToken, TokenError):
            return None

        # The token identifies a global user, not a tenant. Treat a user who does not
        # belong to the current tenant as unauthenticated (see accounts.tenant_access).
        if not is_tenant_member(user):
            return None

        return (user, validated_token)
