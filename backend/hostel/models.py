"""Boarding: hostels, rooms, and which student lives in which room."""
import uuid

from django.db import models

HOSTEL_GENDER_CHOICES = [("boys", "Boys"), ("girls", "Girls"), ("mixed", "Mixed")]


class Hostel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    gender = models.CharField(max_length=10, choices=HOSTEL_GENDER_CHOICES, default="mixed")
    warden = models.ForeignKey("staff.StaffMember", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    warden_phone = models.CharField(max_length=20, blank=True)
    fee_structure = models.ForeignKey(
        "fees.FeeStructure", on_delete=models.SET_NULL, null=True, blank=True, related_name="hostels",
        help_text="The hostel fee charged to this hostel's boarders.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class HostelRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="rooms")
    number = models.CharField(max_length=20)
    floor = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["hostel__name", "floor", "number"]
        constraints = [
            models.UniqueConstraint(fields=["hostel", "number"], name="hostel_room_unique_number"),
            models.CheckConstraint(condition=models.Q(capacity__gte=1), name="hostel_room_capacity_min_1"),
        ]

    def __str__(self):
        return f"{self.hostel.name} {self.number}"


class HostelAllocation(models.Model):
    """A student living in a room from start_date until end_date. Kept as history when they move out."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="hostel_allocations")
    room = models.ForeignKey(HostelRoom, on_delete=models.PROTECT, related_name="allocations")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            # A student lives in one room at a time.
            models.UniqueConstraint(
                fields=["student"], condition=models.Q(end_date__isnull=True), name="hostel_one_current_room_per_student"
            ),
        ]

    @property
    def is_current(self):
        return self.end_date is None
