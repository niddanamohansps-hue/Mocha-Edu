from django.db import models
import uuid


class Student(models.Model):
    """
    Academic Domain: Stores data specific to a person's life as a student.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.OneToOneField(
        "profiles.Profile", on_delete=models.CASCADE, related_name="student_record"
    )

    enrollment_id = models.CharField(max_length=50, unique=True)
    admission_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("graduated", "Graduated"),
            ("withdrawn", "Withdrawn"),
            ("transferred", "Transferred"),
        ],
        default="active",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "admission_date"], name="student_status_date_idx"
            ),
        ]

    def __str__(self):
        return f"{self.profile.first_name} - {self.enrollment_id}"


class AcademicHistory(models.Model):
    """
    Stores previous schooling information.
    """

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="academic_history"
    )
    previous_school = models.CharField(max_length=255)
    last_grade_passed = models.CharField(max_length=50)
    completion_year = models.IntegerField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Academic Histories"


class StudentLevel(models.Model):
    """
    Tracks which level (Grade/Class) and section a student is in for a given year.
    """

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="enrollments"
    )
    # Link to the Academic Structure
    level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        related_name="student_enrollments",
        null=True,  # Temporarily null for migration safety if needed, or strict if new
    )
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.SET_NULL,
        related_name="student_enrollments",
        null=True,
        blank=True,
    )

    academic_year = models.CharField(max_length=20)  # e.g., 2081 or 2024
    is_current = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "academic_year")


PROMOTION_ACTION_CHOICES = [
    ("promoted", "Promoted"),
    ("retained", "Retained"),
    ("transferred", "Transferred"),
    ("withdrawn", "Withdrawn"),
    ("graduated", "Graduated"),
    ("reversed", "Reversed"),
]


class PromotionRecord(models.Model):
    """
    Append-only history of every student lifecycle transition performed by
    the Promotion & Transfer workflow. Never updated after creation, and
    never deleted directly - the only way a row disappears is the same
    on_delete=CASCADE already used by AcademicHistory when the parent
    Student is hard-deleted via the existing (untouched) delete endpoint,
    since both are supplementary per-student history rather than
    source-of-truth enrollment data.

    A correction is represented by a NEW row with action="reversed"
    (linked via `reverses`), never by editing an existing row.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="promotion_records"
    )
    action = models.CharField(max_length=20, choices=PROMOTION_ACTION_CHOICES)

    source_academic_year = models.CharField(max_length=20, blank=True)
    target_academic_year = models.CharField(max_length=20, blank=True)

    source_level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_source",
    )
    target_level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_target",
    )
    source_section = models.ForeignKey(
        "academics.Section",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_source",
    )
    target_section = models.ForeignKey(
        "academics.Section",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_target",
    )

    # Exact StudentLevel row references, so a reversal can restore precisely
    # the row that was current before this action - not just "some row
    # matching this level/year".
    source_student_level = models.ForeignKey(
        StudentLevel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_source",
    )
    target_student_level = models.ForeignKey(
        StudentLevel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_target",
    )

    reason = models.CharField(max_length=255, blank=True)

    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal",
        help_text="Set only on a reversal record - points at the original PromotionRecord it reverses.",
    )

    created_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotion_records_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["student", "-created_at"], name="promorec_student_history_idx"),
            models.Index(fields=["action"], name="promorec_action_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_id} - {self.action} - {self.source_academic_year} -> {self.target_academic_year}"
