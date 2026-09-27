import uuid

from django.apps import apps
from django.db import transaction
from rest_framework import serializers

from accounts.utils.crypto import encrypt_secret
from profiles.models import Profile
from profiles.serializers import ProfileSerializer
from .models import Parent, StudentParentRelation

User = apps.get_model("accounts", "User")


class StudentParentRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentParentRelation
        fields = "__all__"


class ParentSerializer(serializers.ModelSerializer):
    profile_details = ProfileSerializer(source="profile", read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = Parent
        fields = (
            "id",
            "profile",
            "profile_details",
            "occupation",
            "office_address",
            "income_level",
            "children",
        )

    def get_children(self, obj):
        from students.serializers import StudentSerializer

        relations = obj.student_links.all()
        return [
            {
                "relation_type": rel.relation_type,
                "is_primary": rel.is_primary_contact,
                "student": StudentSerializer(rel.student).data,
            }
            for rel in relations
        ]


class ParentPortalActivationSerializer(serializers.Serializer):
    """
    Creates a User account for an existing Parent record and assigns the
    'parent' system role. Mirrors students.serializers.BulkAccountCreationSerializer
    and staff.serializers.StaffActivationSerializer exactly - same
    local/global-username split, same encrypted-temp-password pattern.
    """

    parent_id = serializers.UUIDField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)
    email = serializers.EmailField(required=False, allow_null=True)

    def validate_parent_id(self, value):
        if not Parent.objects.filter(id=value).exists():
            raise serializers.ValidationError("Parent not found")
        return value

    def _generate_unique_local_username(self, base_username):
        local_username = base_username
        counter = 2
        while Profile.objects.filter(local_username=local_username).exists():
            local_username = f"{base_username}{counter}"
            counter += 1
        return local_username

    def _generate_global_username(self, local_username):
        while True:
            random_suffix = uuid.uuid4().hex[:6]
            global_username = f"{local_username}_{random_suffix}"
            if not User.objects.filter(username=global_username).exists():
                return global_username

    @transaction.atomic
    def save(self, **kwargs):
        parent_id = self.validated_data["parent_id"]
        provided_username = self.validated_data["username"]
        password = self.validated_data["password"]
        email = self.validated_data.get("email")

        parent = Parent.objects.select_related("profile").get(id=parent_id)
        profile = parent.profile

        if profile.user_id:
            raise serializers.ValidationError("This parent already has a user account.")

        local_username = self._generate_unique_local_username(provided_username)
        global_username = self._generate_global_username(local_username)

        user = User.objects.create_user(
            username=global_username,
            email=email or None,
            password=password,
            needs_password_change=True,
            initial_password_display=encrypt_secret(password),
        )

        # Link profile BEFORE assigning the role. profiles.signals.create_profile_for_role
        # fires on UserRole post_save and auto-creates a Profile for any role NOT in its
        # ["student", "instructor"] skip list - "parent" is not in that list, so linking
        # first ensures the signal's get_or_create(user_id=user.id, ...) finds this real
        # Parent profile instead of creating a duplicate "New User" one. Mirrors the exact
        # ordering (and reasoning) already used by staff.serializers.InstructorActivationSerializer.
        profile.user_id = user.id
        profile.local_username = local_username
        profile.save()

        from roles.models import Role, UserRole

        try:
            parent_role = Role.objects.get(slug="parent")
            UserRole.objects.get_or_create(
                user=user, role=parent_role, defaults={"is_active": True}
            )
        except Role.DoesNotExist:
            print("Warning: 'parent' role not found. Ensure roles are seeded.")

        return user
