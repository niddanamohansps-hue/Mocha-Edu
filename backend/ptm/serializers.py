from rest_framework import serializers

from academics.models import AcademicLevel, AcademicYear, Section
from families.models import Parent
from staff.models import StaffMember
from students.models import Student

from .models import PTMSession, PTMSlot


class StaffMemberBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffMember
        fields = ["id", "employee_id", "designation", "department", "full_name"]

    def get_full_name(self, obj):
        if hasattr(obj, "profile") and obj.profile:
            return f"{obj.profile.first_name} {obj.profile.last_name}".strip()
        return obj.employee_id


class StudentBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    current_class = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ["id", "enrollment_id", "full_name", "current_class"]

    def get_full_name(self, obj):
        if hasattr(obj, "profile") and obj.profile:
            return f"{obj.profile.first_name} {obj.profile.last_name}".strip()
        return obj.enrollment_id

    def get_current_class(self, obj):
        enrollment = obj.enrollments.filter(is_current=True).first()
        if enrollment:
            sec_name = f" - {enrollment.section.name}" if enrollment.section else ""
            return f"{enrollment.level.name}{sec_name}"
        return ""


class ParentBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()

    class Meta:
        model = Parent
        fields = ["id", "full_name", "phone_number"]

    def get_full_name(self, obj):
        if hasattr(obj, "profile") and obj.profile:
            return f"{obj.profile.first_name} {obj.profile.last_name}".strip()
        return ""

    def get_phone_number(self, obj):
        if hasattr(obj, "profile") and obj.profile:
            return getattr(obj.profile, "phone", "")
        return ""


class PTMSlotSerializer(serializers.ModelSerializer):
    teacher_detail = StaffMemberBriefSerializer(source="teacher", read_only=True)
    student_detail = StudentBriefSerializer(source="student", read_only=True)
    parent_detail = ParentBriefSerializer(source="booked_by_parent", read_only=True)

    class Meta:
        model = PTMSlot
        fields = [
            "id",
            "session",
            "teacher",
            "teacher_detail",
            "start_time",
            "end_time",
            "status",
            "student",
            "student_detail",
            "booked_by_parent",
            "parent_detail",
            "booked_at",
            "parent_notes",
            "teacher_feedback",
            "attended",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "session",
            "teacher",
            "start_time",
            "end_time",
            "status",
            "student",
            "booked_by_parent",
            "booked_at",
            "created_at",
            "updated_at",
        ]


class PTMSessionSerializer(serializers.ModelSerializer):
    teachers_detail = StaffMemberBriefSerializer(
        source="teachers", many=True, read_only=True
    )
    teacher_ids = serializers.PrimaryKeyRelatedField(
        queryset=StaffMember.objects.filter(is_active=True),
        many=True,
        write_only=True,
        source="teachers",
        required=False,
    )
    level_name = serializers.CharField(source="level.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )
    total_slots = serializers.IntegerField(read_only=True)
    booked_slots_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = PTMSession
        fields = [
            "id",
            "title",
            "academic_year",
            "academic_year_name",
            "meeting_date",
            "start_time",
            "end_time",
            "slot_duration_minutes",
            "buffer_minutes",
            "mode",
            "location_or_url",
            "level",
            "level_name",
            "section",
            "section_name",
            "teachers",
            "teachers_detail",
            "teacher_ids",
            "status",
            "instructions",
            "total_slots",
            "booked_slots_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        start_time = attrs.get(
            "start_time", getattr(self.instance, "start_time", None)
        )
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        slot_duration = attrs.get(
            "slot_duration_minutes",
            getattr(self.instance, "slot_duration_minutes", 10),
        )

        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError(
                {"end_time": "Meeting end time must be after start time."}
            )

        if slot_duration and slot_duration <= 0:
            raise serializers.ValidationError(
                {"slot_duration_minutes": "Slot duration must be positive."}
            )

        return attrs


class PTMSlotBookingRequestSerializer(serializers.Serializer):
    slot_id = serializers.UUIDField(required=True)
    student_id = serializers.UUIDField(required=True)
    notes = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, default=""
    )


class PTMSlotFeedbackRequestSerializer(serializers.Serializer):
    feedback = serializers.CharField(
        required=False, allow_blank=True, max_length=2000, default=""
    )
    attended = serializers.BooleanField(required=False, default=True)
