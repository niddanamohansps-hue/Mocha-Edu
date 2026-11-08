from django.db import IntegrityError
from rest_framework import serializers

from .models import (
    CoScholasticActivity,
    CoScholasticGrade,
    ExamComponentMark,
    ExamMark,
    ExamMarkChange,
    ExamResult,
    ExamSchedule,
    ExamScheduleComponent,
    Examination,
    ExamType,
    GradeBoundary,
    RecheckRequest,
    TermWeightage,
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
            "publication_requested_at", "published_by_user_id", "date_sheet_published_at", "date_sheet_version",
            "marks_due_date", "supplementary_of", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_published", "published_at", "publication_requested_by_user_id",
                            "publication_requested_at", "published_by_user_id", "date_sheet_published_at",
                            "date_sheet_version", "supplementary_of", "created_at", "updated_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"end_date": "End date must be on or after the start date."})
        return attrs


class ExamScheduleComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamScheduleComponent
        fields = [
            "id", "exam_schedule", "name", "code", "max_marks", "pass_marks",
            "is_theory", "requires_separate_pass", "order", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = ExamScheduleComponent(
            id=self.instance.id if self.instance else None,
            exam_schedule=attrs.get("exam_schedule", getattr(self.instance, "exam_schedule", None)),
            name=attrs.get("name", getattr(self.instance, "name", "")),
            code=attrs.get("code", getattr(self.instance, "code", "")),
            max_marks=attrs.get("max_marks", getattr(self.instance, "max_marks", None)),
            pass_marks=attrs.get("pass_marks", getattr(self.instance, "pass_marks", None)),
            is_theory=attrs.get("is_theory", getattr(self.instance, "is_theory", True)),
            requires_separate_pass=attrs.get("requires_separate_pass", getattr(self.instance, "requires_separate_pass", False)),
            order=attrs.get("order", getattr(self.instance, "order", 0)),
        )
        try:
            instance.clean()
        except Exception as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else {"non_field_errors": exc.messages}
            )
        return attrs


class ExamScheduleSerializer(serializers.ModelSerializer):
    """Read shape."""

    subject_name = serializers.CharField(source="subject.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    room_name = serializers.CharField(source="room.name", read_only=True)
    period_name = serializers.CharField(source="period.name", read_only=True)
    examination_name = serializers.CharField(source="examination.name", read_only=True)
    components = ExamScheduleComponentSerializer(many=True, read_only=True)

    class Meta:
        model = ExamSchedule
        fields = [
            "id", "examination", "examination_name", "academic_year", "subject", "subject_name",
            "section", "section_name", "date", "start_time", "end_time", "period", "period_name",
            "room", "room_name", "max_marks", "pass_marks", "is_locked", "locked_at",
            "components", "created_at", "updated_at",
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


class StudentComponentMarkInputSerializer(serializers.Serializer):
    component = serializers.UUIDField()
    marks_obtained = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    is_absent = serializers.BooleanField(default=False)


class ExamMarkRecordInputSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    marks_obtained = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    is_absent = serializers.BooleanField(default=False)
    # Optional; older clients send only is_absent. See marks.normalise_record.
    attendance = serializers.ChoiceField(choices=ExamMark.Attendance.choices, required=False)
    remarks = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    components = StudentComponentMarkInputSerializer(many=True, required=False)

    def validate(self, attrs):
        from .marks import normalise_record

        return normalise_record(attrs)


class ExamComponentMarkSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source="component.name", read_only=True)
    component_code = serializers.CharField(source="component.code", read_only=True)
    max_marks = serializers.DecimalField(source="component.max_marks", max_digits=6, decimal_places=2, read_only=True)
    pass_marks = serializers.DecimalField(source="component.pass_marks", max_digits=6, decimal_places=2, read_only=True)
    requires_separate_pass = serializers.BooleanField(source="component.requires_separate_pass", read_only=True)

    class Meta:
        model = ExamComponentMark
        fields = [
            "id", "mark", "component", "component_name", "component_code",
            "max_marks", "pass_marks", "requires_separate_pass",
            "marks_obtained", "is_absent", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExamMarkSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)
    component_marks = ExamComponentMarkSerializer(many=True, read_only=True)

    class Meta:
        model = ExamMark
        fields = [
            "id", "student", "student_name", "enrollment_id", "marks_obtained",
            "is_absent", "attendance", "grace_marks", "remarks", "entered_by",
            "component_marks", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "entered_by", "grace_marks", "created_at", "updated_at"]

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
    # Why marks changed; required when changing entered marks on a locked schedule.
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def __init__(self, *args, exam_schedule=None, **kwargs):
        self._exam_schedule = exam_schedule
        super().__init__(*args, **kwargs)

    def validate_records(self, records):
        if not records:
            raise serializers.ValidationError("At least one record is required.")

        schedule_components = {}
        if self._exam_schedule:
            schedule_components = {str(c.id): c for c in self._exam_schedule.components.all()}

        seen = set()
        for record in records:
            student_id = str(record["student"])
            if student_id in seen:
                raise serializers.ValidationError(
                    f"Duplicate entry for student {student_id} in the same submission."
                )
            seen.add(student_id)

            if "components" in record:
                for c_data in record["components"]:
                    cid = str(c_data["component"])
                    if schedule_components and cid not in schedule_components:
                        raise serializers.ValidationError(
                            f"Component {cid} does not belong to this exam schedule."
                        )
                    comp = schedule_components.get(cid)
                    c_marks = c_data.get("marks_obtained")
                    if c_marks is not None:
                        if c_marks < 0:
                            raise serializers.ValidationError(f"Component marks for student {student_id} cannot be negative.")
                        if comp and c_marks > comp.max_marks:
                            raise serializers.ValidationError(
                                f"Component '{comp.name}' marks for student {student_id} ({c_marks}) "
                                f"cannot exceed maximum marks ({comp.max_marks})."
                            )

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

        if self._exam_schedule.examination.supplementary_of_id:
            # A re-sit paper takes marks only for the students entitled to re-sit this subject.
            from .supplementary import candidate_student_ids

            entitled = candidate_student_ids(self._exam_schedule.examination_id, self._exam_schedule.subject_id)
            invalid = seen - entitled
            if invalid:
                raise serializers.ValidationError(
                    f"Student(s) {sorted(invalid)} are not entitled to this supplementary paper - nothing was saved."
                )
            return records

        roster_ids = get_section_roster_student_ids(self._exam_schedule.section_id)
        invalid = seen - roster_ids
        if invalid:
            raise serializers.ValidationError(
                f"Student(s) {sorted(invalid)} are not currently enrolled in this section - "
                f"nothing was saved."
            )
        return records

    def save(self, entered_by, user_id=None, require_reason=False):
        from .marks import record_marks

        return record_marks(
            self._exam_schedule, self.validated_data["records"], entered_by=entered_by, user_id=user_id,
            reason=self.validated_data.get("reason", ""), require_reason=require_reason,
        )


class ExamMarkChangeSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    enrollment_id = serializers.CharField(source="mark.student.enrollment_id", read_only=True)
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = ExamMarkChange
        fields = [
            "id", "mark", "kind", "student_name", "enrollment_id", "old_marks", "new_marks", "old_attendance",
            "new_attendance", "old_grace", "new_grace", "reason", "changed_by", "created_at",
        ]

    def get_student_name(self, obj):
        profile = obj.mark.student.profile
        return f"{profile.first_name} {profile.last_name}"

    def get_changed_by(self, obj):
        return self.context.get("names", {}).get(str(obj.changed_by_user_id), "")


class RecheckRequestSerializer(serializers.ModelSerializer):
    student = serializers.UUIDField(source="mark.student_id", read_only=True)
    student_name = serializers.SerializerMethodField()
    enrollment_id = serializers.CharField(source="mark.student.enrollment_id", read_only=True)
    subject_name = serializers.CharField(source="mark.exam_schedule.subject.name", read_only=True)
    examination_name = serializers.CharField(source="mark.exam_schedule.examination.name", read_only=True)
    max_marks = serializers.DecimalField(source="mark.exam_schedule.max_marks", max_digits=6, decimal_places=2, read_only=True)
    current_marks = serializers.DecimalField(source="mark.marks_obtained", max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = RecheckRequest
        fields = [
            "id", "mark", "student", "student_name", "enrollment_id", "subject_name", "examination_name", "max_marks",
            "current_marks", "status", "reason", "original_marks", "revised_marks", "decision_comment",
            "fee_amount", "fee_paid_at", "fee_reference", "created_at", "decided_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        profile = obj.mark.student.profile
        return f"{profile.first_name} {profile.last_name}"


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


class TermWeightageSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    examination_name = serializers.CharField(source="examination.name", read_only=True)

    class Meta:
        model = TermWeightage
        fields = [
            "id", "academic_year", "level", "level_name", "examination",
            "examination_name", "weightage_percentage", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = TermWeightage(
            id=self.instance.id if self.instance else None,
            academic_year=attrs.get("academic_year", getattr(self.instance, "academic_year", "")),
            level=attrs.get("level", getattr(self.instance, "level", None)),
            examination=attrs.get("examination", getattr(self.instance, "examination", None)),
            weightage_percentage=attrs.get("weightage_percentage", getattr(self.instance, "weightage_percentage", None)),
        )
        try:
            instance.clean()
        except Exception as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else {"non_field_errors": exc.messages}
            )
        return attrs


class CoScholasticActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = CoScholasticActivity
        fields = ["id", "name", "code", "description", "order", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CoScholasticGradeSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)
    examination_name = serializers.CharField(source="examination.name", read_only=True)
    activity_name = serializers.CharField(source="activity.name", read_only=True)
    activity_code = serializers.CharField(source="activity.code", read_only=True)

    class Meta:
        model = CoScholasticGrade
        fields = [
            "id", "student", "student_name", "enrollment_id", "examination",
            "examination_name", "activity", "activity_name", "activity_code",
            "grade", "remarks", "recorded_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at", "updated_at"]

    def get_student_name(self, obj):
        profile = obj.student.profile
        return f"{profile.first_name} {profile.last_name}"


class SingleCoScholasticGradeInputSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    activity = serializers.UUIDField()
    grade = serializers.CharField(max_length=10)
    remarks = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class BulkCoScholasticGradeEntrySerializer(serializers.Serializer):
    examination = serializers.UUIDField()
    records = SingleCoScholasticGradeInputSerializer(many=True)

    def validate_records(self, records):
        if not records:
            raise serializers.ValidationError("At least one grade record is required.")
        return records
