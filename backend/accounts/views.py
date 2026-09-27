from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .serializers import LoginSerializer, OrganizationRegisterSerializer, UserSerializer
from .utils.jwt_cookies import set_jwt_cookies, clear_jwt_cookies, set_access_cookie
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


class RegisterOrganizationView(APIView):
    permission_classes = [AllowAny]

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
