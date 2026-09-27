from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Period, Room, TimetableEntry, TimetableSubstitution
from .services import check_entry_conflicts, validate_substitution, validate_timetable_entry


class PeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Period
        fields = [
            "id",
            "academic_year",
            "name",
            "order",
            "start_time",
            "end_time",
            "is_break",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "name", "capacity", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class TimetableEntrySerializer(serializers.ModelSerializer):
    """Read shape - used for list/retrieve and the section/instructor weekly views."""

    section_name = serializers.CharField(source="section.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    instructor_name = serializers.SerializerMethodField()
    room_name = serializers.CharField(source="room.name", read_only=True)
    period_name = serializers.CharField(source="period.name", read_only=True)
    period_order = serializers.IntegerField(source="period.order", read_only=True)
    day_of_week_display = serializers.CharField(source="get_day_of_week_display", read_only=True)

    class Meta:
        model = TimetableEntry
        fields = [
            "id",
            "academic_year",
            "section",
            "section_name",
            "subject",
            "subject_name",
            "instructor",
            "instructor_name",
            "room",
            "room_name",
            "day_of_week",
            "day_of_week_display",
            "period",
            "period_name",
            "period_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_instructor_name(self, obj):
        if not obj.instructor_id:
            return None
        profile = obj.instructor.staff_member.profile
        return f"{profile.first_name} {profile.last_name}"


class TimetableEntryCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableEntry
        fields = ["id", "academic_year", "section", "subject", "instructor", "room", "day_of_week", "period"]
        read_only_fields = ["id"]
        # DRF auto-generates UniqueTogetherValidators from unique_together,
        # which would fire before our own validate() and produce a generic
        # "must make a unique set" message. check_entry_conflicts() below
        # already covers all three constraints with clear, specific errors,
        # and the DB constraints themselves remain the final protection.
        validators = []

    def validate(self, attrs):
        instance = self.instance
        section = attrs.get("section", getattr(instance, "section", None))
        subject = attrs.get("subject", getattr(instance, "subject", None))
        period = attrs.get("period", getattr(instance, "period", None))
        academic_year = attrs.get("academic_year", getattr(instance, "academic_year", None))
        instructor = attrs.get("instructor", getattr(instance, "instructor", None))
        room = attrs.get("room", getattr(instance, "room", None))
        day_of_week = attrs.get("day_of_week", getattr(instance, "day_of_week", None))

        validate_timetable_entry(
            section=section, subject=subject, period=period, academic_year=academic_year, instructor=instructor
        )
        check_entry_conflicts(
            section=section,
            instructor=instructor,
            room=room,
            academic_year=academic_year,
            day_of_week=day_of_week,
            period=period,
            exclude_id=instance.id if instance else None,
        )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        try:
            return TimetableEntry.objects.create(**validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {"non_field_errors": ["This slot is already taken. Please choose a different period, room, or instructor."]}
            )

    @transaction.atomic
    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {"non_field_errors": ["This slot is already taken. Please choose a different period, room, or instructor."]}
            )
        return instance


class TimetableSubstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableSubstitution
        fields = [
            "id",
            "timetable_entry",
            "date",
            "substitute_instructor",
            "reason",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]
        # Same reasoning as TimetableEntryCreateUpdateSerializer above - our
        # own validate() produces the clear "already exists" message.
        validators = []

    def validate(self, attrs):
        timetable_entry = attrs.get("timetable_entry", getattr(self.instance, "timetable_entry", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        substitute_instructor = attrs.get(
            "substitute_instructor", getattr(self.instance, "substitute_instructor", None)
        )

        existing = TimetableSubstitution.objects.filter(timetable_entry=timetable_entry, date=date)
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise serializers.ValidationError(
                {"non_field_errors": ["A substitution already exists for this entry on this date."]}
            )

        validate_substitution(
            timetable_entry=timetable_entry, date=date, substitute_instructor=substitute_instructor
        )
        return attrs
