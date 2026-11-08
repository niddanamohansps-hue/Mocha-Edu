"""Exam-hall attendance: the invigilator records who sat the paper, room by room.

Marking a student absent also records them as absent on the marks sheet, so the teacher entering marks does not have
to find out. It never overwrites real work: a student who already has a score, was recorded as medical, malpractice
or exempt, or whose paper is locked is reported back as a conflict and left as the marks sheet has them. Marking
someone present again undoes an absence the hall recorded. Nothing can be changed once results are published.
"""
from django.db import transaction
from django.utils import timezone

from core.audit import log_action

from .marks import record_marks
from .models import ExamInvigilation, ExamMark, ExamMarkChange, ExamSeat, ExamSitting, Examination


HALL_ABSENT_REASON = "Marked absent in the exam hall"


class HallError(Exception):
    """The request cannot be done. Nothing was changed."""


def may_mark(user, sitting, room, *, is_manager):
    """Whoever manages exam allocation, or a staff member on duty in this room for this sitting."""
    if is_manager:
        return True
    return ExamInvigilation.objects.filter(sitting=sitting, room=room, staff__profile__user_id=user.id).exists()


def room_attendance(sitting, room):
    seats = (
        ExamSeat.objects.filter(sitting=sitting, room=room)
        .select_related("student__profile", "schedule__subject", "schedule__section__level")
        .order_by("seat_number")
    )
    return {
        "sitting": {
            "id": sitting.id,
            "examination": sitting.examination.name,
            "date": sitting.date,
            "start_time": sitting.start_time,
            "end_time": sitting.end_time,
        },
        "room": {"id": room.id, "name": room.name},
        "rows": [
            {
                "student_id": s.student_id,
                "name": f"{s.student.profile.first_name} {s.student.profile.last_name}".strip(),
                "enrollment_id": s.student.enrollment_id,
                "class": f"{s.schedule.section.level.name} {s.schedule.section.name}",
                "subject": s.schedule.subject.name,
                "seat": s.seat_number,
                "status": s.hall_status,
            }
            for s in seats
        ],
    }


def _apply_to_marks(seat, absent, user_id):
    """Reflect one student's hall status on the marks sheet. Returns a conflict message, or None."""
    schedule = seat.schedule
    if schedule.is_locked:
        return "This paper is locked, so its marks sheet was not changed."
    mark = ExamMark.objects.filter(exam_schedule=schedule, student=seat.student).first()
    if absent:
        if mark is not None and (mark.marks_obtained is not None or mark.attendance not in ("present", "absent")):
            if mark.attendance == "absent":
                return None
            return "This student already has a score or a recorded status on the marks sheet, which was left as it is."
        record = {"student": str(seat.student_id), "attendance": "absent", "is_absent": True, "marks_obtained": None}
    else:
        if mark is None or mark.attendance != "absent":
            return None  # nothing the hall recorded needs undoing
        last = ExamMarkChange.objects.filter(mark=mark).order_by("-created_at").first()
        if last is None or last.reason != HALL_ABSENT_REASON:
            # The teacher recorded this absence, not the hall, so the hall does not overrule it.
            return "The marks sheet shows this student absent for another reason, which was left as it is."
        record = {"student": str(seat.student_id), "attendance": "present", "is_absent": False, "marks_obtained": None}
    record_marks(
        schedule, [record], entered_by=None, user_id=user_id, kind=ExamMarkChange.Kind.ENTRY,
        reason=HALL_ABSENT_REASON if absent else "Marked present in the exam hall",
    )
    return None


@transaction.atomic
def mark_attendance(sitting, room, records, *, user, request=None):
    if Examination.objects.filter(pk=sitting.examination_id, is_published=True).exists():
        raise HallError("The results are published, so attendance can no longer be changed.")
    if not records:
        raise HallError("Choose who was present and who was absent.")

    seats = {
        str(s.student_id): s
        for s in ExamSeat.objects.select_for_update(of=("self",)).select_related("schedule", "student__profile").filter(sitting=sitting, room=room)
    }
    parsed = []
    for record in records:
        student_id, status = str(record.get("student")), record.get("status")
        if status not in ("present", "absent"):
            raise HallError("Each student must be marked present or absent.")
        if student_id not in seats:
            raise HallError("A student in the list is not seated in this room for this sitting.")
        parsed.append((seats[student_id], status))

    now = timezone.now()
    conflicts, absent_count = [], 0
    for seat, status in parsed:
        seat.hall_status, seat.hall_marked_by_user_id, seat.hall_marked_at = status, getattr(user, "id", None), now
        seat.save(update_fields=["hall_status", "hall_marked_by_user_id", "hall_marked_at"])
        absent_count += int(status == "absent")
        problem = _apply_to_marks(seat, status == "absent", getattr(user, "id", None))
        if problem:
            conflicts.append(
                {
                    "student_id": seat.student_id,
                    "name": f"{seat.student.profile.first_name} {seat.student.profile.last_name}".strip(),
                    "problem": problem,
                }
            )
    log_action(
        request, "exam_hall_attendance_marked", "ExamSitting", str(sitting.id),
        {"room": str(room.id), "students": len(parsed), "absent": absent_count},
    )
    return {"saved": len(parsed), "absent": absent_count, "conflicts": conflicts}


# ---- the room report: scripts collected and incidents -----------------------------------------


def _counts(sitting, room):
    """``(seated, absent)`` for a room at a sitting, from the seating plan and the hall attendance."""
    seats = ExamSeat.objects.filter(sitting=sitting, room=room)
    return seats.count(), seats.filter(hall_status="absent").count()


def room_report(sitting, room):
    """The report as it stands, with how many scripts were expected: everyone seated except those the hall marked
    absent (someone not yet marked is assumed to have sat)."""
    from .models import ExamRoomReport

    seated, absent = _counts(sitting, room)
    expected = seated - absent
    report = ExamRoomReport.objects.filter(sitting=sitting, room=room).first()
    return {
        "seated": seated,
        "absent": absent,
        "expected": expected,
        "submitted": report is not None,
        "scripts_collected": report.scripts_collected if report else None,
        "difference": (report.scripts_collected - expected) if report else None,
        "incidents": report.incidents if report else "",
        "submitted_by": report.submitted_by_name if report else "",
        "submitted_at": report.updated_at if report else None,
    }


@transaction.atomic
def submit_room_report(sitting, room, *, scripts_collected, incidents, user, request=None):
    from .models import ExamRoomReport

    if Examination.objects.filter(pk=sitting.examination_id, is_published=True).exists():
        raise HallError("The results are published, so this report can no longer be changed.")
    try:
        scripts = int(scripts_collected)
    except (TypeError, ValueError):
        raise HallError("Enter the number of scripts collected.")
    seated, _ = _counts(sitting, room)
    if not seated:
        raise HallError("Nobody is seated in this room for this sitting.")
    if scripts < 0 or scripts > seated:
        raise HallError(f"The scripts collected must be between 0 and the {seated} students seated in this room.")

    ExamRoomReport.objects.update_or_create(
        sitting=sitting, room=room,
        defaults={
            "scripts_collected": scripts,
            "incidents": (incidents or "").strip(),
            "submitted_by_user_id": getattr(user, "id", None),
            "submitted_by_name": user.get_username() if getattr(user, "is_authenticated", False) else "",
        },
    )
    log_action(request, "exam_room_report_submitted", "ExamSitting", str(sitting.id),
               {"room": str(room.id), "scripts": scripts, "has_incidents": bool((incidents or "").strip())})
    return room_report(sitting, room)


def room_reports_overview(examination):
    """Every room of every sitting of an examination, with whether it has reported and whether its count matches."""
    from .models import ExamRoomReport

    rows = []
    for sitting in ExamSitting.objects.filter(examination=examination):
        for room_id in ExamSeat.objects.filter(sitting=sitting).values_list("room_id", flat=True).distinct():
            seats = ExamSeat.objects.filter(sitting=sitting, room_id=room_id)
            seated = seats.count()
            absent = seats.filter(hall_status="absent").count()
            report = ExamRoomReport.objects.filter(sitting=sitting, room_id=room_id).select_related("room").first()
            room = report.room if report else seats.select_related("room").first().room
            expected = seated - absent
            rows.append(
                {
                    "sitting": sitting.id,
                    "room_id": room_id,
                    "room": room.name,
                    "date": sitting.date,
                    "start_time": sitting.start_time,
                    "end_time": sitting.end_time,
                    "seated": seated,
                    "absent": absent,
                    "expected": expected,
                    "submitted": report is not None,
                    "scripts_collected": report.scripts_collected if report else None,
                    "difference": (report.scripts_collected - expected) if report else None,
                    "has_incidents": bool(report and report.incidents),
                    "incidents": report.incidents if report else "",
                }
            )
    rows.sort(key=lambda r: (r["date"], r["start_time"], r["room"]))
    return rows
