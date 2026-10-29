import uuid
from django.db import models
from django.utils import timezone


class PTMSession(models.Model):
    """
    Parent-Teacher Meeting Event / Session.
    Defines the date, overall time frame, slot duration, target classes,
    and participating teachers.
    """

    class Mode(models.TextChoices):
        IN_PERSON = "in_person", "In-Person"
        ONLINE = "online", "Online / Virtual"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, help_text="e.g. 'Term 1 Mid-Term PTM'")
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ptm_sessions",
    )
    meeting_date = models.DateField(help_text="Date the PTM is conducted")
    start_time = models.TimeField(help_text="Session opening time, e.g. 09:00:00")
    end_time = models.TimeField(help_text="Session closing time, e.g. 13:00:00")
    slot_duration_minutes = models.PositiveIntegerField(
        default=10,
        help_text="Duration of each parent discussion slot in minutes (e.g. 10 or 15)",
    )
    buffer_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Buffer/transit gap between consecutive slots in minutes",
    )
    mode = models.CharField(
        max_length=20,
        choices=Mode.choices,
        default=Mode.IN_PERSON,
    )
    location_or_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Room number/hall or video meeting link",
    )
    level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ptm_sessions",
        help_text="Leave blank if open to all grades",
    )
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ptm_sessions",
        help_text="Leave blank if open to all sections of the grade",
    )
    teachers = models.ManyToManyField(
        "staff.StaffMember",
        related_name="ptm_sessions",
        blank=True,
        help_text="Participating teachers for whom time slots will be generated",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    instructions = models.TextField(
        blank=True,
        help_text="Guidelines and notes displayed to parents during booking",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-meeting_date", "start_time"]
        verbose_name = "PTM Session"
        verbose_name_plural = "PTM Sessions"

    def __str__(self):
        return f"{self.title} ({self.meeting_date})"

    @property
    def total_slots(self):
        return self.slots.count()

    @property
    def booked_slots_count(self):
        return self.slots.filter(status=PTMSlot.Status.BOOKED).count()


class PTMSlot(models.Model):
    """
    Discrete bookable time slot for a specific teacher during a PTM session.
    """

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        BOOKED = "booked", "Booked"
        BLOCKED = "blocked", "Blocked"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        PTMSession,
        on_delete=models.CASCADE,
        related_name="slots",
    )
    teacher = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.CASCADE,
        related_name="ptm_slots",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )

    # Booking information
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ptm_slots",
    )
    booked_by_parent = models.ForeignKey(
        "families.Parent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ptm_bookings",
    )
    booked_at = models.DateTimeField(null=True, blank=True)
    parent_notes = models.TextField(
        blank=True,
        help_text="Discussion points or questions from parent",
    )

    # Post-meeting recording
    teacher_feedback = models.TextField(
        blank=True,
        help_text="Teacher's remarks, academic progress notes, and action items",
    )
    attended = models.BooleanField(
        default=False,
        help_text="Whether the parent and teacher attended the meeting",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["session", "start_time", "teacher"]
        unique_together = [("session", "teacher", "start_time")]
        verbose_name = "PTM Slot"
        verbose_name_plural = "PTM Slots"

    def __str__(self):
        return f"{self.session.title} - {self.teacher} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}): {self.status}"

