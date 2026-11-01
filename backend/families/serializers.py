import uuid

from django.apps import apps
from django.db import transaction
from rest_framework import serializers

from accounts.utils.crypto import encrypt_secret
from profiles.models import Profile
from profiles.serializers import ProfileSerializer, WithProfileUsersListSerializer
from students.models import Student
from .models import Parent, StudentParentRelation

User = apps.get_model("accounts", "User")


class StudentParentRelationSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField(read_only=True)
    parent_name = serializers.SerializerMethodField(read_only=True)
    student_enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)

    class Meta:
        model = StudentParentRelation
        fields = (
            "id",
            "student",
            "parent",
            "relation_type",
            "is_primary_contact",
            "can_pickup",
            "student_name",
            "parent_name",
            "student_enrollment_id",
        )
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=StudentParentRelation.objects.all(),
                fields=["student", "parent"],
                message="This student is already linked to this parent.",
            )
        ]

    def get_student_name(self, obj):
        if obj.student and getattr(obj.student, "profile", None):
            return f"{obj.student.profile.first_name} {obj.student.profile.last_name}".strip()
        return ""

    def get_parent_name(self, obj):
        if obj.parent and getattr(obj.parent, "profile", None):
            return f"{obj.parent.profile.first_name} {obj.parent.profile.last_name}".strip()
        return ""

    def validate(self, attrs):
        student = attrs.get("student") or (self.instance.student if self.instance else None)
        parent = attrs.get("parent") or (self.instance.parent if self.instance else None)

        if student and parent:
            qs = StudentParentRelation.objects.filter(student=student, parent=parent)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("This student is already linked to this parent.")

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        is_primary = validated_data.get("is_primary_contact", False)
        student = validated_data.get("student")
        if is_primary and student:
            # Setting a new primary unsets the old one for this student
            StudentParentRelation.objects.filter(
                student=student, is_primary_contact=True
            ).update(is_primary_contact=False)
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        is_primary = validated_data.get("is_primary_contact", instance.is_primary_contact)
        student = validated_data.get("student", instance.student)
        if is_primary and student:
            # Setting a new primary unsets the old one for this student
            StudentParentRelation.objects.filter(
                student=student, is_primary_contact=True
            ).exclude(pk=instance.pk).update(is_primary_contact=False)
        return super().update(instance, validated_data)


class _ChildSummarySerializer(serializers.ModelSerializer):
    """
    Minimal, read-only student summary embedded in ParentSerializer.children.
    """

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ("id", "enrollment_id", "full_name")

    def get_full_name(self, obj):
        return f"{obj.profile.first_name} {obj.profile.last_name}"


class ParentSerializer(serializers.ModelSerializer):
    profile = serializers.PrimaryKeyRelatedField(
        queryset=Profile.objects.all(), required=False, allow_null=True
    )
    profile_details = ProfileSerializer(source="profile", read_only=True)
    children = serializers.SerializerMethodField()

    # Writable nested/flat profile fields
    first_name = serializers.CharField(required=False, write_only=True)
    middle_name = serializers.CharField(required=False, allow_blank=True, write_only=True)
    last_name = serializers.CharField(required=False, write_only=True)
    phone = serializers.CharField(required=False, allow_blank=True, write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True, write_only=True)
    gender = serializers.CharField(required=False, allow_blank=True, write_only=True)
    address = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        list_serializer_class = WithProfileUsersListSerializer
        model = Parent
        fields = (
            "id",
            "profile",
            "profile_details",
            "occupation",
            "office_address",
            "income_level",
            "whatsapp_opt_in",
            "whatsapp_opt_in_at",
            "children",
            # Writable profile fields:
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "email",
            "gender",
            "address",
        )

    def to_internal_value(self, data):
        if isinstance(data, dict) and isinstance(data.get("profile"), dict):
            data = data.copy()
            raw_profile = data.pop("profile")
            ret = super().to_internal_value(data)
            for f in ["first_name", "middle_name", "last_name", "phone", "email", "gender", "address"]:
                if f in raw_profile and raw_profile[f] is not None:
                    ret[f] = raw_profile[f]
            return ret
        return super().to_internal_value(data)

    def validate(self, attrs):
        # On create, if profile is not supplied, first_name and last_name are required
        if self.instance is None and not attrs.get("profile"):
            raw_profile = self.initial_data.get("profile")
            first_name = attrs.get("first_name") or (raw_profile.get("first_name") if isinstance(raw_profile, dict) else None)
            last_name = attrs.get("last_name") or (raw_profile.get("last_name") if isinstance(raw_profile, dict) else None)
            errors = {}
            if not first_name:
                errors["first_name"] = ["This field is required when creating a parent profile."]
            if not last_name:
                errors["last_name"] = ["This field is required when creating a parent profile."]
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    def get_children(self, obj):
        relations = obj.student_links.all()  # preloaded with the student and profile by ParentViewSet
        return [
            {
                "relation_id": rel.id,
                "relation_type": rel.relation_type,
                "is_primary": rel.is_primary_contact,
                "can_pickup": rel.can_pickup,
                "student": _ChildSummarySerializer(rel.student).data,
            }
            for rel in relations
        ]

    def _extract_profile_data(self, validated_data):
        profile_data = {}
        for field in ["first_name", "middle_name", "last_name", "phone", "email", "gender", "address"]:
            if field in validated_data:
                profile_data[field] = validated_data.pop(field)

        # Allow passing nested profile dictionary directly: { "profile": { "first_name": "...", ... } }
        raw_profile = self.initial_data.get("profile")
        if isinstance(raw_profile, dict):
            for field in ["first_name", "middle_name", "last_name", "phone", "email", "gender", "address"]:
                if field in raw_profile and field not in profile_data:
                    profile_data[field] = raw_profile[field]

        return profile_data

    @transaction.atomic
    def create(self, validated_data):
        profile = validated_data.pop("profile", None)
        profile_data = self._extract_profile_data(validated_data)

        if not profile:
            profile = Profile.objects.create(
                first_name=profile_data.get("first_name", ""),
                middle_name=profile_data.get("middle_name", ""),
                last_name=profile_data.get("last_name", ""),
                phone=profile_data.get("phone", ""),
                email=profile_data.get("email") or None,
                gender=profile_data.get("gender", ""),
                address=profile_data.get("address", ""),
            )
        elif profile_data:
            # If an existing profile was passed and profile fields are also provided, update them
            for attr, val in profile_data.items():
                if attr == "email":
                    profile.email = val or None
                    if profile.user:
                        profile.user.email = val or None
                        profile.user.save(update_fields=["email"])
                else:
                    setattr(profile, attr, val if val is not None else "")
            profile.save()

        parent = Parent.objects.create(profile=profile, **validated_data)
        return parent

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("profile", None)  # Linked profile entity cannot be changed
        profile_data = self._extract_profile_data(validated_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data:
            profile = instance.profile
            for attr, val in profile_data.items():
                if attr == "email":
                    profile.email = val or None
                    if profile.user:
                        profile.user.email = val or None
                        profile.user.save(update_fields=["email"])
                else:
                    setattr(profile, attr, val if val is not None else "")
            profile.save()

        return instance


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

        # Default email to profile.email if not explicitly provided during activation
        user_email = email or getattr(profile, "email", None) or None

        user = User.objects.create_user(
            username=global_username,
            email=user_email,
            password=password,
            needs_password_change=True,
            initial_password_display=encrypt_secret(password),
        )

        profile.user_id = user.id
        profile.local_username = local_username
        if user_email and not getattr(profile, "email", None):
            profile.email = user_email
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
