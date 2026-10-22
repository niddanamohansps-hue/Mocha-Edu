import uuid

from django.core.exceptions import ValidationError
from django.db import models


ATTENDANCE_STATUS_CHOICES = [
    ("present", "Present"),
    ("absent", "Absent"),
    ("late", "Late"),
    ("half_day", "Half Day"),
    ("leave", "Leave"),
]

ALLOWED_STATUS_KEYS = {choice[0] for choice in ATTENDANCE_STATUS_CHOICES}

# Weekdays the school is closed every week, as Python weekday numbers (0 = Monday ... 6 = Sunday).
# The default is Sunday, which is what the leave code always assumed, so no school changes behaviour
# until its owner picks different days.
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def default_weekly_off_days():
    return [6]


def validate_weekly_off_days(value):
    """A list of distinct weekday numbers 0-6, at most six of them (the school must open some day)."""
    if not isinstance(value, list):
        raise ValidationError("Must be a list of weekday numbers (0 = Monday ... 6 = Sunday).")
    if any(isinstance(day, bool) or not isinstance(day, int) or not 0 <= day <= 6 for day in value):
        raise ValidationError("Each weekly off day must be a whole number from 0 (Monday) to 6 (Sunday).")
    if len(set(value)) != len(value):
        raise ValidationError("A weekday is listed more than once.")
    if len(value) > 6:
        raise ValidationError("At least one day of the week must be a working day.")
    return sorted(value)


DEFAULT_STATUS_WEIGHTS = {
    "present": 1.0,
    "absent": 0.0,
    "late": 1.0,
    "half_day": 0.5,
    "leave": None,
}


def default_status_weights():
    return dict(DEFAULT_STATUS_WEIGHTS)


class AttendanceSession(models.Model):
    """
    One daily attendance-taking event for a Section. Individual student marks
    are stored on StudentAttendance rows linked to this session, so a whole
    class is submitted/edited/locked as one unit.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(
        "academics.Section", on_delete=models.CASCADE, related_name="attendance_sessions"
    )
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    date = models.DateField()

    recorded_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendance_sessions",
    )

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("section", "date")
        indexes = [
            models.Index(fields=["date"], name="attsession_date_idx"),
        ]

    def __str__(self):
        return f"{self.section} - {self.date}"


class StudentAttendance(models.Model):
    """
    One student's attendance mark within an AttendanceSession.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="student_records"
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="attendance_records"
    )
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES)
    remarks = models.CharField(max_length=255, blank=True)

    recorded_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_student_attendance",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("session", "student")
        indexes = [
            models.Index(fields=["student", "-created_at"], name="studentatt_history_idx"),
        ]

    def __str__(self):
        return f"{self.student} - {self.session.date} - {self.status}"


class StaffAttendance(models.Model):
    """
    Manually-recorded daily attendance for a staff member. No session concept -
    each staff member's attendance is marked individually per day, not as a
    section-wide batch. V1 has no self check-in/biometric/kiosk support.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(
        "staff.StaffMember", on_delete=models.CASCADE, related_name="attendance_records"
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES)
    remarks = models.CharField(max_length=255, blank=True)

    recorded_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_staff_attendance",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("staff", "date")
        indexes = [
            models.Index(fields=["staff", "-date"], name="staffatt_history_idx"),
        ]

    def __str__(self):
        return f"{self.staff} - {self.date} - {self.status}"


class AttendanceSettings(models.Model):
    """
    Tenant-scoped singleton. Use AttendanceSettings.get_solo() to fetch/create
    the one row for the current schema, mirroring the get_or_create pattern
    already used elsewhere in the project (e.g. profiles.InstitutionProfile).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status_weights = models.JSONField(default=default_status_weights)
    minimum_attendance_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=75.00
    )
    lock_after_days = models.IntegerField(default=0)
    weekly_off_days = models.JSONField(
        default=default_weekly_off_days,
        blank=True,  # an empty list is valid: no weekly off day
        help_text="Weekdays the school is closed every week: 0 = Monday ... 6 = Sunday.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def weekly_off(cls):
        """The school's weekly off days as a frozenset of weekday numbers. Never writes: with no saved
        settings it returns the default (Sunday)."""
        row = cls.objects.only("weekly_off_days").first()
        days = row.weekly_off_days if row is not None else default_weekly_off_days()
        return frozenset(days)

    def clean(self):
        try:
            self.weekly_off_days = validate_weekly_off_days(self.weekly_off_days)
        except ValidationError as exc:
            raise ValidationError({"weekly_off_days": exc.messages})
        if not isinstance(self.status_weights, dict):
            raise ValidationError({"status_weights": "Must be a JSON object."})

        keys = set(self.status_weights.keys())
        if not keys.issubset(ALLOWED_STATUS_KEYS):
            raise ValidationError(
                {
                    "status_weights": (
                        f"Unknown status key(s): {sorted(keys - ALLOWED_STATUS_KEYS)}. "
                        f"Only {sorted(ALLOWED_STATUS_KEYS)} are allowed."
                    )
                }
            )
        for key, value in self.status_weights.items():
            if value is not None and not isinstance(value, (int, float)):
                raise ValidationError(
                    {"status_weights": f"Weight for '{key}' must be a number or null."}
                )
            if isinstance(value, (int, float)) and not (0 <= value <= 1):
                raise ValidationError(
                    {"status_weights": f"Weight for '{key}' must be between 0 and 1."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        instance = cls.objects.first()
        if instance is None:
            instance = cls.objects.create()
        return instance

    def __str__(self):
        return "Attendance Settings"
