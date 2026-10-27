from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import (
    ExamMark,
    ExamResult,
    ExamSchedule,
    Examination,
    ExamType,
    GradeBoundary,
)
from .services import validate_exam_schedule


class ExamTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamType
        fields = ["id", "name", "order", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExaminationSerializer(serializers.ModelSerializer):
    exam_type_name = serializers.CharField(source="exam_type.name", read_only=True)

    class Meta:
        model = Examination
        fields = [
            "id", "academic_year", "name", "exam_type", "exam_type_name",
            "start_date", "end_date", "is_published", "published_at", "publication_requested_by_user_id",
            "publication_requested_at", "published_by_user_id", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_published", "published_at", "publication_requested_by_user_id",
                            "publication_requested_at", "published_by_user_id", "created_at", "updated_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": "End date must be on or after the start date."})
        return attrs


class ExamScheduleSerializer(serializers.ModelSerializer):
    """Read shape."""

    subject_name = serializers.CharField(source="subject.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    room_name = serializers.CharField(source="room.name", read_only=True)
    period_name = serializers.CharField(source="period.name", read_only=True)
    examination_name = serializers.CharField(source="examination.name", read_only=True)

    class Meta:
        model = ExamSchedule
        fields = [
            "id", "examination", "examination_name", "academic_year", "subject", "subject_name",
            "section", "section_name", "date", "start_time", "end_time", "period", "period_name",
            "room", "room_name", "max_marks", "pass_marks", "is_locked", "locked_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_locked", "locked_at", "created_at", "updated_at"]


class ExamScheduleCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamSchedule
        fields = [
            "id", "examination", "academic_year", "subject", "section", "date",
            "start_time", "end_time", "period", "room", "max_marks", "pass_marks",
        ]
        read_only_fields = ["id"]
        # DRF auto-generates a UniqueTogetherValidator from unique_together,
        # which would fire before validate() and produce a generic message -
        # our own validate_exam_schedule() + the conflict checks it runs
        # already cover this with clear, specific errors (same reasoning as
        # timetable.serializers.TimetableEntryCreateUpdateSerializer).
        validators = []

    def validate(self, attrs):
        instance = self.instance
        examination = attrs.get("examination", getattr(instance, "examination", None))
        subject = attrs.get("subject", getattr(instance, "subject", None))
        section = attrs.get("section", getattr(instance, "section", None))
        academic_year = attrs.get("academic_year", getattr(instance, "academic_year", None))
        date = attrs.get("date", getattr(instance, "date", None))
        start_time = attrs.get("start_time", getattr(instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(instance, "end_time", None))
        period = attrs.get("period", getattr(instance, "period", None))
        room = attrs.get("room", getattr(instance, "room", None))
        max_marks = attrs.get("max_marks", getattr(instance, "max_marks", None))
        pass_marks = attrs.get("pass_marks", getattr(instance, "pass_marks", None))

        if max_marks is not None and pass_marks is not None and pass_marks > max_marks:
            raise serializers.ValidationError({"pass_marks": "Pass marks cannot exceed maximum marks."})

        if examination.is_published:
            raise serializers.ValidationError(
                {"non_field_errors": ["This examination is already published and cannot be modified."]}
            )

        validate_exam_schedule(
            examination=examination, subject=subject, section=section, academic_year=academic_year,
            date=date, start_time=start_time, end_time=end_time, period=period, room=room,
            exclude_id=instance.id if instance else None,
        )
        return attrs

    def create(self, validated_data):
        try:
            return ExamSchedule.objects.create(**validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {"non_field_errors": ["A schedule already exists for this examination/subject/section."]}
            )


class ExamMarkRecordInputSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    marks_obtained = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    is_absent = serializers.BooleanField(default=False)
    remarks = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs.get("is_absent"):
            attrs["marks_obtained"] = None
        return attrs


class ExamMarkSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)

    class Meta:
        model = ExamMark
        fields = [
            "id", "student", "student_name", "enrollment_id", "marks_obtained",
            "is_absent", "remarks", "entered_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "entered_by", "created_at", "updated_at"]

    def get_student_name(self, obj):
        profile = obj.student.profile
        return f"{profile.first_name} {profile.last_name}"


class ExamMarkBulkSerializer(serializers.Serializer):
    """
    Bulk create/upsert for one ExamSchedule's marks. Full pre-validation
    before any write; the entire batch is rejected if one record is invalid.
    Resubmission updates existing rows rather than creating duplicates -
    exact same shape/behavior as attendance's bulk session serializer.
    """

    records = ExamMarkRecordInputSerializer(many=True)

    def __init__(self, *args, exam_schedule=None, **kwargs):
        self._exam_schedule = exam_schedule
        super().__init__(*args, **kwargs)

    def validate_records(self, records):
        if not records:
            raise serializers.ValidationError("At least one record is required.")

        seen = set()
        for record in records:
            student_id = str(record["student"])
            if student_id in seen:
                raise serializers.ValidationError(
                    f"Duplicate entry for student {student_id} in the same submission."
                )
            seen.add(student_id)

            marks = record.get("marks_obtained")
            if marks is not None:
                if marks < 0:
                    raise serializers.ValidationError(f"Marks for student {student_id} cannot be negative.")
                if marks > self._exam_schedule.max_marks:
                    raise serializers.ValidationError(
                        f"Marks for student {student_id} cannot exceed the maximum marks "
                        f"({self._exam_schedule.max_marks})."
                    )

        from .services import get_section_roster_student_ids

        roster_ids = get_section_roster_student_ids(self._exam_schedule.section_id)
        invalid = seen - roster_ids
        if invalid:
            raise serializers.ValidationError(
                f"Student(s) {sorted(invalid)} are not currently enrolled in this section - "
                f"nothing was saved."
            )
        return records

    @transaction.atomic
    def save(self, entered_by):
        records = self.validated_data["records"]
        existing = {
            str(m.student_id): m for m in ExamMark.objects.filter(exam_schedule=self._exam_schedule)
        }

        to_create, to_update = [], []
        for record in records:
            student_id = str(record["student"])
            if student_id in existing:
                row = existing[student_id]
                row.marks_obtained = record.get("marks_obtained")
                row.is_absent = record["is_absent"]
                row.remarks = record.get("remarks", "")
                row.entered_by = entered_by
                to_update.append(row)
            else:
                to_create.append(
                    ExamMark(
                        exam_schedule=self._exam_schedule,
                        student_id=student_id,
                        marks_obtained=record.get("marks_obtained"),
                        is_absent=record["is_absent"],
                        remarks=record.get("remarks", ""),
                        entered_by=entered_by,
                    )
                )

        if to_create:
            ExamMark.objects.bulk_create(to_create)
        if to_update:
            ExamMark.objects.bulk_update(
                to_update, ["marks_obtained", "is_absent", "remarks", "entered_by", "updated_at"]
            )

        absent_count = sum(1 for r in records if r["is_absent"])
        return {
            "created": len(to_create),
            "updated": len(to_update),
            "absent": absent_count,
            "total": len(records),
        }


class ExamResultSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = ExamResult
        fields = [
            "id", "examination", "student", "student_name", "academic_year",
            "total_marks_obtained", "total_max_marks", "percentage", "overall_grade",
            "is_pass", "subject_breakdown", "published_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        profile = obj.student.profile
        return f"{profile.first_name} {profile.last_name}"


class GradeBoundarySerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeBoundary
        fields = [
            "id", "academic_year", "min_percentage", "max_percentage",
            "grade_label", "grade_point", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = GradeBoundary(
            id=self.instance.id if self.instance else None,
            academic_year=attrs.get("academic_year", getattr(self.instance, "academic_year", None)),
            min_percentage=attrs.get("min_percentage", getattr(self.instance, "min_percentage", None)),
            max_percentage=attrs.get("max_percentage", getattr(self.instance, "max_percentage", None)),
            grade_label=attrs.get("grade_label", getattr(self.instance, "grade_label", "")),
        )
        try:
            instance.clean()
        except Exception as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else {"non_field_errors": exc.messages}
            )
        return attrs

    def create(self, validated_data):
        return GradeBoundary.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
