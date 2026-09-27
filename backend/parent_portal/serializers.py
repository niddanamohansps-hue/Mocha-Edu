"""
Own read-only serializers - deliberately not imported from
timetable.serializers / examinations.serializers, matching this codebase's
established convention of each TENANT_APP owning its own serializers rather
than cross-importing them (mirrors why services.py duplicates the small
identity helpers instead of importing them from a peer app).
"""

from rest_framework import serializers

from examinations.models import ExamResult
from timetable.models import TimetableEntry


class ChildTimetableEntrySerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    instructor_name = serializers.SerializerMethodField()
    room_name = serializers.CharField(source="room.name", read_only=True)
    period_name = serializers.CharField(source="period.name", read_only=True)
    period_order = serializers.IntegerField(source="period.order", read_only=True)
    day_of_week_display = serializers.CharField(
        source="get_day_of_week_display", read_only=True
    )

    class Meta:
        model = TimetableEntry
        fields = [
            "id",
            "day_of_week",
            "day_of_week_display",
            "period",
            "period_name",
            "period_order",
            "subject",
            "subject_name",
            "instructor_name",
            "room",
            "room_name",
        ]
        read_only_fields = fields

    def get_instructor_name(self, obj):
        if not obj.instructor_id:
            return None
        profile = obj.instructor.staff_member.profile
        return f"{profile.first_name} {profile.last_name}"


class ChildExamResultSerializer(serializers.ModelSerializer):
    examination_name = serializers.CharField(source="examination.name", read_only=True)

    class Meta:
        model = ExamResult
        fields = [
            "id",
            "examination",
            "examination_name",
            "academic_year",
            "total_marks_obtained",
            "total_max_marks",
            "percentage",
            "overall_grade",
            "is_pass",
            "subject_breakdown",
            "published_at",
        ]
        read_only_fields = fields
