import uuid

from django.db import models


DAY_OF_WEEK_CHOICES = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]


class Period(models.Model):
    """
    One slot in the daily sequence (e.g. "Period 1", "Lunch Break"). Scoped by
    academic_year (a plain string, matching the project-wide convention
    already used by StudentLevel/SubjectEnrollment/AttendanceSession - no
    dedicated AcademicYear model exists or is being introduced here).

    Breaks are represented as Period rows with is_break=True rather than a
    separate model - they participate in the daily ordering but never
    receive a TimetableEntry.
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
    name = models.CharField(max_length=100)
    order = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("academic_year", "order")
        ordering = ["academic_year", "order"]

    def __str__(self):
        return f"{self.name} ({self.academic_year})"


class Room(models.Model):
    """
    Optional. TimetableEntry.room may be null - schools that don't track
    room assignments simply never populate it, and no conflict check applies.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    capacity = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TimetableEntry(models.Model):
    """
    A WEEKLY RECURRING slot - "every Monday, Period 3, Section 10-A has Math
    with Instructor X" - not a per-date record. One row per recurring slot,
    not one row per calendar day.

    day_of_week: 0=Monday ... 6=Sunday (see DAY_OF_WEEK_CHOICES above).

    Conflict prevention is enforced by three unique_together constraints
    below, relying on PostgreSQL's NULL semantics (multiple NULLs never
    collide) so instructor/room conflicts only apply once those fields are
    actually populated.
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
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.CASCADE, related_name="timetable_entries"
    )
    instructor = models.ForeignKey(
        "staff.Instructor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_entries",
    )
    room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_entries"
    )
    day_of_week = models.IntegerField(choices=DAY_OF_WEEK_CHOICES)
    period = models.ForeignKey(
        Period, on_delete=models.CASCADE, related_name="timetable_entries"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ("section", "academic_year", "day_of_week", "period"),
            ("instructor", "academic_year", "day_of_week", "period"),
            ("room", "academic_year", "day_of_week", "period"),
        ]
        indexes = [
            models.Index(fields=["academic_year", "day_of_week"], name="tt_entry_year_day_idx"),
        ]
        ordering = ["day_of_week", "period__order"]

    def __str__(self):
        return f"{self.section} - {self.get_day_of_week_display()} - {self.period}"


class TimetableSubstitution(models.Model):
    """
    A single-date exception to a recurring TimetableEntry - "who actually
    covered this slot on this specific date, if different from the usual
    instructor." Not a recurring concept itself.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timetable_entry = models.ForeignKey(
        TimetableEntry, on_delete=models.CASCADE, related_name="substitutions"
    )
    date = models.DateField()
    substitute_instructor = models.ForeignKey(
        "staff.Instructor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="substitute_assignments",
    )
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_substitutions",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("timetable_entry", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.timetable_entry} substituted on {self.date}"
