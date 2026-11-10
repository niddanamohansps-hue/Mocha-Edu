from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import AcademicYear, CalendarEvent, Program, AcademicLevel, Section, Subject, SubjectAssignment
from staff.serializers import InstructorSerializer


class SectionSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    program_name = serializers.CharField(source="level.program.name", read_only=True)

    class Meta:
        model = Section
        fields = [
            "id",
            "level",
            "level_name",
            "program_name",
            "name",
            "capacity",
        ]


class AcademicLevelSerializer(serializers.ModelSerializer):
    sections = SectionSerializer(many=True, read_only=True)
    program_name = serializers.CharField(source="program.name", read_only=True)

    class Meta:
        model = AcademicLevel
        fields = [
            "id",
            "program",
            "program_name",
            "name",
            "order",
            "sections",
        ]


class ProgramSerializer(serializers.ModelSerializer):
    levels = AcademicLevelSerializer(many=True, read_only=True)

    class Meta:
        model = Program
        fields = [
            "id",
            "name",
            "code",
            "description",
            "is_active",
            "created_at",
            "levels",
        ]


class SubjectSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)

    class Meta:
        model = Subject
        fields = [
            "id",
            "level",
            "level_name",
            "name",
            "code",
            "credits",
            "is_elective",
            "description",
        ]


class SubjectAssignmentSerializer(serializers.ModelSerializer):
    subject_details = SubjectSerializer(source="subject", read_only=True)
    section_details = SectionSerializer(source="section", read_only=True)
    instructor_details = InstructorSerializer(source="instructor", read_only=True)

    class Meta:
        model = SubjectAssignment
        fields = [
            "id",
            "section",
            "section_details",
            "subject",
            "subject_details",
            "instructor",
            "instructor_details",
        ]


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ("id", "name", "start_date", "end_date", "is_current", "created_at", "updated_at")
        read_only_fields = ("id", "is_current", "created_at", "updated_at")

    def validate(self, attrs):
        instance = AcademicYear(
            pk=getattr(self.instance, "pk", None),
            name=attrs.get("name", getattr(self.instance, "name", "")),
            start_date=attrs.get("start_date", getattr(self.instance, "start_date", None)),
            end_date=attrs.get("end_date", getattr(self.instance, "end_date", None)),
        )
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        # Two sessions may not share a day: attendance, fees and exams are filed by the date's academic year.
        # Checked here (inside the school's schema) rather than in clean(), which validates the year on its own.
        clash = (
            AcademicYear.objects.filter(start_date__lte=instance.end_date, end_date__gte=instance.start_date)
            .exclude(pk=instance.pk)
            .order_by("start_date")
            .first()
        )
        if clash:
            raise serializers.ValidationError(
                {"start_date": f"These dates overlap {clash.name} ({clash.start_date:%d %b %Y} – {clash.end_date:%d %b %Y})."}
            )
        return attrs

    def validate_name(self, value):
        qs = AcademicYear.objects.filter(name=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("An academic year with this name already exists.")
        return value


class CalendarEventSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    event_type_display = serializers.CharField(source="get_event_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    audience_display = serializers.CharField(source="get_audience_display", read_only=True)

    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "title",
            "description",
            "event_type",
            "event_type_display",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "is_all_day",
            "is_holiday",
            "status",
            "status_display",
            "academic_year",
            "academic_year_name",
            "location",
            "audience",
            "audience_display",
            "created_by_id",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by_id",
            "created_by_username",
            "created_at",
            "updated_at",
            "academic_year_name",
            "event_type_display",
            "status_display",
            "audience_display",
        ]

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        if "event_type" in data and isinstance(data["event_type"], str):
            data["event_type"] = data["event_type"].upper()
        if "status" in data and isinstance(data["status"], str):
            data["status"] = data["status"].upper()
        if "audience" in data and isinstance(data["audience"], str):
            data["audience"] = data["audience"].upper()
        return super().to_internal_value(data)

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        is_all_day = attrs.get("is_all_day", getattr(self.instance, "is_all_day", True))
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        event_type = attrs.get("event_type", getattr(self.instance, "event_type", "ACADEMIC"))

        instance = CalendarEvent(
            title=attrs.get("title", getattr(self.instance, "title", "")),
            start_date=start_date,
            end_date=end_date,
            is_all_day=is_all_day,
            start_time=start_time,
            end_time=end_time,
            event_type=event_type,
        )
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)

        if instance.is_holiday:
            attrs["is_holiday"] = True
        return attrs

