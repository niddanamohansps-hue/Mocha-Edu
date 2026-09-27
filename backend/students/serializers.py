from rest_framework import serializers
from .models import Student, AcademicHistory, StudentLevel
from profiles.models import Profile
from families.models import Parent, StudentParentRelation
from django.db import transaction
import uuid
from django.apps import apps
from django_tenants.utils import tenant_context, get_public_schema_name
from accounts.utils.crypto import encrypt_secret

User = apps.get_model("accounts", "User")


from academics.models import AcademicLevel, Section


class StudentEnrollmentSerializer(serializers.Serializer):
    # Basic Info for Profile
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    last_name = serializers.CharField(max_length=100)
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")]
    )
    date_of_birth = serializers.DateField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    # Academic Info
    level_id = serializers.UUIDField()
    section_id = serializers.UUIDField(required=False, allow_null=True)
    academic_year = serializers.CharField(max_length=20)
    admission_date = serializers.DateField(required=False, allow_null=True)
    previous_school = serializers.CharField(required=False, allow_blank=True)
    last_grade_passed = serializers.CharField(required=False, allow_blank=True)

    # Parent Info (Nested)
    parents = serializers.ListField(
        child=serializers.DictField(), required=False, default=[]
    )

    def validate_email(self, value):
        if value:
            # Check if user already exists in public schema
            # We allow existing users to be enrolled in new schools
            pass
        return value

    def validate_level_id(self, value):
        if not AcademicLevel.objects.filter(id=value).exists():
            raise serializers.ValidationError("Academic Level not found")
        return value

    def validate_section_id(self, value):
        if value and not Section.objects.filter(id=value).exists():
            raise serializers.ValidationError("Section not found")
        return value

    @transaction.atomic
    def create(self, validated_data):
        parents_data = validated_data.pop("parents", [])
        level_id = validated_data.pop("level_id")
        section_id = validated_data.pop("section_id", None)

        # 1. Create Identity Profile (No login credentials yet)
        profile = Profile.objects.create(
            user_id=None,  # No global user at admission time
            local_username=None,  # Will be set during portal activation
            first_name=validated_data["first_name"],
            middle_name=validated_data.get("middle_name", ""),
            last_name=validated_data["last_name"],
            gender=validated_data["gender"],
            date_of_birth=validated_data["date_of_birth"],
            phone=validated_data.get("phone", ""),
            address=validated_data.get("address", ""),
        )

        # 3. Create Student Record
        student = Student.objects.create(
            profile=profile,
            enrollment_id=f"STD-{uuid.uuid4().hex[:8].upper()}",
            admission_date=validated_data.get("admission_date"),
        )

        # 4. Create Academic History
        if validated_data.get("previous_school"):
            AcademicHistory.objects.create(
                student=student,
                previous_school=validated_data["previous_school"],
                last_grade_passed=validated_data.get("last_grade_passed", ""),
            )

        # 5. Create Initial Level Placement
        level = AcademicLevel.objects.get(id=level_id)
        section = Section.objects.get(id=section_id) if section_id else None

        StudentLevel.objects.create(
            student=student,
            level=level,
            section=section,
            academic_year=validated_data["academic_year"],
            is_current=True,
        )

        # 6. Handle Parents
        for p_data in parents_data:
            # Create Parent Profile (usually no email for kids' parents initially)
            p_profile = Profile.objects.create(
                first_name=p_data.get("first_name", ""),
                middle_name=p_data.get("middle_name", ""),
                last_name=p_data.get("last_name", ""),
                phone=p_data.get("phone", ""),
                gender=p_data.get("gender", "other"),
                address=p_data.get("address", ""),
            )

            parent = Parent.objects.create(
                profile=p_profile, occupation=p_data.get("occupation", "")
            )

            StudentParentRelation.objects.create(
                student=student,
                parent=parent,
                relation_type=p_data.get("relation", "other"),
                is_primary_contact=p_data.get("is_primary", False),
            )

        return student

    @transaction.atomic
    def update(self, instance, validated_data):
        # instance is the Student object
        profile = instance.profile

        # 1. Update Profile (Identity)
        profile.first_name = validated_data.get("first_name", profile.first_name)
        profile.middle_name = validated_data.get("middle_name", profile.middle_name)
        profile.last_name = validated_data.get("last_name", profile.last_name)
        profile.gender = validated_data.get("gender", profile.gender)
        profile.date_of_birth = validated_data.get(
            "date_of_birth", profile.date_of_birth
        )
        profile.phone = validated_data.get("phone", profile.phone)
        profile.address = validated_data.get("address", profile.address)
        profile.save()

        # 2. Update Student Record
        if "admission_date" in validated_data:
            instance.admission_date = validated_data["admission_date"]
        instance.save()

        # 3. Update or Create Level Info
        # We try to update the CURRENT level
        current_level = instance.enrollments.filter(is_current=True).first()

        new_level_id = validated_data.get("level_id")
        new_section_id = validated_data.get("section_id")

        if new_level_id or new_section_id or "academic_year" in validated_data:
            if current_level:
                if new_level_id:
                    current_level.level = AcademicLevel.objects.get(id=new_level_id)
                if new_section_id:
                    current_level.section = Section.objects.get(id=new_section_id)

                current_level.academic_year = validated_data.get(
                    "academic_year", current_level.academic_year
                )
                current_level.save()
            else:
                # Fallback if no current level exists
                level = (
                    AcademicLevel.objects.get(id=new_level_id) if new_level_id else None
                )
                section = (
                    Section.objects.get(id=new_section_id) if new_section_id else None
                )

                if level:
                    StudentLevel.objects.create(
                        student=instance,
                        level=level,
                        section=section,
                        academic_year=validated_data.get("academic_year", ""),
                        is_current=True,
                    )

        # 4. Handle Parents - TODO: Complex Nested Update
        # For now, we skip updating parents via this endpoint to avoid complexity
        # and recommend a dedicated Family Management API.

        return instance


class BulkAccountCreationSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)
    email = serializers.EmailField(required=False, allow_null=True)

    def validate_student_id(self, value):
        if not Student.objects.filter(id=value).exists():
            raise serializers.ValidationError("Student not found")
        return value

    def validate_username(self, value):
        # We don't validate against global User table anymore
        # Instead, we'll check local_username uniqueness within the tenant
        return value

    def _generate_unique_local_username(self, base_username):
        """
        Generate a unique local_username within the current tenant.
        Appends numbers if duplicates exist (e.g., johnprasaddoe, johnprasaddoe2, johnprasaddoe3)
        """
        local_username = base_username
        counter = 2

        # Check if this local_username already exists in this school
        while Profile.objects.filter(local_username=local_username).exists():
            local_username = f"{base_username}{counter}"
            counter += 1

        return local_username

    def _generate_global_username(self, local_username):
        """
        Generate a globally unique username for the User table.
        Format: local_username + random suffix
        """
        while True:
            random_suffix = uuid.uuid4().hex[:6]
            global_username = f"{local_username}_{random_suffix}"

            if not User.objects.filter(username=global_username).exists():
                return global_username

    @transaction.atomic
    def save(self, **kwargs):
        student_id = self.validated_data["student_id"]
        provided_username = self.validated_data[
            "username"
        ]  # From frontend (e.g., "johnprasaddoe")
        password = self.validated_data["password"]
        email = self.validated_data.get("email")

        student = Student.objects.select_related("profile").get(id=student_id)
        profile = student.profile

        if profile.user_id:
            raise serializers.ValidationError(
                "This student already has a user account."
            )

        # Step 1: Generate unique local_username (school-specific)
        # This is what the user will see and use to login
        local_username = self._generate_unique_local_username(provided_username)

        # Step 2: Generate globally unique username for User table
        # This is for Django's authentication system
        global_username = self._generate_global_username(local_username)

        # Step 3: Create global user with the unique global username
        user = User.objects.create_user(
            username=global_username,  # Globally unique
            email=email or None,
            password=password,
            needs_password_change=True,
            initial_password_display=encrypt_secret(password),
        )

        # Step 4: Assign Student Role
        from django.db import connection
        from roles.models import Role, UserRole

        try:
            student_role = Role.objects.get(slug="student")
            UserRole.objects.get_or_create(
                user=user,
                role=student_role,
                defaults={"is_active": True},
            )
        except Role.DoesNotExist:
            print("Warning: 'student' role not found. Ensure roles are seeded.")

        # Step 5: Update profile with both usernames
        profile.user_id = user.id
        profile.local_username = local_username  # School-specific (e.g., "johnprasaddoe" or "johnprasaddoe2")
        profile.save()

        return user


# === PROMOTION & TRANSFER ===

from .models import PromotionRecord  # noqa: E402


class PromotionEntryInputSerializer(serializers.Serializer):
    """One student's requested lifecycle action within a batch. UUID
    fields resolved to model instances happen in the view, not here - this
    serializer only validates shape/choices; academics.services owns the
    cross-field business validation (target belongs to level, duplicate
    target year, etc.)."""

    student = serializers.UUIDField()
    action = serializers.ChoiceField(
        choices=["promoted", "retained", "transferred", "withdrawn", "graduated"]
    )
    target_academic_year = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    target_level = serializers.UUIDField(required=False, allow_null=True)
    target_section = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class PromotionBatchInputSerializer(serializers.Serializer):
    source_academic_year = serializers.CharField(max_length=20)
    entries = PromotionEntryInputSerializer(many=True)

    def validate_entries(self, value):
        if not value:
            raise serializers.ValidationError("At least one entry is required.")
        return value


class PromotionRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)
    source_level_name = serializers.CharField(source="source_level.name", read_only=True, default=None)
    target_level_name = serializers.CharField(source="target_level.name", read_only=True, default=None)
    source_section_name = serializers.CharField(source="source_section.name", read_only=True, default=None)
    target_section_name = serializers.CharField(source="target_section.name", read_only=True, default=None)
    is_reversed = serializers.SerializerMethodField()

    class Meta:
        model = PromotionRecord
        fields = [
            "id", "student", "student_name", "enrollment_id", "action",
            "source_academic_year", "target_academic_year",
            "source_level", "source_level_name", "target_level", "target_level_name",
            "source_section", "source_section_name", "target_section", "target_section_name",
            "reason", "reverses", "is_reversed", "created_by", "created_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        profile = obj.student.profile
        return f"{profile.first_name} {profile.last_name}"

    def get_is_reversed(self, obj):
        return hasattr(obj, "reversal")
