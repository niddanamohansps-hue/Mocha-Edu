import datetime
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.dates import school_today

from .models import PTMSession, PTMSlot


def generate_slots_for_session(session: PTMSession) -> int:
    """
    Generate discrete bookable slots for every teacher assigned to the session,
    spanning between start_time and end_time in slot_duration_minutes steps.
    Idempotent: skips slots that already exist.
    """
    teachers = list(session.teachers.all())
    if not teachers:
        return 0

    base_date = datetime.date.today()
    cur = datetime.datetime.combine(base_date, session.start_time)
    session_end = datetime.datetime.combine(base_date, session.end_time)
    slot_delta = datetime.timedelta(minutes=session.slot_duration_minutes)
    step_delta = datetime.timedelta(
        minutes=session.slot_duration_minutes + session.buffer_minutes
    )

    if cur + slot_delta > session_end:
        raise ValidationError(
            "Slot duration is greater than the total session time window."
        )

    existing_slots = set(
        PTMSlot.objects.filter(session=session).values_list("teacher_id", "start_time")
    )

    new_slots = []
    while cur + slot_delta <= session_end:
        slot_start = cur.time()
        slot_end = (cur + slot_delta).time()

        for teacher in teachers:
            if (teacher.id, slot_start) not in existing_slots:
                new_slots.append(
                    PTMSlot(
                        session=session,
                        teacher=teacher,
                        start_time=slot_start,
                        end_time=slot_end,
                        status=PTMSlot.Status.AVAILABLE,
                    )
                )
        cur += step_delta

    if new_slots:
        PTMSlot.objects.bulk_create(new_slots)

    return len(new_slots)


def book_slot(slot_id, student, parent, notes: str = "") -> PTMSlot:
    """
    Concurrency-safe atomic slot booking.
    Acquires an exclusive row-level lock on the slot via select_for_update()
    to guarantee no double-booking race condition.
    """
    with transaction.atomic():
        try:
            slot = (
                PTMSlot.objects.select_for_update()
                .select_related("session", "teacher__profile")
                .get(id=slot_id)
            )
        except PTMSlot.DoesNotExist:
            raise ValidationError("Meeting slot not found.")

        session = slot.session

        if session.status != PTMSession.Status.PUBLISHED:
            raise ValidationError("This PTM session is not currently open for bookings.")

        if session.meeting_date < school_today():
            raise ValidationError("This PTM session has already taken place.")

        if session.level_id or session.section_id:
            current = student.enrollments.filter(is_current=True).first()
            if session.level_id and (current is None or current.level_id != session.level_id):
                raise ValidationError("This PTM session is not open to this student's class.")
            if session.section_id and (current is None or current.section_id != session.section_id):
                raise ValidationError("This PTM session is not open to this student's section.")

        if slot.status != PTMSlot.Status.AVAILABLE:
            raise ValidationError("This slot has already been booked or blocked.")

        # Check if student already has a slot booked with this teacher in this session
        already_booked_teacher = PTMSlot.objects.filter(
            session=session,
            teacher=slot.teacher,
            student=student,
            status=PTMSlot.Status.BOOKED,
        ).exists()
        if already_booked_teacher:
            raise ValidationError(
                f"A meeting with {slot.teacher.profile.first_name} {slot.teacher.profile.last_name} "
                "is already booked for this student in this session."
            )

        # Check if student already has an overlapping slot at the exact same start time
        overlapping_booking = PTMSlot.objects.filter(
            session=session,
            student=student,
            start_time=slot.start_time,
            status=PTMSlot.Status.BOOKED,
        ).exists()
        if overlapping_booking:
            raise ValidationError(
                "The student already has another meeting booked at this exact time."
            )

        # Update slot
        slot.student = student
        slot.booked_by_parent = parent
        slot.booked_at = timezone.now()
        slot.parent_notes = (notes or "").strip()
        slot.status = PTMSlot.Status.BOOKED
        slot.save()

        return slot


def cancel_booking(slot_id, parent=None, is_admin=False) -> PTMSlot:
    """
    Cancels a booked slot and resets it back to AVAILABLE.
    Parents can only cancel their own bookings; staff/admins can cancel any.
    """
    with transaction.atomic():
        try:
            slot = PTMSlot.objects.select_for_update().get(id=slot_id)
        except PTMSlot.DoesNotExist:
            raise ValidationError("Meeting slot not found.")

        if slot.status != PTMSlot.Status.BOOKED:
            raise ValidationError("Only booked slots can be cancelled.")

        if not is_admin and (parent is None or slot.booked_by_parent_id != parent.id):
            raise PermissionDenied("You do not have permission to cancel this booking.")

        slot.student = None
        slot.booked_by_parent = None
        slot.booked_at = None
        slot.parent_notes = ""
        slot.status = PTMSlot.Status.AVAILABLE
        slot.save()

        return slot


def block_slot(slot_id, teacher_member=None, is_admin=False) -> PTMSlot:
    """
    Allows a teacher or admin to block an available slot (e.g. for break or prep).
    """
    with transaction.atomic():
        try:
            slot = PTMSlot.objects.select_for_update().get(id=slot_id)
        except PTMSlot.DoesNotExist:
            raise ValidationError("Meeting slot not found.")

        if slot.status != PTMSlot.Status.AVAILABLE:
            raise ValidationError("Only available slots can be blocked.")

        if not is_admin and (teacher_member is None or slot.teacher_id != teacher_member.id):
            raise PermissionDenied("You can only block your own slots.")

        slot.status = PTMSlot.Status.BLOCKED
        slot.save()
        return slot


def unblock_slot(slot_id, teacher_member=None, is_admin=False) -> PTMSlot:
    """
    Restores a blocked slot back to AVAILABLE.
    """
    with transaction.atomic():
        try:
            slot = PTMSlot.objects.select_for_update().get(id=slot_id)
        except PTMSlot.DoesNotExist:
            raise ValidationError("Meeting slot not found.")

        if slot.status != PTMSlot.Status.BLOCKED:
            raise ValidationError("Only blocked slots can be unblocked.")

        if not is_admin and (teacher_member is None or slot.teacher_id != teacher_member.id):
            raise PermissionDenied("You can only unblock your own slots.")

        slot.status = PTMSlot.Status.AVAILABLE
        slot.save()
        return slot


def record_slot_feedback(
    slot_id,
    teacher_member=None,
    feedback: str = "",
    attended: bool = True,
    is_admin=False,
) -> PTMSlot:
    """
    Records meeting discussion notes, action items, and attendance.
    """
    with transaction.atomic():
        try:
            slot = PTMSlot.objects.select_for_update().get(id=slot_id)
        except PTMSlot.DoesNotExist:
            raise ValidationError("Meeting slot not found.")

        if not is_admin and (teacher_member is None or slot.teacher_id != teacher_member.id):
            raise PermissionDenied("You can only record feedback for your own slots.")

        slot.teacher_feedback = (feedback or "").strip()
        slot.attended = attended
        if attended and slot.status == PTMSlot.Status.BOOKED:
            slot.status = PTMSlot.Status.COMPLETED
        slot.save()
        return slot

