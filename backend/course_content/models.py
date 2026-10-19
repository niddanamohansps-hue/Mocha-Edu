from django.db import models
import uuid


class ContentType(models.TextChoices):
    NOTE = "note", "Study Note"
    DOCUMENT = "document", "Document/PDF"
    VIDEO = "video", "Video Tutorial"
    LINK = "link", "External Link"
    ASSIGNMENT = "assignment", "Assignment"


class CourseContent(models.Model):
    """
    Educational content (notes, videos, assignments, documents)
    Flexible multi-level targeting for distribution
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Basic Info
    title = models.CharField(max_length=200)
    description = models.TextField()
    content_type = models.CharField(max_length=20, choices=ContentType.choices)

    # File/URL storage
    file = models.FileField(upload_to="course_content/%Y/%m/", null=True, blank=True)
    external_url = models.URLField(null=True, blank=True)

    # Author (any staff member can create content)
    created_by = models.ForeignKey(
        "staff.StaffMember", on_delete=models.CASCADE, related_name="created_content"
    )

    # Flexible visibility targeting (multi-level)
    target_programs = models.ManyToManyField("academics.Program", blank=True)
    target_levels = models.ManyToManyField("academics.AcademicLevel", blank=True)
    target_sections = models.ManyToManyField("academics.Section", blank=True)
    target_subjects = models.ManyToManyField("academics.Subject", blank=True)
    specific_students = models.ManyToManyField("students.Student", blank=True)

    # Publishing control
    is_published = models.BooleanField(default=False)
    publish_date = models.DateTimeField(null=True, blank=True)

    # Metadata
    is_pinned = models.BooleanField(default=False)  # Show at top
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["content_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_content_type_display()})"


class SubjectEnrollment(models.Model):
    """
    Tracks which subjects each student is taking
    Enables subject-specific content filtering
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="subject_enrollments"
    )
    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.CASCADE,
        related_name="student_enrollments",
    )
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["student", "subject", "academic_year"]

    def __str__(self):
        return f"{self.student.profile.full_name} - {self.subject.name}"


class Assignment(models.Model):
    """
    Assignment-specific fields extending CourseContent
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    content = models.OneToOneField(
        CourseContent, on_delete=models.CASCADE, related_name="assignment_details"
    )

    # Assignment specifics
    due_date = models.DateTimeField()
    total_points = models.DecimalField(max_digits=5, decimal_places=2, default=100)

    # Submission settings
    SUBMISSION_TYPES = [
        ("file", "File Upload"),
        ("text", "Text Entry"),
        ("link", "URL Link"),
        ("none", "No Submission Required"),
    ]
    submission_type = models.CharField(
        max_length=20, choices=SUBMISSION_TYPES, default="file"
    )
    allow_late_submission = models.BooleanField(default=False)
    late_penalty_percent = models.IntegerField(default=0)  # % deduction per day

    # Instructions
    instructions = models.TextField()

    def __str__(self):
        return f"Assignment: {self.content.title}"


class AssignmentSubmission(models.Model):
    """
    Student submissions for assignments
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
    )

    # Submission data
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_file = models.FileField(
        upload_to="submissions/%Y/%m/", null=True, blank=True
    )
    submission_text = models.TextField(blank=True)
    submission_url = models.URLField(blank=True)

    # Status tracking
    STATUS_CHOICES = [
        ("pending", "Not Submitted"),
        ("submitted", "Submitted"),
        ("graded", "Graded"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Grading
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions",
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["assignment", "student"]
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student.profile.full_name} - {self.assignment.content.title}"

    @property
    def is_late(self):
        """Check if submission was late"""
        if self.submitted_at and self.assignment.due_date:
            return self.submitted_at > self.assignment.due_date
        return False
