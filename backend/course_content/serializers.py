from rest_framework import serializers
from .models import CourseContent, SubjectEnrollment, Assignment, AssignmentSubmission
from django.utils import timezone


class CourseContentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.profile.full_name", read_only=True
    )
    content_type_display = serializers.CharField(
        source="get_content_type_display", read_only=True
    )
    file_size = serializers.SerializerMethodField()

    # Target details for display
    target_programs_details = serializers.SerializerMethodField()
    target_levels_details = serializers.SerializerMethodField()
    target_sections_details = serializers.SerializerMethodField()
    target_subjects_details = serializers.SerializerMethodField()

    class Meta:
        model = CourseContent
        fields = [
            "id",
            "title",
            "description",
            "content_type",
            "content_type_display",
            "file",
            "file_size",
            "external_url",
            "created_by",
            "created_by_name",
            "target_programs",
            "target_programs_details",
            "target_levels",
            "target_levels_details",
            "target_sections",
            "target_sections_details",
            "target_subjects",
            "target_subjects_details",
            "specific_students",
            "is_published",
            "publish_date",
            "is_pinned",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_file_size(self, obj):
        if obj.file:
            try:
                return obj.file.size
            except (FileNotFoundError, OSError):
                # File reference exists in DB but file is missing on disk
                return None
        return None

    def get_target_programs_details(self, obj):
        return [{"id": p.id, "name": p.name} for p in obj.target_programs.all()]

    def get_target_levels_details(self, obj):
        return [
            {"id": l.id, "name": l.name, "program": l.program.name}
            for l in obj.target_levels.all()
        ]

    def get_target_sections_details(self, obj):
        return [
            {"id": s.id, "name": s.name, "level": s.level.name}
            for s in obj.target_sections.all()
        ]

    def get_target_subjects_details(self, obj):
        return [
            {"id": s.id, "name": s.name, "code": s.code}
            for s in obj.target_subjects.all()
        ]

    def validate_file(self, value):
        """Validate file size (max 10MB)"""
        if value and value.size > 10 * 1024 * 1024:  # 10MB
            raise serializers.ValidationError("File size must not exceed 10MB")
        return value

    def validate(self, data):
        """Ensure either file or external_url is provided for non-assignment content"""
        content_type = data.get("content_type")
        file = data.get("file")
        external_url = data.get("external_url")

        if content_type == "link" and not external_url:
            raise serializers.ValidationError(
                "External URL is required for link type content"
            )

        if (
            content_type in ["note", "document", "video"]
            and not file
            and not external_url
        ):
            raise serializers.ValidationError("Either file or external URL is required")

        return data


class SubjectEnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source="student.profile.full_name", read_only=True
    )
    student_enrollment_id = serializers.CharField(
        source="student.enrollment_id", read_only=True
    )
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)

    class Meta:
        model = SubjectEnrollment
        fields = [
            "id",
            "student",
            "student_name",
            "student_enrollment_id",
            "subject",
            "subject_name",
            "subject_code",
            "academic_year",
            "enrolled_at",
        ]
        read_only_fields = ["enrolled_at"]


class AssignmentSerializer(serializers.ModelSerializer):
    content_details = CourseContentSerializer(source="content", read_only=True)
    submission_type_display = serializers.CharField(
        source="get_submission_type_display", read_only=True
    )
    is_overdue = serializers.SerializerMethodField()
    total_submissions = serializers.SerializerMethodField()
    graded_submissions = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "content",
            "content_details",
            "due_date",
            "total_points",
            "submission_type",
            "submission_type_display",
            "allow_late_submission",
            "late_penalty_percent",
            "instructions",
            "is_overdue",
            "total_submissions",
            "graded_submissions",
        ]

    def get_is_overdue(self, obj):
        return timezone.now() > obj.due_date

    def get_total_submissions(self, obj):
        return (
            obj.submissions.filter(status="submitted").count()
            + obj.submissions.filter(status="graded").count()
        )

    def get_graded_submissions(self, obj):
        return obj.submissions.filter(status="graded").count()


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source="student.profile.full_name", read_only=True
    )
    student_enrollment_id = serializers.CharField(
        source="student.enrollment_id", read_only=True
    )
    assignment_title = serializers.CharField(
        source="assignment.content.title", read_only=True
    )
    graded_by_name = serializers.CharField(
        source="graded_by.profile.full_name", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_late = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id",
            "assignment",
            "assignment_title",
            "student",
            "student_name",
            "student_enrollment_id",
            "submitted_at",
            "submission_file",
            "submission_text",
            "submission_url",
            "status",
            "status_display",
            "score",
            "feedback",
            "graded_by",
            "graded_by_name",
            "graded_at",
            "is_late",
            "created_at",
            "updated_at",
        ]
        # Presentation only. Students submit through SubmitAssignmentSerializer and graders grade
        # through GradeSubmissionSerializer, so no field here is writable (a submission route must
        # never be able to change a score, feedback, status or grading metadata).
        read_only_fields = fields


class CreateAssignmentSerializer(serializers.Serializer):
    """
    Serializer for creating an assignment with its base content
    """

    # Content fields
    title = serializers.CharField(max_length=200)
    description = serializers.CharField()
    file = serializers.FileField(required=False, allow_null=True)
    external_url = serializers.URLField(required=False, allow_blank=True)

    # Targeting
    target_programs = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    target_levels = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    target_sections = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    target_subjects = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    specific_students = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )

    is_published = serializers.BooleanField(default=True)
    is_pinned = serializers.BooleanField(default=False)

    # Assignment-specific fields
    due_date = serializers.DateTimeField()
    total_points = serializers.DecimalField(max_digits=5, decimal_places=2, default=100)
    submission_type = serializers.ChoiceField(
        choices=["file", "text", "link", "none"], default="file"
    )
    allow_late_submission = serializers.BooleanField(default=False)
    late_penalty_percent = serializers.IntegerField(default=0)
    instructions = serializers.CharField()

    def validate_file(self, value):
        """Validate file size (max 10MB)"""
        if value and value.size > 10 * 1024 * 1024:  # 10MB
            raise serializers.ValidationError("File size must not exceed 10MB")
        return value


MAX_SUBMISSION_FILE_BYTES = 10 * 1024 * 1024  # 10MB


class SubmitAssignmentSerializer(serializers.Serializer):
    """The only fields a student may set when submitting work. Anything else in the request
    (score, feedback, status, grader fields, ...) is ignored, never written."""

    submission_file = serializers.FileField(required=False, allow_null=True)
    submission_text = serializers.CharField(required=False, allow_blank=True)
    submission_url = serializers.URLField(required=False, allow_blank=True)

    def validate_submission_file(self, value):
        """Validate file size (max 10MB)"""
        if value and value.size > MAX_SUBMISSION_FILE_BYTES:
            raise serializers.ValidationError("File size must not exceed 10MB")
        return value

    def validate(self, attrs):
        has_file = bool(attrs.get("submission_file"))
        has_text = bool((attrs.get("submission_text") or "").strip())
        has_url = bool((attrs.get("submission_url") or "").strip())
        if not (has_file or has_text or has_url):
            raise serializers.ValidationError(
                "Provide a file, some text, or a link to submit."
            )
        return attrs


class GradeSubmissionSerializer(serializers.Serializer):
    """Score and feedback for grading. The score must lie between 0 and the assignment's
    total points; pass the submission as ``context["submission"]``."""

    score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0)
    feedback = serializers.CharField(required=False, allow_blank=True)

    def validate_score(self, value):
        submission = self.context.get("submission")
        if submission is not None and value > submission.assignment.total_points:
            raise serializers.ValidationError(
                f"Score cannot exceed the assignment total of {submission.assignment.total_points}."
            )
        return value
