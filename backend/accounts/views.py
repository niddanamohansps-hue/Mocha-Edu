from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import status
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from notifications.services import queue_email

from .serializers import (
    LoginSerializer,
    OrganizationRegisterSerializer,
    UserSerializer,
    ForgotPasswordSerializer,
    ResetPasswordConfirmSerializer,
)
from .models import User
from .utils.jwt_cookies import set_jwt_cookies, clear_jwt_cookies, set_access_cookie
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

password_reset_token_generator = PasswordResetTokenGenerator()


def _blacklist_all_refresh_tokens_for_user(user):
    """
    Revokes every outstanding (not-yet-expired) refresh token for this user,
    so a session active on another device/browser can't mint new access
    tokens after a password reset. Uses the same token_blacklist app/tables
    LogoutView already relies on - no second revocation mechanism.

    Known limitation (see final report): an access token already issued
    remains valid until its own short expiry elapses - there is no
    access-token blacklist in this project, only refresh-token blacklisting.
    """
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)


class RegisterOrganizationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register_organization"

    def post(self, request):
        serializer = OrganizationRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        return Response(
            {
                "message": "Organization created successfully.",
                "domain_url": result["domain_url"],
                "organization_name": result["organization"].name,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        response = Response({"message": "Login successful"}, status=status.HTTP_200_OK)
        set_jwt_cookies(response, user)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except (TokenError, InvalidToken):
                # Already invalid/expired - nothing to blacklist, logout still proceeds.
                pass

        response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        clear_jwt_cookies(response)
        return response


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)

            response = Response(
                {"message": "Token refreshed"}, status=status.HTTP_200_OK
            )
            set_access_cookie(response, access_token)
            return response
        except (TokenError, InvalidToken):
            return Response(
                {"detail": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED
            )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        tenant = getattr(request, "tenant", None)
        requested_role = request.query_params.get("active_role")

        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "needs_password_change": user.needs_password_change,
            "profile": None,
            "roles": [],
            "active_role": None,
        }

        if tenant and tenant.schema_name != "public":
            from roles.models import UserRole

            role_objects = UserRole.objects.filter(user=user).select_related("role")

            role_slugs = [ur.role.slug for ur in role_objects]
            data["roles"] = role_slugs

            # Determine Active Role
            # If requested role is valid for this user, use it; otherwise default to first available
            active_role = None
            if requested_role in role_slugs:
                active_role = requested_role
            elif role_slugs:
                active_role = role_slugs[0]

            data["active_role"] = active_role
            data["permissions"] = []

            if active_role:
                # Find the UserRole object for the active role to get the relation
                # We already fetched them in role_objects, let's find the matching one
                active_user_role = next(
                    (ur for ur in role_objects if ur.role.slug == active_role), None
                )

                if active_user_role:
                    if active_user_role.role.slug == "owner":
                        data["permissions"] = ["*"]  # Superuser wildcard
                    else:
                        data["permissions"] = list(
                            active_user_role.role.permissions.values_list(
                                "codename", flat=True
                            )
                        )

            # Fetch Unified Profile
            from profiles.models import Profile
            from profiles.serializers import ProfileSerializer

            profile = Profile.objects.filter(user_id=user.id).first()
            if profile:
                data["profile"] = ProfileSerializer(profile).data

        return Response(data)


class VerifyAccountView(APIView):
    """
    Checks if a username or email already exists in the global identity pool.
    Used during 'Get Started' to guide the user to login or choose new names.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "verify_account"

    def post(self, request):
        email = request.data.get("email")
        username = request.data.get("username")
        password = request.data.get("password")

        from accounts.models import User

        results = {
            "email_exists": False,
            "username_exists": False,
            "valid_password": False,
            "exists": False,  # Compatibility flag
        }

        user_by_email = User.objects.filter(email=email).first() if email else None
        user_by_username = (
            User.objects.filter(username=username).first() if username else None
        )

        if user_by_email:
            results["email_exists"] = True
            results["exists"] = True
            if password:
                results["valid_password"] = user_by_email.check_password(password)

        if user_by_username:
            results["username_exists"] = True
            # If we were checking by username and email together,
            # we consider it 'existing' if either exists
            results["exists"] = True

        return Response(results)


class ChangePasswordView(APIView):
    """
    Enables users to update their password.
    Specifically clears the 'needs_password_change' flag and temporary credentials.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        new_password = request.data.get("new_password")
        if not new_password:
            return Response(
                {"error": "A new password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as e:
            return Response(
                {"error": " ".join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.needs_password_change = False
        user.initial_password_display = None
        user.save()

        from core.audit import log_action

        log_action(request, action="password_changed", model_name="User", object_id=user.id)

        return Response({"message": "Password updated successfully."})


class ForgotPasswordView(APIView):
    """
    Sends a password-reset email containing a one-time link back to the
    tenant dashboard this request came from. Always returns the same
    generic message regardless of whether the email matches an account,
    to avoid leaking which addresses are registered.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "forgot_password"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Same normalization UserManager.create_user() applies at signup,
        # so a lookup here matches whatever was actually stored - without
        # this, a legitimately-matching address could silently miss due to
        # casing alone, which would itself be an inconsistent (and in
        # principle probeable) difference in lookup behavior.
        email = User.objects.normalize_email(serializer.validated_data["email"])

        user = User.objects.filter(email=email).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = password_reset_token_generator.make_token(user)
            # The hostname is the tenant subdomain this request came in on
            # (this is a multi-tenant app - a single fixed frontend URL
            # would send every school's reset link to the wrong tenant).
            # Only protocol/port come from settings.
            host = request.get_host().split(":")[0]
            port_suffix = (
                f":{settings.PASSWORD_RESET_FRONTEND_PORT}"
                if settings.PASSWORD_RESET_FRONTEND_PORT
                else ""
            )
            reset_url = (
                f"{settings.PASSWORD_RESET_FRONTEND_PROTOCOL}://{host}{port_suffix}"
                f"/reset-password?uid={uid}&token={token}"
            )
            timeout_hours = max(1, settings.PASSWORD_RESET_TIMEOUT // 3600)

            # Everything below writes rows that must either all commit or
            # all roll back together - queue_email()'s Celery dispatch is
            # deferred via transaction.on_commit(), so the worker can never
            # see an EmailOutboxEvent from a request that ultimately failed.
            with transaction.atomic():
                queue_email(
                    to_email=email,
                    subject="Reset your EDU Sekai password",
                    body=(
                        "Someone requested a password reset for this account.\n\n"
                        f"Reset your password: {reset_url}\n\n"
                        f"This link expires in {timeout_hours} hour(s) and can only be used once.\n\n"
                        "If you didn't request this, you can safely ignore this email - "
                        "your password will not be changed."
                    ),
                )

                # Safe to log unconditionally here (only reached when a real
                # user was found) - this never affects the HTTP response
                # below, so it creates no enumeration channel via the API.
                from core.audit import log_action

                log_action(
                    request,
                    action="password_reset_requested",
                    model_name="User",
                    object_id=user.id,
                )

        return Response(
            {"message": "If an account with that email exists, a reset link has been sent."}
        )


class ResetPasswordConfirmView(APIView):
    """Consumes the uid/token from the emailed reset link and sets a new password."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "reset_password"

    def post(self, request):
        serializer = ResetPasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError, UnicodeDecodeError):
            return Response(
                {"error": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # LoginSerializer already treats is_active=False as "this account
        # cannot authenticate" (AuthenticationFailed("User account is
        # disabled")) - extend that same boundary here rather than letting
        # a disabled account still complete a credential change. Checked
        # before the token itself so a disabled account can't be used to
        # probe whether a given token is otherwise valid; the response is
        # identical to any other invalid-link case either way.
        if not user.is_active:
            return Response(
                {"error": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password_reset_token_generator.check_token(user, token):
            # The user WAS resolved (uid decoded to a real account) but the
            # token itself is wrong/expired/already-used - worth a quiet
            # audit trail (someone has a dead/tampered link for a real
            # account), unlike a malformed/nonexistent uid above where
            # there's no real account to attribute this to. Never exposed
            # to the caller - the response is identical either way.
            from core.audit import log_action

            log_action(
                request,
                action="password_reset_failed",
                model_name="User",
                object_id=user.id,
            )
            return Response(
                {"error": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as e:
            return Response(
                {"error": " ".join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        # The token generator already bakes the password hash into its
        # check, so reusing this exact token after this point fails
        # check_token() above regardless - this additionally revokes any
        # OTHER already-issued refresh tokens (other devices/sessions),
        # which a changed password hash alone would not do.
        _blacklist_all_refresh_tokens_for_user(user)

        from core.audit import log_action

        log_action(request, action="password_reset", model_name="User", object_id=user.id)

        return Response({"message": "Password has been reset successfully."})
