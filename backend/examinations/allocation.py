"""Exam-day logistics: which room each student sits in, and which staff invigilate each room.

A *sitting* is every paper of one examination that starts at the same date and time (several classes usually sit
together). Seats are allocated per sitting: students of all its papers are interleaved so neighbours are from
different papers where possible, then placed in rooms. Invigilators are then chosen for the rooms in use.

Students have no roll number in this system, so within a paper they are ordered by enrollment id.
"""
import uuid
from collections import defaultdict

from django.db import transaction

from core.audit import log_action

from .models import ExamInvigilation, ExamSchedule, ExamSeat, ExamSitting


class AllocationError(Exception):
    """The request cannot be satisfied (not enough seats or staff, a clash). Nothing was changed."""


# --- sittings --------------------------------------------------------------------------------


@transaction.atomic
def sync_sittings(examination):
    """Make the sittings match the examination's papers: one per distinct (date, start time), spanning the latest
    end time among its papers. A sitting left with no papers is removed along with its seats and duties."""
    wanted = {}
    for schedule in ExamSchedule.objects.filter(examination=examination):
        key = (schedule.date, schedule.start_time)
        end = wanted.get(key)
        wanted[key] = schedule.end_time if end is None else max(end, schedule.end_time)

    existing = {(s.date, s.start_time): s for s in ExamSitting.objects.filter(examination=examination)}
    for key, sitting in existing.items():
        if key not in wanted:
            sitting.delete()
    for (date, start), end in wanted.items():
        sitting = existing.get((date, start))
        if sitting is None:
            ExamSitting.objects.create(examination=examination, date=date, start_time=start, end_time=end)
        elif sitting.end_time != end:
            sitting.end_time = end
            sitting.save(update_fields=["end_time"])
    return list(ExamSitting.objects.filter(examination=examination))


def sitting_schedules(sitting):
    return list(
        ExamSchedule.objects.filter(examination=sitting.examination, date=sitting.date, start_time=sitting.start_time)
        .select_related("subject", "section__level")
        .order_by("section__level__name", "section__name", "subject__name")
    )


def _roster(section_id):
    from students.models import Student

    return list(
        Student.objects.filter(
            enrollments__section_id=section_id, enrollments__is_current=True, status="active"
        )
        .select_related("profile")
        .order_by("enrollment_id")
        .distinct()
    )


def sitting_roster(sitting):
    """``[(student, schedule)]`` for everyone sitting this sitting, in a stable order."""
    pairs, seen = [], {}
    for schedule in sitting_schedules(sitting):
        for student in _roster(schedule.section_id):
            if student.id in seen:
                raise AllocationError(
                    f"{student.profile.first_name} {student.profile.last_name} is in two papers at the same time "
                    f"({seen[student.id]} and {schedule.subject.name}); fix the exam schedule first."
                )
            seen[student.id] = schedule.subject.name
            pairs.append((student, schedule))
    return pairs


def _overlapping(sitting):
    """Other sittings (any examination) on the same day whose time overlaps this one."""
    return ExamSitting.objects.filter(
        date=sitting.date, start_time__lt=sitting.end_time, end_time__gt=sitting.start_time
    ).exclude(pk=sitting.pk)


# --- rooms -----------------------------------------------------------------------------------


def _interleave(groups):
    """Round-robin across the papers, so neighbouring seats are from different papers while more than one paper
    still has students. Each group is a list; larger groups go first so the tail is as short as possible."""
    queues = [list(g) for g in sorted(groups, key=len, reverse=True) if g]
    out = []
    while queues:
        for queue in list(queues):
            out.append(queue.pop(0))
            if not queue:
                queues.remove(queue)
    return out


@transaction.atomic
def allocate_rooms(sitting, *, mix=True, room_ids=None, request=None):
    """Seat every student of the sitting. Replaces any earlier seating of it. Raises AllocationError, changing
    nothing, when the available rooms cannot hold everyone."""
    from timetable.models import Room

    sitting = ExamSitting.objects.select_for_update().get(pk=sitting.pk)
    pairs = sitting_roster(sitting)
    if not pairs:
        raise AllocationError("No students are enrolled in the papers of this sitting.")

    busy = set(ExamSeat.objects.filter(sitting__in=_overlapping(sitting)).values_list("room_id", flat=True))
    rooms = Room.objects.filter(capacity__gt=0).exclude(pk__in=busy)
    if room_ids:
        try:
            wanted = [uuid.UUID(str(i)) for i in room_ids]
        except ValueError:
            raise AllocationError("A chosen room is not valid.")
        by_id = {r.id: r for r in rooms.filter(pk__in=wanted)}
        if any(i not in by_id for i in wanted):
            raise AllocationError("Some chosen rooms are unknown, have no capacity, or are in use at that time.")
        ordered = [by_id[i] for i in wanted]
    else:
        ordered = sorted(rooms, key=lambda r: (-r.capacity, r.name))

    total = len(pairs)
    available = sum(r.capacity for r in ordered)
    if available < total:
        raise AllocationError(
            f"Not enough seats: {total} students but only {available} seats in the available rooms "
            f"(short by {total - available}). Add rooms or free some capacity."
        )

    if mix:
        groups = defaultdict(list)
        for student, schedule in pairs:
            groups[schedule.id].append((student, schedule))
        sequence = _interleave(groups.values())
    else:
        sequence = pairs

    ExamSeat.objects.filter(sitting=sitting).delete()
    seats, index = [], 0
    for room in ordered:
        if index >= total:
            break
        for number in range(1, room.capacity + 1):
            if index >= total:
                break
            student, schedule = sequence[index]
            seats.append(ExamSeat(sitting=sitting, room=room, student=student, schedule=schedule, seat_number=number))
            index += 1
    ExamSeat.objects.bulk_create(seats)

    used = {s.room_id for s in seats}
    # Duties in rooms that are no longer used would point at empty rooms.
    dropped = ExamInvigilation.objects.filter(sitting=sitting).exclude(room_id__in=used).delete()[0]
    log_action(
        request, "exam_rooms_allocated", "ExamSitting", str(sitting.id),
        {"students": total, "rooms": len(used), "mixed": bool(mix), "duties_dropped": dropped},
    )
    return {"students": total, "rooms": len(used), "duties_dropped": dropped}


@transaction.atomic
def move_seat(sitting, student_id, room_id, seat_number, request=None):
    """Put a student in a specific seat. If someone is there, the two swap seats."""
    from timetable.models import Room

    mine = ExamSeat.objects.select_for_update().filter(sitting=sitting, student_id=student_id).first()
    if mine is None:
        raise AllocationError("That student has no seat in this sitting.")
    room = Room.objects.filter(pk=room_id).first()
    if room is None or not 1 <= seat_number <= room.capacity:
        raise AllocationError("That seat does not exist in that room.")
    busy = ExamSeat.objects.filter(sitting__in=_overlapping(sitting), room=room).exists()
    if busy:
        raise AllocationError("That room is in use by another sitting at this time.")

    other = ExamSeat.objects.select_for_update().filter(sitting=sitting, room=room, seat_number=seat_number).first()
    if other is not None and other.pk == mine.pk:
        return mine
    old_room, old_number = mine.room_id, mine.seat_number
    if other is not None:
        # Free the target seat first so the unique (room, seat) constraint is never violated mid-swap.
        other.seat_number = 0
        other.save(update_fields=["seat_number"])
    mine.room, mine.seat_number = room, seat_number
    mine.save(update_fields=["room", "seat_number"])
    if other is not None:
        other.room_id, other.seat_number = old_room, old_number
        other.save(update_fields=["room", "seat_number"])
    log_action(
        request, "exam_seat_moved", "ExamSitting", str(sitting.id),
        {"student": str(student_id), "room": str(room_id), "seat": seat_number, "swapped": other is not None},
    )
    return mine


# --- invigilators ----------------------------------------------------------------------------


def _on_leave(date):
    """Staff with an approved leave covering the date (a half day counts as unavailable: it is safer to ask
    someone else than to leave a room uncovered)."""
    from staff.models import LeaveApplication

    return set(
        LeaveApplication.objects.filter(status="approved", start_date__lte=date, end_date__gte=date)
        .values_list("staff_id", flat=True)
    )


def _busy_staff(sitting):
    return set(
        ExamInvigilation.objects.filter(sitting__in=_overlapping(sitting)).values_list("staff_id", flat=True)
    )


def _teaching_sections(examination):
    """``{staff_id: {section_id}}`` from the timetable, for the examination's academic year."""
    from timetable.models import TimetableEntry

    out = defaultdict(set)
    rows = TimetableEntry.objects.filter(academic_year=examination.academic_year).values_list(
        "instructor__staff_member_id", "section_id"
    )
    for staff_id, section_id in rows:
        if staff_id:
            out[staff_id].add(section_id)
    return out


def _staff_name(staff):
    return f"{staff.profile.first_name} {staff.profile.last_name}".strip()


@transaction.atomic
def allocate_invigilators(sitting, *, per_room=2, avoid_own_class=True, staff_ids=None, include_non_teaching=False,
                          request=None):
    """Choose invigilators for every room in use. The first in each room is the chief. Nobody is picked who is on
    approved leave that day, already on duty at an overlapping time, or (optionally) who teaches a class sitting
    in that room. Duties are spread by giving the next place to whoever has the fewest so far in this examination.
    Replaces earlier duties of the sitting; raises AllocationError, changing nothing, when there are too few staff."""
    from staff.models import StaffMember

    if not 1 <= per_room <= 4:
        raise AllocationError("Invigilators per room must be between 1 and 4.")
    sitting = ExamSitting.objects.select_for_update().get(pk=sitting.pk)
    seats = list(ExamSeat.objects.filter(sitting=sitting).select_related("room", "schedule"))
    if not seats:
        raise AllocationError("Allocate rooms for this sitting first.")

    room_sections = defaultdict(set)
    rooms = {}
    for seat in seats:
        rooms[seat.room_id] = seat.room
        room_sections[seat.room_id].add(seat.schedule.section_id)
    ordered_rooms = sorted(rooms.values(), key=lambda r: (-sum(1 for s in seats if s.room_id == r.id), r.name))

    candidates = StaffMember.objects.filter(is_active=True).select_related("profile")
    if staff_ids:
        candidates = candidates.filter(pk__in=staff_ids)
    elif not include_non_teaching:
        candidates = candidates.filter(instructor_record__isnull=False)
    unavailable = _on_leave(sitting.date) | _busy_staff(sitting)
    pool = [s for s in candidates.order_by("employee_id") if s.id not in unavailable]

    teaching = _teaching_sections(sitting.examination) if avoid_own_class else {}
    duties = defaultdict(int)
    for staff_id in ExamInvigilation.objects.filter(sitting__examination=sitting.examination).exclude(
        sitting=sitting
    ).values_list("staff_id", flat=True):
        duties[staff_id] += 1

    chosen, taken, short = [], set(), []
    for room in ordered_rooms:
        sections = room_sections[room.id]
        picked = []
        for _ in range(per_room):
            options = [
                s for s in pool
                if s.id not in taken and not (teaching.get(s.id, set()) & sections)
            ]
            if not options:
                break
            best = min(options, key=lambda s: (duties[s.id], s.employee_id))
            taken.add(best.id)
            duties[best.id] += 1
            picked.append(best)
        if len(picked) < per_room:
            short.append(f"{room.name} (needs {per_room}, found {len(picked)})")
        for index, staff in enumerate(picked):
            chosen.append((room, staff, ExamInvigilation.Role.CHIEF if index == 0 else ExamInvigilation.Role.INVIGILATOR))
    if short:
        raise AllocationError(
            "Not enough available staff for: " + "; ".join(short)
            + ". Staff on leave, already on duty at that time, or teaching those classes are skipped."
        )

    ExamInvigilation.objects.filter(sitting=sitting).delete()
    created_by = getattr(getattr(request, "user", None), "id", None)
    ExamInvigilation.objects.bulk_create(
        [ExamInvigilation(sitting=sitting, room=room, staff=staff, role=role, created_by_id=created_by)
         for room, staff, role in chosen]
    )
    log_action(request, "exam_invigilators_allocated", "ExamSitting", str(sitting.id),
               {"rooms": len(ordered_rooms), "per_room": per_room, "staff": len(chosen)})
    return [staff.id for _, staff, _ in chosen]


@transaction.atomic
def replace_invigilator(invigilation, new_staff, request=None):
    """Swap the person on a duty (someone fell ill). The replacement must be free: not on leave, not already on
    duty at an overlapping time, not already on this sitting."""
    invigilation = ExamInvigilation.objects.select_for_update().select_related("sitting").get(pk=invigilation.pk)
    sitting = invigilation.sitting
    if not new_staff.is_active:
        raise AllocationError("That staff member is not active.")
    if new_staff.id in _on_leave(sitting.date):
        raise AllocationError("That staff member is on approved leave that day.")
    if new_staff.id in _busy_staff(sitting):
        raise AllocationError("That staff member is on duty at an overlapping time.")
    if ExamInvigilation.objects.filter(sitting=sitting, staff=new_staff).exclude(pk=invigilation.pk).exists():
        raise AllocationError("That staff member is already on this sitting.")
    old = invigilation.staff_id
    invigilation.staff = new_staff
    invigilation.save(update_fields=["staff"])
    log_action(request, "exam_invigilator_replaced", "ExamInvigilation", str(invigilation.id),
               {"from": str(old), "to": str(new_staff.id)})
    return invigilation


def notify_invigilators(sitting, staff_ids):
    """An in-app notice to each assigned staff member who has a login."""
    from notifications.services import notify_many
    from staff.models import StaffMember

    rooms = {i.staff_id: i.room.name for i in ExamInvigilation.objects.filter(sitting=sitting, staff_id__in=staff_ids)
             .select_related("room")}
    for staff in StaffMember.objects.filter(pk__in=staff_ids).select_related("profile"):
        user_id = staff.profile.user_id
        if not user_id:
            continue
        notify_many(
            recipient_user_ids=[user_id],
            title=f"Exam duty: {sitting.examination.name}",
            body=(f"{sitting.date:%d %b %Y}, {sitting.start_time:%H:%M}-{sitting.end_time:%H:%M}, "
                  f"room {rooms.get(staff.id, '-')}."),
            category="exam_duty",
            link="/dashboard/examinations/duties",
        )


# --- read models -----------------------------------------------------------------------------


def _student_name(student):
    return f"{student.profile.first_name} {student.profile.last_name}".strip()


def build_sitting_plan(sitting):
    seats = list(
        ExamSeat.objects.filter(sitting=sitting)
        .select_related("room", "student__profile", "schedule__subject", "schedule__section__level")
        .order_by("room__name", "seat_number")
    )
    duties = list(
        ExamInvigilation.objects.filter(sitting=sitting).select_related("room", "staff__profile").order_by("room__name", "role")
    )
    rooms = {}
    for seat in seats:
        entry = rooms.setdefault(
            seat.room_id,
            {"room": {"id": seat.room_id, "name": seat.room.name, "capacity": seat.room.capacity},
             "seats": [], "invigilators": []},
        )
        entry["seats"].append(
            {
                "seat": seat.seat_number,
                "student_id": seat.student_id,
                "student": _student_name(seat.student),
                "enrollment_id": seat.student.enrollment_id,
                "class": f"{seat.schedule.section.level.name} {seat.schedule.section.name}",
                "subject": seat.schedule.subject.name,
            }
        )
    for duty in duties:
        if duty.room_id in rooms:
            rooms[duty.room_id]["invigilators"].append(
                {"id": duty.id, "staff_id": duty.staff_id, "name": _staff_name(duty.staff),
                 "employee_id": duty.staff.employee_id, "role": duty.role}
            )
    seated = {s.student_id for s in seats}
    try:
        expected = {s.id for s, _ in sitting_roster(sitting)}
    except AllocationError:
        expected = set()
    return {
        "sitting": sitting_summary(sitting),
        "rooms": list(rooms.values()),
        "unseated": len(expected - seated),
    }


def sitting_summary(sitting):
    return {
        "id": sitting.id,
        "examination": sitting.examination_id,
        "date": sitting.date,
        "start_time": sitting.start_time,
        "end_time": sitting.end_time,
        "papers": [
            {"schedule": s.id, "subject": s.subject.name, "class": f"{s.section.level.name} {s.section.name}"}
            for s in sitting_schedules(sitting)
        ],
        "seated": ExamSeat.objects.filter(sitting=sitting).count(),
        "rooms_used": ExamSeat.objects.filter(sitting=sitting).values("room_id").distinct().count(),
        "invigilators": ExamInvigilation.objects.filter(sitting=sitting).count(),
    }


def duty_rows(queryset):
    rows = []
    for duty in queryset.select_related("sitting__examination", "room", "staff__profile").order_by(
        "sitting__date", "sitting__start_time", "room__name"
    ):
        rows.append(
            {
                "id": duty.id,
                "staff_id": duty.staff_id,
                "staff": _staff_name(duty.staff),
                "employee_id": duty.staff.employee_id,
                "examination": duty.sitting.examination.name,
                "date": duty.sitting.date,
                "start_time": duty.sitting.start_time,
                "end_time": duty.sitting.end_time,
                "room": duty.room.name,
                "role": duty.role,
            }
        )
    return rows


def build_admit_cards(examination, section):
    """One admit card per student of the section: their papers in date order, each with the room and seat from the
    seating plan. A paper with no seat yet falls back to the room set on the paper itself, then to blank."""
    schedules = list(
        ExamSchedule.objects.filter(examination=examination, section=section)
        .select_related("subject", "room")
        .order_by("date", "start_time")
    )
    students = _roster(section.id)
    seats = {}
    for seat in ExamSeat.objects.filter(
        sitting__examination=examination, student__in=students
    ).select_related("room", "sitting"):
        seats[(seat.student_id, seat.sitting.date, seat.sitting.start_time)] = seat

    cards = []
    for student in students:
        papers = []
        for schedule in schedules:
            seat = seats.get((student.id, schedule.date, schedule.start_time))
            papers.append(
                {
                    "subject": schedule.subject.name,
                    "date": schedule.date,
                    "start_time": schedule.start_time,
                    "end_time": schedule.end_time,
                    "room": seat.room.name if seat else (schedule.room.name if schedule.room else ""),
                    "seat": seat.seat_number if seat else None,
                }
            )
        cards.append(
            {
                "student_id": student.id,
                "name": _student_name(student),
                "enrollment_id": student.enrollment_id,
                "class": f"{section.level.name} {section.name}",
                "papers": papers,
            }
        )
    return {
        "examination": {
            "id": examination.id,
            "name": examination.name,
            "start_date": examination.start_date,
            "end_date": examination.end_date,
        },
        "class": f"{section.level.name} {section.name}",
        "cards": cards,
    }
