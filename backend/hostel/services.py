"""Allocating students to rooms, and charging the hostel fee to boarders."""
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import HostelAllocation, HostelRoom

GENDER_FOR_HOSTEL = {"boys": "male", "girls": "female"}


def current_count(room):
    return room.allocations.filter(end_date__isnull=True).count()


@transaction.atomic
def allocate(*, student, room, start_date=None, note=""):
    """Put a student in a room. A student already in a room is moved: the old stay ends the day before
    (or the same day, when they are moved on the day they moved in)."""
    room = HostelRoom.objects.select_for_update().select_related("hostel").get(id=room.id)
    if not room.is_active or not room.hostel.is_active:
        raise serializers.ValidationError("This room is not in use.")
    if student.status != "active":
        raise serializers.ValidationError("Only an active student can be given a room.")
    required = GENDER_FOR_HOSTEL.get(room.hostel.gender)
    gender = student.profile.gender
    if required and gender and gender != required:
        raise serializers.ValidationError(f"{room.hostel.name} is a {room.hostel.get_gender_display().lower()} hostel.")

    start_date = start_date or timezone.localdate()
    current = HostelAllocation.objects.select_for_update().filter(student=student, end_date__isnull=True).first()
    if current and current.room_id == room.id:
        raise serializers.ValidationError("The student is already in this room.")
    if current_count(room) >= room.capacity:
        raise serializers.ValidationError(f"Room {room.number} is full ({room.capacity} beds).")
    if current:
        if start_date < current.start_date:
            raise serializers.ValidationError("The move cannot be before the date the student moved into their current room.")
        # A move on the day they moved in is a correction: the old stay ends that same day.
        current.end_date = max(start_date - timezone.timedelta(days=1), current.start_date)
        current.save(update_fields=["end_date", "updated_at"])
    return HostelAllocation.objects.create(student=student, room=room, start_date=start_date, note=note)


@transaction.atomic
def vacate(allocation, *, end_date=None):
    allocation = HostelAllocation.objects.select_for_update().get(id=allocation.id)
    if allocation.end_date is not None:
        raise serializers.ValidationError("This student has already left this room.")
    end_date = end_date or timezone.localdate()
    if end_date < allocation.start_date:
        raise serializers.ValidationError("The leaving date cannot be before the student moved in.")
    allocation.end_date = end_date
    allocation.save(update_fields=["end_date", "updated_at"])
    return allocation


def boarder_enrollments(hostel):
    """Who the hostel fee is charged to: current boarders, with their enrolment for the fee's year."""
    from students.models import StudentLevel

    def for_structure(structure):
        students = HostelAllocation.objects.filter(room__hostel=hostel, end_date__isnull=True).values("student_id")
        return (
            StudentLevel.objects.filter(
                student_id__in=students, academic_year=structure.academic_year, is_current=True,
                student__status="active",
            )
            .select_related("student__profile", "level", "section")
            .order_by("student__profile__first_name", "student__profile__last_name")
        )

    return for_structure
