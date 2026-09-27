from rest_framework import serializers
from .models import StaffMember, Instructor
from profiles.serializers import ProfileSerializer
from django.db import transaction
from profiles.models import Profile
from django.apps import apps
import uuid
from accounts.utils.crypto import encrypt_secret

User = apps.get_model("accounts", "User")


class InstructorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instructor
        fields = "__all__"


class StaffMemberSerializer(serializers.ModelSerializer):
    profile_details = ProfileSerializer(source="profile", read_only=True)
    instructor_data = InstructorSerializer(source="instructor_record", read_only=True)

    class Meta:
        model = StaffMember
        fields = (
            "id",
            "profile",
            "profile_details",
            "employee_id",
            "designation",
            "department",
            "joining_date",
            "is_active",
            "qualification",
            "experience_years",
            "instructor_data",
        )


class InstructorOnboardingSerializer(serializers.Serializer):
    """
    Handles the 'hiring' phase of an instructor.
    Creates Profile -> StaffMember -> Instructor without a User account.
    """

    # Personal Info
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    last_name = serializers.CharField(max_length=100)
    gender = serializers.ChoiceField(
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")]
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_null=True)

    # Professional Info
    joining_date = serializers.DateField(required=False, allow_null=True)
    specialization = serializers.CharField(max_length=100, default="General")
    qualification = serializers.CharField(required=False, allow_blank=True)
    experience_years = serializers.IntegerField(required=False, default=0)
    bio = serializers.CharField(required=False, allow_blank=True)

    @transaction.atomic
    def create(self, validated_data):
        # 1. Create Identity Profile
        profile = Profile.objects.create(
            user_id=None,  # No login yet
            first_name=validated_data["first_name"],
            middle_name=validated_data.get("middle_name", ""),
            last_name=validated_data["last_name"],
            gender=validated_data["gender"],
            date_of_birth=validated_data.get("date_of_birth"),
            phone=validated_data.get("phone", ""),
            address=validated_data.get("address", ""),
            # Store email in profile mostly for contact reference, user email comes later
        )

        # 2. Create StaffMember Record
        # Generate a temporary or permanent Employee ID
        # Since we don't have a user ID yet, we use a random UUID segment
        emp_id = f"INS-{uuid.uuid4().hex[:8].upper()}"

        staff = StaffMember.objects.create(
            profile=profile,
            employee_id=emp_id,
            designation="Instructor",
            joining_date=validated_data.get("joining_date"),
            qualification=validated_data.get("qualification", ""),
            experience_years=validated_data.get("experience_years", 0),
        )

        # 3. Create Instructor Record
        instructor = Instructor.objects.create(
            staff_member=staff,
            specialization=validated_data.get("specialization", "General"),
            bio=validated_data.get("bio", ""),
        )

        return instructor


class InstructorActivationSerializer(serializers.Serializer):
    """
    Handles the 'IT Access' phase.
    Creates a User account and links it to an existing Staff/Instructor profile.
    """

    staff_id = serializers.UUIDField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)
    email = serializers.EmailField(required=False, allow_null=True)

    def validate_staff_id(self, value):
        if not StaffMember.objects.filter(id=value).exists():
            raise serializers.ValidationError("Staff member not found")
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
        staff_id = self.validated_data["staff_id"]
        provided_username = self.validated_data["username"]
        password = self.validated_data["password"]
        email = self.validated_data.get("email")

        staff = StaffMember.objects.select_related("profile").get(id=staff_id)
        profile = staff.profile

        if profile.user_id:
            raise serializers.ValidationError(
                "This instructor already has a user account."
            )

        # 1. Generate Usernames
        local_username = self._generate_unique_local_username(provided_username)
        global_username = self._generate_global_username(local_username)

        # 2. Create Global User
        user = User.objects.create_user(
            username=global_username,
            email=email or None,
            password=password,
            needs_password_change=True,
            initial_password_display=encrypt_secret(password),
        )

        # 2. Link Profile (Do this BEFORE assigning role to prevent Signal from creating a duplicate profile)
        profile.user_id = user.id
        profile.local_username = local_username
        profile.save()

        # 3. Assign Instructor Role
        from roles.models import Role, UserRole

        try:
            role = Role.objects.get(slug="instructor")
            UserRole.objects.create(
                user=user,
                role=role,
                is_active=True,
            )
        except Role.DoesNotExist:
            raise serializers.ValidationError(
                "Instructor role not found in the system."
            )

        return user


class StaffOnboardingSerializer(serializers.Serializer):
    """
    Handles the 'hiring' phase for General Staff (Non-Instructor).
    Creates Profile -> StaffMember.
    """

    # Personal Info
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    last_name = serializers.CharField(max_length=100)
    gender = serializers.ChoiceField(
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")]
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_null=True)

    # Professional Info
    designation = serializers.CharField(max_length=100)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    joining_date = serializers.DateField(required=False, allow_null=True)
    qualification = serializers.CharField(required=False, allow_blank=True)
    experience_years = serializers.IntegerField(required=False, default=0)

    @transaction.atomic
    def create(self, validated_data):
        # 1. Create Identity Profile
        profile = Profile.objects.create(
            user_id=None,
            first_name=validated_data["first_name"],
            middle_name=validated_data.get("middle_name", ""),
            last_name=validated_data["last_name"],
            gender=validated_data["gender"],
            date_of_birth=validated_data.get("date_of_birth"),
            phone=validated_data.get("phone", ""),
            address=validated_data.get("address", ""),
        )

        # 2. Create StaffMember Record
        emp_id = f"STF-{uuid.uuid4().hex[:8].upper()}"

        staff = StaffMember.objects.create(
            profile=profile,
            employee_id=emp_id,
            designation=validated_data["designation"],
            department=validated_data.get("department", ""),
            joining_date=validated_data.get("joining_date"),
            qualification=validated_data.get("qualification", ""),
            experience_years=validated_data.get("experience_years", 0),
        )

        return staff


class StaffActivationSerializer(serializers.Serializer):
    """
    Handles the 'IT Access' phase for General Staff.
    Creates User account + Assigns specific Role (e.g. Accountant, Librarian).
    """

    staff_id = serializers.UUIDField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128)
    role_slug = serializers.CharField(max_length=50)  # REQUIRED for general staff
    # TODO: Update to ListField(child=CharField) if multi-role selection is implemented in frontend activation table
    email = serializers.EmailField(required=False, allow_null=True)

    def validate_staff_id(self, value):
        if not StaffMember.objects.filter(id=value).exists():
            raise serializers.ValidationError("Staff member not found")
        return value

    def validate_role_slug(self, value):
        from roles.models import Role

        # Block 'instructor' and 'owner' from this specific generic endpoint to prevent misuse
        if value in ["instructor", "student"]:
            raise serializers.ValidationError(
                f"Invalid role selection: {value}. Use specific onboarding flows."
            )

        if not Role.objects.filter(slug=value).exists():
            raise serializers.ValidationError(f"Role '{value}' does not exist.")

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
        staff_id = self.validated_data["staff_id"]
        provided_username = self.validated_data["username"]
        password = self.validated_data["password"]
        role_slug = self.validated_data["role_slug"]
        email = self.validated_data.get("email")

        staff = StaffMember.objects.select_related("profile").get(id=staff_id)
        profile = staff.profile

        if profile.user_id:
            raise serializers.ValidationError(
                "This staff member already has a user account."
            )

        # 1. Generate Usernames
        local_username = self._generate_unique_local_username(provided_username)
        global_username = self._generate_global_username(local_username)

        # 2. Create Global User
        user = User.objects.create_user(
            username=global_username,
            email=email or None,
            password=password,
            needs_password_change=True,
            initial_password_display=encrypt_secret(password),
        )

        # 2. Link Profile (Do this BEFORE assigning role to prevent Signal from creating a duplicate profile)
        profile.user_id = user.id
        profile.local_username = local_username
        profile.save()

        # 3. Assign Selected Role
        from roles.models import Role, UserRole

        role = Role.objects.get(slug=role_slug)
        UserRole.objects.create(
            user=user,
            role=role,
            is_active=True,
        )

        return user


class StaffMemberUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating StaffMember and their underlying Profile.
    Accepts flat structure for Profile fields to match the frontend form.
    """

    # Personal Info (Mapped from Profile)
    first_name = serializers.CharField(source="profile.first_name", required=False)
    middle_name = serializers.CharField(
        source="profile.middle_name", required=False, allow_blank=True
    )
    last_name = serializers.CharField(source="profile.last_name", required=False)
    gender = serializers.CharField(source="profile.gender", required=False)
    date_of_birth = serializers.DateField(
        source="profile.date_of_birth", required=False, allow_null=True
    )
    phone = serializers.CharField(
        source="profile.phone", required=False, allow_blank=True
    )
    address = serializers.CharField(
        source="profile.address", required=False, allow_blank=True
    )
    email = serializers.EmailField(
        source="profile.email", required=False, allow_null=True
    )

    class Meta:
        model = StaffMember
        fields = (
            "id",
            "employee_id",
            "designation",
            "department",
            "joining_date",
            "qualification",
            "experience_years",
            # Profile fields
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "date_of_birth",
            "phone",
            "address",
            "email",
        )
        read_only_fields = ("id", "employee_id")

    @transaction.atomic
    def update(self, instance, validated_data):
        # DRF ungroups 'source="profile.xyz"' into a nested 'profile' dict
        profile_data = validated_data.pop("profile", {})

        # Update StaffMember fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update Profile fields
        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance


class InstructorDetailSerializer(InstructorSerializer):
    staff_member = StaffMemberSerializer(read_only=True)

    class Meta(InstructorSerializer.Meta):
        fields = "__all__"
