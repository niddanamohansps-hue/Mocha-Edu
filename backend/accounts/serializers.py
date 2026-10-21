from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from django.db import transaction
from django.conf import settings

from accounts.models import User
from accounts.provisioning import ProvisioningError, provision_organization
from organizations.models import Organization


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "is_active", "needs_password_change")


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        local_username = attrs.get(
            "username"
        )  # User enters their school-specific username
        password = attrs.get("password")

        # Step 1: Try to find the Profile with this local_username in the current tenant
        from profiles.models import Profile
        from django.db import connection

        profile = Profile.objects.filter(local_username=local_username).first()

        if not profile or not profile.user_id:
            # Fallback: Try direct authentication (for backwards compatibility or owner accounts)
            user = authenticate(username=local_username, password=password)
        else:
            # Step 2: Get the global User linked to this Profile
            from accounts.models import User

            global_user = User.objects.filter(id=profile.user_id).first()

            if not global_user:
                raise AuthenticationFailed("Invalid credentials")

            # Step 3: Authenticate using the global username
            user = authenticate(username=global_user.username, password=password)

        if not user:
            raise AuthenticationFailed("Invalid credentials")

        if not user.is_active:
            raise AuthenticationFailed("User account is disabled")

        attrs["user"] = user
        return attrs


class OrganizationRegisterSerializer(serializers.Serializer):
    organization_name = serializers.CharField(max_length=255)
    subdomain = serializers.SlugField(max_length=50)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_subdomain(self, value):
        if Organization.objects.filter(schema_name=value).exists():
            raise serializers.ValidationError("This subdomain is already taken.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "This username is already taken. Please choose another one."
            )
        return value

    def validate_email(self, value):
        # We allow existing users to register new organizations
        return value

    def validate(self, attrs):
        # An existing account may open another organization, but only with its own password.
        # Checked here (not only in create) so a paid signup cannot fail on it after payment.
        existing = User.objects.filter(email=attrs["email"]).first()
        if existing and not existing.check_password(attrs["password"]):
            raise serializers.ValidationError(
                {"password": "Password does not match existing account for this email."}
            )
        return attrs

    def create(self, validated_data):
        # Creating a tenant runs schema DDL, so it is deliberately not one transaction. The steps
        # live in accounts.provisioning so a paid signup can resume them after a partial failure.
        try:
            return provision_organization(
                organization_name=validated_data["organization_name"],
                subdomain=validated_data["subdomain"],
                username=validated_data["username"],
                email=validated_data["email"],
                password=validated_data["password"],
                phone=validated_data.get("phone", ""),
            )
        except ProvisioningError as exc:
            raise serializers.ValidationError({"non_field_errors": [exc.message]})
