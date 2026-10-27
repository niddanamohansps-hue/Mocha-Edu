"""
Marks integrity: every change to a mark is kept with who, when and why (ExamMarkChange); grace marks; recheck
requests after publication; and marks import from a CSV file.

Rules:
* Marks of a published examination are not edited directly. They change only through a recheck or grace marks,
  and either one updates that student's published result at the same moment, on record.
* Changing a mark that was already entered on a locked schedule needs a reason.
* Grace marks never take a mark above the schedule's maximum, and always need a reason.
"""
import csv
import io
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import ExamMark, ExamMarkChange, ExamResult, RecheckRequest

NOT_SAT = ExamMark.NOT_SAT
ATTENDANCE_VALUES = {choice for choice, _ in ExamMark.Attendance.choices}


def _same(a, b):
    return (a is None and b is None) or (a is not None and b is not None and Decimal(a) == Decimal(b))


def normalise_record(record):
    """Fills attendance from is_absent (older clients) or is_absent from attendance; clears marks when not sat."""
    attendance = record.get("attendance") or ("absent" if record.get("is_absent") else "present")
    record["attendance"] = attendance
    record["is_absent"] = attendance in NOT_SAT
    if attendance != "present":
        record["marks_obtained"] = None
    return record


@transaction.atomic
def record_marks(schedule, records, *, entered_by, user_id, kind=ExamMarkChange.Kind.ENTRY, reason="", require_reason=False):
    """Creates or updates one schedule's marks and writes a history row for each mark that is new or changed.
    Unchanged resubmissions write nothing. Returns a summary of what happened."""
    existing = {str(m.student_id): m for m in ExamMark.objects.select_for_update().filter(exam_schedule=schedule)}
    reason = (reason or "").strip()

    changed = [
        (existing[str(r["student"])], r) for r in records
        if str(r["student"]) in existing and (
            not _same(existing[str(r["student"])].marks_obtained, r.get("marks_obtained"))
            or existing[str(r["student"])].attendance != r["attendance"]
        )
    ]
    # A locked schedule's entered marks are final unless someone says why they change.
    if require_reason and not reason and any(
        row.marks_obtained is not None or row.attendance != "present" for row, _ in changed
    ):
        raise serializers.ValidationError({"reason": ["This schedule is locked. Give a reason for changing marks."]})

    created, updated, history = [], [], []
    for record in records:
        student_id = str(record["student"])
        row = existing.get(student_id)
        if row is None:
            row = ExamMark(
                exam_schedule=schedule, student_id=student_id, marks_obtained=record.get("marks_obtained"),
                is_absent=record["is_absent"], attendance=record["attendance"], remarks=record.get("remarks", ""),
                entered_by=entered_by,
            )
            created.append(row)
            history.append(ExamMarkChange(
                mark=row, kind=kind, new_marks=row.marks_obtained, new_attendance=row.attendance,
                reason=reason, changed_by_user_id=user_id,
            ))
            continue
        old_marks, old_attendance = row.marks_obtained, row.attendance
        row.marks_obtained = record.get("marks_obtained")
        row.is_absent = record["is_absent"]
        row.attendance = record["attendance"]
        row.remarks = record.get("remarks", "")
        row.entered_by = entered_by
        updated.append(row)
        if not _same(old_marks, row.marks_obtained) or old_attendance != row.attendance:
            history.append(ExamMarkChange(
                mark=row, kind=ExamMarkChange.Kind.CORRECTION if kind == ExamMarkChange.Kind.ENTRY else kind,
                old_marks=old_marks, new_marks=row.marks_obtained, old_attendance=old_attendance,
                new_attendance=row.attendance, old_grace=row.grace_marks, new_grace=row.grace_marks,
                reason=reason, changed_by_user_id=user_id,
            ))

    if created:
        ExamMark.objects.bulk_create(created)
    if updated:
        ExamMark.objects.bulk_update(updated, ["marks_obtained", "is_absent", "attendance", "remarks", "entered_by", "updated_at"])
    if history:
        ExamMarkChange.objects.bulk_create(history)

    return {
        "created": len(created),
        "updated": len(updated),
        "changed": len(changed),
        "absent": sum(1 for r in records if r["is_absent"]),
        "total": len(records),
    }


def refresh_published_result(examination, student):
    """Recalculates one student's published result after a recheck or grace marks. The old snapshot is replaced
    deliberately and the change is on record in the mark's history; nothing else in the result is touched."""
    from .services import calculate_student_examination_result

    if not examination.is_published:
        return None
    result = calculate_student_examination_result(examination, student)
    if result is None:
        return None
    ExamResult.objects.filter(examination=examination, student=student).update(
        total_marks_obtained=result["total_marks_obtained"],
        total_max_marks=result["total_max_marks"],
        percentage=result["percentage"],
        overall_grade=result["overall_grade"],
        is_pass=result["is_pass"],
        subject_breakdown=result["subject_breakdown"],
    )
    return result


def _locked_mark(mark_id):
    return ExamMark.objects.select_for_update(of=("self",)).select_related(
        "exam_schedule__examination", "exam_schedule__subject", "student"
    ).get(pk=mark_id)


@transaction.atomic
def apply_grace(mark, grace, reason, user_id):
    """Sets a mark's grace marks (replacing any earlier grace). Needs a reason; never above the maximum."""
    mark = _locked_mark(mark.pk)
    reason = (reason or "").strip()
    if not reason:
        raise serializers.ValidationError({"reason": ["Give a reason for grace marks."]})
    if grace < 0:
        raise serializers.ValidationError({"grace_marks": ["Grace marks cannot be negative."]})
    if mark.attendance != "present" or mark.marks_obtained is None:
        raise serializers.ValidationError({"grace_marks": ["Grace marks need entered marks for a student who sat the exam."]})
    room = mark.exam_schedule.max_marks - mark.marks_obtained
    if grace > room:
        raise serializers.ValidationError({"grace_marks": [f"At most {room} grace marks fit under the maximum of {mark.exam_schedule.max_marks}."]})
    if _same(grace, mark.grace_marks):
        return mark
    ExamMarkChange.objects.create(
        mark=mark, kind=ExamMarkChange.Kind.GRACE, old_marks=mark.marks_obtained, new_marks=mark.marks_obtained,
        old_attendance=mark.attendance, new_attendance=mark.attendance, old_grace=mark.grace_marks,
        new_grace=grace, reason=reason, changed_by_user_id=user_id,
    )
    mark.grace_marks = grace
    mark.save(update_fields=["grace_marks", "updated_at"])
    refresh_published_result(mark.exam_schedule.examination, mark.student)
    return mark


@transaction.atomic
def request_recheck(mark, reason, user_id):
    mark = _locked_mark(mark.pk)
    reason = (reason or "").strip()
    if not reason:
        raise serializers.ValidationError({"reason": ["Say what should be re-checked."]})
    if not mark.exam_schedule.examination.is_published:
        raise serializers.ValidationError({"non_field_errors": ["A recheck can be asked for once results are published."]})
    if mark.attendance != "present" or mark.marks_obtained is None:
        raise serializers.ValidationError({"non_field_errors": ["Only marks that were entered can be re-checked."]})
    if mark.rechecks.filter(status=RecheckRequest.Status.PENDING).exists():
        raise serializers.ValidationError({"non_field_errors": ["A recheck of this mark is already waiting."]})
    return RecheckRequest.objects.create(
        mark=mark, reason=reason[:1000], original_marks=mark.marks_obtained, requested_by_user_id=user_id,
    )


@transaction.atomic
def decide_recheck(recheck, *, accept, revised_marks, comment, user_id):
    recheck = RecheckRequest.objects.select_for_update().get(pk=recheck.pk)
    if recheck.status != RecheckRequest.Status.PENDING:
        raise serializers.ValidationError({"non_field_errors": ["This recheck has already been decided."]})
    comment = (comment or "").strip()
    mark = _locked_mark(recheck.mark_id)
    if accept:
        if revised_marks is None:
            raise serializers.ValidationError({"revised_marks": ["Enter the marks after the recheck."]})
        if revised_marks < 0 or revised_marks > mark.exam_schedule.max_marks:
            raise serializers.ValidationError({"revised_marks": [f"Marks must be between 0 and {mark.exam_schedule.max_marks}."]})
        if mark.grace_marks and revised_marks + mark.grace_marks > mark.exam_schedule.max_marks:
            raise serializers.ValidationError({"revised_marks": ["With the existing grace marks this goes above the maximum. Reduce the grace marks first."]})
        if not _same(revised_marks, mark.marks_obtained):
            ExamMarkChange.objects.create(
                mark=mark, kind=ExamMarkChange.Kind.RECHECK, old_marks=mark.marks_obtained, new_marks=revised_marks,
                old_attendance=mark.attendance, new_attendance=mark.attendance, old_grace=mark.grace_marks,
                new_grace=mark.grace_marks, reason=(comment or recheck.reason)[:500], changed_by_user_id=user_id,
            )
            mark.marks_obtained = revised_marks
            mark.save(update_fields=["marks_obtained", "updated_at"])
            refresh_published_result(mark.exam_schedule.examination, mark.student)
        recheck.status = RecheckRequest.Status.ACCEPTED
        recheck.revised_marks = revised_marks
    else:
        if not comment:
            raise serializers.ValidationError({"decision_comment": ["Say why the recheck is rejected."]})
        recheck.status = RecheckRequest.Status.REJECTED
    recheck.decision_comment = comment[:1000]
    recheck.decided_by_user_id = user_id
    recheck.decided_at = timezone.now()
    recheck.save()
    return recheck


# --- CSV import ---------------------------------------------------------------------------------

MAX_IMPORT_BYTES = 512 * 1024
ATTENDANCE_WORDS = {
    "": "present", "present": "present", "p": "present",
    "absent": "absent", "a": "absent", "ab": "absent",
    "medical": "medical", "m": "medical",
    "malpractice": "malpractice",
    "exempt": "exempt", "ex": "exempt",
}


def parse_marks_csv(schedule, upload):
    """Reads a CSV with columns enrollment_id, marks and optionally attendance and remarks. Returns
    (records, rows, errors): records are ready for record_marks; rows describe each line for a preview; errors
    name each bad line. Nothing is saved here."""
    from students.models import Student

    from .services import get_section_roster_student_ids

    if upload.size > MAX_IMPORT_BYTES:
        return [], [], ["The file is larger than 512 KB."]
    raw = upload.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [], ["Save the file as CSV (UTF-8) and try again."]

    reader = csv.DictReader(io.StringIO(text))
    headers = {(h or "").strip().lower() for h in (reader.fieldnames or [])}
    if not {"enrollment_id", "marks"} <= headers:
        return [], [], ["The first row must name the columns enrollment_id and marks (attendance and remarks are optional)."]

    roster = get_section_roster_student_ids(schedule.section_id)
    students = {
        s.enrollment_id.strip().lower(): s
        for s in Student.objects.filter(id__in=roster).select_related("profile")
    }
    records, rows, errors, seen = [], [], [], set()
    for line, raw_row in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}
        if not any(row.values()):
            continue
        enrollment = row.get("enrollment_id", "")
        student = students.get(enrollment.lower())
        if student is None:
            errors.append(f"Line {line}: {enrollment or '(blank)'} is not a current student of this section.")
            continue
        if student.id in seen:
            errors.append(f"Line {line}: {enrollment} appears more than once.")
            continue
        seen.add(student.id)
        attendance = ATTENDANCE_WORDS.get(row.get("attendance", "").lower())
        if attendance is None:
            errors.append(f"Line {line}: attendance must be present, absent, medical, malpractice or exempt.")
            continue
        marks = None
        if attendance == "present" and row.get("marks", "") != "":
            try:
                marks = Decimal(row["marks"])
            except InvalidOperation:
                errors.append(f"Line {line}: marks must be a number.")
                continue
            if not marks.is_finite() or marks < 0 or marks > schedule.max_marks:
                errors.append(f"Line {line}: marks must be between 0 and {schedule.max_marks}.")
                continue
            if marks != marks.quantize(Decimal("0.01")):
                errors.append(f"Line {line}: marks can have at most two decimal places.")
                continue
        remarks = row.get("remarks", "")[:255]
        records.append(normalise_record({"student": student.id, "marks_obtained": marks, "attendance": attendance, "remarks": remarks}))
        rows.append({
            "line": line, "enrollment_id": student.enrollment_id,
            "student_name": f"{student.profile.first_name} {student.profile.last_name}".strip(),
            "marks": str(marks) if marks is not None else None, "attendance": attendance,
        })
    if not records and not errors:
        errors.append("The file has no rows of marks.")
    return records, rows, errors
