import uuid

from django.core.exceptions import ValidationError
from django.db import models


class ExamType(models.Model):
    """
    Configurable exam category (e.g. "Mid-Term", "Unit Test", "Annual
    Examination"). Deliberately NOT a hardcoded Python choices list - naming
    varies too much by school/region to fix in code, and unlike Attendance's
    status choices, an exam type carries no differential system behavior.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    order = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Examination(models.Model):
    """
    A named examination event (e.g. "Mid-Term 2026"). academic_year is a
    plain string, matching the project-wide convention already used by
    StudentLevel/AttendanceSession/TimetableEntry - no dedicated AcademicYear
    model exists or is introduced here.

    Publication is whole-exam, not per-schedule: once is_published=True, an
    ExamResult snapshot exists per participating student and must not be
    silently recalculated.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    name = models.CharField(max_length=200)
    exam_type = models.ForeignKey(ExamType, on_delete=models.PROTECT, related_name="examinations")
    start_date = models.DateField()
    end_date = models.DateField()

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.academic_year})"


class ExamSchedule(models.Model):
    """
    Examination + Subject + Section, with its own authoritative date/time -
    NOT a reference to timetable.TimetableEntry, which represents a
    recurring WEEKLY template, not a one-off dated event. Regular timetable
    entries are not authoritative on examination days (classes are commonly
    suspended), so exam scheduling is deliberately independent of them.

    timetable.Room and timetable.Period are reused directly (both optional -
    an exam may run outside normal periods/rooms), never duplicated.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name="schedules")
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.CASCADE, related_name="exam_schedules"
    )
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, related_name="exam_schedules"
    )

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    period = models.ForeignKey(
        "timetable.Period", on_delete=models.SET_NULL, null=True, blank=True, related_name="exam_schedules"
    )
    room = models.ForeignKey(
        "timetable.Room", on_delete=models.SET_NULL, null=True, blank=True, related_name="exam_schedules"
    )

    max_marks = models.DecimalField(max_digits=6, decimal_places=2)
    pass_marks = models.DecimalField(max_digits=6, decimal_places=2)

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("examination", "subject", "section")
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.examination} - {self.subject} - {self.section}"


class ExamMark(models.Model):
    """
    Raw, source-of-truth marks for one student in one ExamSchedule.

    marks_obtained is nullable: NULL + is_absent=False means "not yet
    graded"; is_absent=True means the student was absent. These two states
    must remain distinguishable - NULL is never silently treated as absent.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam_schedule = models.ForeignKey(ExamSchedule, on_delete=models.CASCADE, related_name="marks")
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="exam_marks"
    )
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_absent = models.BooleanField(default=False)
    remarks = models.CharField(max_length=255, blank=True)

    entered_by = models.ForeignKey(
        "staff.StaffMember", on_delete=models.SET_NULL, null=True, blank=True, related_name="entered_exam_marks"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("exam_schedule", "student")
        indexes = [
            models.Index(fields=["student", "-created_at"], name="exammark_student_idx"),
        ]

    def __str__(self):
        return f"{self.student} - {self.exam_schedule} - {self.marks_obtained}"


class ExamResult(models.Model):
    """
    Immutable publication snapshot. Created ONCE, atomically, when an
    Examination is published - never recalculated afterward, even if
    GradeBoundary or ExamMark data changes later. subject_breakdown carries
    enough per-subject detail (marks/max/percentage/grade/absence) that
    rendering a student's published result never needs to re-derive
    anything from mutable configuration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name="results")
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="exam_results"
    )
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    total_marks_obtained = models.DecimalField(max_digits=8, decimal_places=2)
    total_max_marks = models.DecimalField(max_digits=8, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    overall_grade = models.CharField(max_length=20, blank=True)
    is_pass = models.BooleanField()

    subject_breakdown = models.JSONField(default=list)

    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("examination", "student")
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.student} - {self.examination} - {self.percentage}%"


class GradeBoundary(models.Model):
    """
    Tenant-configurable grading scale (e.g. 90-100 -> A+). Deliberately not
    hardcoded - grading scales vary by school/country. Overlap/ordering is
    validated at the application layer (clean()/save()), not via a
    PostgreSQL EXCLUDE constraint, which would be excessive for a small,
    admin-managed table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    grade_label = models.CharField(max_length=20)
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["academic_year", "-min_percentage"]
        verbose_name_plural = "Grade Boundaries"

    def clean(self):
        if self.min_percentage is None or self.max_percentage is None:
            return
        if self.min_percentage < 0 or self.max_percentage > 100:
            raise ValidationError("Percentage values must be between 0 and 100.")
        if self.min_percentage >= self.max_percentage:
            raise ValidationError({"min_percentage": "min_percentage must be less than max_percentage."})

        overlapping = GradeBoundary.objects.filter(
            academic_year=self.academic_year,
            min_percentage__lt=self.max_percentage,
            max_percentage__gt=self.min_percentage,
        ).exclude(id=self.id)
        if overlapping.exists():
            raise ValidationError(
                f"This range overlaps with an existing grade boundary "
                f"({overlapping.first().grade_label}) for {self.academic_year}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.grade_label} ({self.min_percentage}-{self.max_percentage}%, {self.academic_year})"
