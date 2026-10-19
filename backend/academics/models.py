from django.db import models
import uuid


class Program(models.Model):
    """
    Broad academic stream or program (e.g. High School, Bachelors in CS, A-Levels).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=20, unique=True, help_text="Short code e.g. 'HS', 'BSC'"
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class AcademicLevel(models.Model):
    """
    Horizontal level within a program (e.g. Grade 10, Semester 1).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="levels"
    )
    name = models.CharField(max_length=50, help_text="e.g. 'Grade 10', 'Semester 1'")
    order = models.IntegerField(default=1, help_text="For sorting: 1, 2, 3...")

    class Meta:
        ordering = ["program", "order"]
        unique_together = ["program", "name"]

    def __str__(self):
        return f"{self.program.code} - {self.name}"


class Section(models.Model):
    """
    Physical grouping of student within a level (e.g. Section A, Morning Shift).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    level = models.ForeignKey(
        AcademicLevel, on_delete=models.CASCADE, related_name="sections"
    )
    name = models.CharField(max_length=50, help_text="e.g. 'A', 'Group 1'")
    capacity = models.IntegerField(default=40)

    class Meta:
        unique_together = ["level", "name"]
        ordering = ["level", "name"]

    def __str__(self):
        return f"{self.level.name} - {self.name}"


class Subject(models.Model):
    """
    Subject definition for a specific level (e.g. Mathematics for Grade 10).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    level = models.ForeignKey(
        AcademicLevel, on_delete=models.CASCADE, related_name="subjects"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, help_text="Course code e.g. MTH101")
    credits = models.DecimalField(max_digits=4, decimal_places=1, default=1.0)
    is_elective = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ["level", "code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class SubjectAssignment(models.Model):
    """
    Mapping of a Subject to a specific Section and Instructor.
    This defines 'Who teaches What to Whom'.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="assignments"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="assignments"
    )
    instructor = models.ForeignKey(
        "staff.Instructor",
        on_delete=models.SET_NULL,
        null=True,
        related_name="assignments",
    )

    class Meta:
        # A section normally has one main teacher for a specific subject
        unique_together = ["section", "subject"]

    def __str__(self):
        return f"{self.subject.code} in {self.section} by {self.instructor}"


class AcademicYear(models.Model):
    """
    Tenant-local academic year. Phase 1.2A introduces only the entity; existing
    free-text academic_year CharFields across other apps are intentionally left
    untouched until a later, human-reviewed migration maps them.

    Name is "YYYY-YY" with consecutive years (e.g. "2026-27"). Invalid names are
    rejected, never repaired. Uniqueness and the single-current-year rule are
    enforced by database constraints; the schema itself scopes them per tenant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="academicyear_name_unique"),
            models.UniqueConstraint(
                fields=["is_current"],
                condition=models.Q(is_current=True),
                name="academicyear_one_current",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        import re
        from django.core.exceptions import ValidationError

        match = re.fullmatch(r"(\d{4})-(\d{2})", self.name or "")
        if not match or (int(match.group(1)) + 1) % 100 != int(match.group(2)):
            raise ValidationError(
                {"name": 'Academic year must be "YYYY-YY" with consecutive years, e.g. "2026-27".'}
            )

        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError({"end_date": "End date must be after the start date."})


class CalendarEvent(models.Model):
    """
    Tenant-local academic calendar event or holiday.
    Supports single-day, multi-day, all-day, and timed events,
    with categories including holidays, closures, exams, meetings, and activities.
    """

    EVENT_TYPE_CHOICES = [
        ("HOLIDAY", "Public / School Holiday"),
        ("ACADEMIC", "Academic Event"),
        ("EXAMINATION", "Examination Period"),
        ("ACTIVITY", "School Activity / Sports"),
        ("MEETING", "Parent-Teacher Meeting"),
        ("CLOSURE", "School Closure / Emergency"),
        ("DEADLINE", "Academic Deadline"),
        ("OTHER", "Other"),
    ]

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PUBLISHED", "Published"),
        ("CANCELLED", "Cancelled"),
    ]

    AUDIENCE_CHOICES = [
        ("ALL", "Entire School"),
        ("STAFF", "Staff & Faculty Only"),
        ("STUDENTS", "Students & Parents Only"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES, default="ACADEMIC")
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=True)
    is_holiday = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PUBLISHED")
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendar_events",
    )
    location = models.CharField(max_length=200, blank=True, default="")
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="ALL")
    created_by_id = models.UUIDField(null=True, blank=True)
    created_by_username = models.CharField(max_length=150, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "start_time", "title"]
        indexes = [
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["academic_year", "start_date"]),
            models.Index(fields=["event_type", "start_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_event_type_display()}) [{self.start_date} to {self.end_date}]"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot precede start date."})

        if not self.is_all_day and self.start_date == self.end_date and self.start_time and self.end_time:
            if self.end_time < self.start_time:
                raise ValidationError({"end_time": "End time cannot precede start time on the same date."})

        if self.event_type in ("HOLIDAY", "CLOSURE"):
            self.is_holiday = True

    def save(self, *args, **kwargs):
        if self.event_type in ("HOLIDAY", "CLOSURE"):
            self.is_holiday = True
        super().save(*args, **kwargs)

