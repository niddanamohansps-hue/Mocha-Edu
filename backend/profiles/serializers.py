from rest_framework import serializers
from .models import Profile, InstitutionProfile
from django.db import connection


def attach_users(profiles):
    """Loads the users of many profiles in one query (Profile.user is a soft link, not a join)."""
    from accounts.models import User

    profiles = [p for p in profiles if p is not None]
    ids = {p.user_id for p in profiles if p.user_id and not hasattr(p, "_user_cache")}
    users = {u.id: u for u in User.objects.filter(id__in=ids)} if ids else {}
    for profile in profiles:
        if not hasattr(profile, "_user_cache"):
            profile._user_cache = users.get(profile.user_id) if profile.user_id else None


class WithProfileUsersListSerializer(serializers.ListSerializer):
    """For lists of objects that have a ``profile``: their users are loaded together, not one per row."""

    def to_representation(self, data):
        items = list(data.all() if hasattr(data, "all") else data)
        attach_users(getattr(item, "profile", None) for item in items)
        return super().to_representation(items)


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    username = serializers.CharField(source="user.username", read_only=True)
    student_id = serializers.SerializerMethodField()
    staff_id = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "id",
            "user_id",
            "username",
            "local_username",
            "email",
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "date_of_birth",
            "blood_group",
            "phone",
            "alt_phone",
            "address",
            "profile_image",
            "student_id",
            "staff_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user_id", "email", "username", "student_id", "staff_id")

    def get_email(self, obj):
        if obj.user and getattr(obj.user, "email", None):
            return obj.user.email
        return getattr(obj, "email", None) or None

    def get_student_id(self, obj):
        student = getattr(obj, "student_record", None)
        return str(student.id) if student else None

    def get_staff_id(self, obj):
        staff = getattr(obj, "staff_record", None)
        return str(staff.id) if staff else None


class InstitutionProfileSerializer(serializers.ModelSerializer):
    # These fields come from the Organization model in the public schema
    name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = InstitutionProfile
        fields = (
            "id",
            "name",
            "phone",
            "email",
            "logo",
            "banner",
            "tagline",
            "mission",
            "vision",
            "about",
            "established_date",
            "website",
            "facebook_url",
            "instagram_url",
            "twitter_url",
            "linkedin_url",
        )
        read_only_fields = ("id",)

    def to_representation(self, instance):
        """Add organization data to the output."""
        data = super().to_representation(instance)
        tenant = getattr(connection, "tenant", None)
        if tenant:
            data["name"] = tenant.name
            data["phone"] = getattr(tenant, "phone", "")
            data["email"] = getattr(tenant, "email", "")
        return data

    def update(self, instance, validated_data):
        # Extract organization-related fields
        tenant = validated_data.pop("organization", getattr(connection, "tenant", None))

        org_fields = ["name", "phone", "email"]
        updated_org = False

        for field in org_fields:
            if field in validated_data:
                val = validated_data.pop(field)
                if tenant:
                    setattr(tenant, field, val)
                    updated_org = True

        if updated_org and tenant:
            tenant.save()

        return super().update(instance, validated_data)
