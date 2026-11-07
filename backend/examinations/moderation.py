"""Marks moderation: adjusting a whole paper's marks together (add or scale), with a preview first.

Rules: only before results are published (afterwards a mark changes only through a recheck or grace marks); only
marks of students who sat the paper and have a score; papers split into score parts are not moderated here because
their parts would no longer add up; a mark never goes below 0 or above the maximum less any grace marks already
given; and every change is kept, with who and why, in the mark's history.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction

from core.audit import log_action

from .models import ExamMark, ExamMarkChange, Examination

STEPS = {Decimal("1"), Decimal("0.5"), Decimal("0.25"), Decimal("0.01")}
METHODS = ("add", "scale")
MIN_REASON = 5


class ModerationError(Exception):
    """The moderation cannot be done as asked. Nothing was changed."""


def _decimal(value, name):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ModerationError(f"{name} must be a number.")


def _check_schedule(schedule):
    # Read the flag fresh: a cached copy of the examination could be out of date.
    if Examination.objects.filter(pk=schedule.examination_id, is_published=True).exists():
        raise ModerationError("The results are published, so marks can no longer be moderated. Use a recheck or grace marks.")
    if schedule.components.exists():
        raise ModerationError("This paper is split into score parts, so its marks cannot be moderated together.")


def _plan(schedule, *, method, value, step, below):
    """What moderation would do, without changing anything. Returns ``(rows, summary)``."""
    _check_schedule(schedule)
    if method not in METHODS:
        raise ModerationError("Choose to add marks or to multiply them.")
    value = _decimal(value, "The amount")
    step = _decimal(step, "The rounding")
    if step not in STEPS:
        raise ModerationError("Round to 1, 0.5, 0.25 or 0.01 marks.")
    if method == "scale" and value <= 0:
        raise ModerationError("The multiplier must be more than zero.")
    below = _decimal(below, "The limit") if below not in (None, "") else None

    max_marks = Decimal(schedule.max_marks)
    pass_marks = Decimal(schedule.pass_marks)
    marks = list(
        ExamMark.objects.filter(exam_schedule=schedule, attendance=ExamMark.Attendance.PRESENT, marks_obtained__isnull=False)
        .select_related("student__profile").order_by("student__enrollment_id")
    )

    rows, capped = [], 0
    for mark in marks:
        old = Decimal(mark.marks_obtained)
        grace = Decimal(mark.grace_marks or 0)
        if below is not None and old >= below:
            continue
        raw = old + value if method == "add" else old * value
        new = (raw / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
        ceiling = max_marks - grace  # grace marks already given count towards the maximum
        limited = max(Decimal("0"), min(new, ceiling))
        capped += int(limited != new)
        if limited == old:
            continue
        before = min(old + grace, max_marks)
        after = min(limited + grace, max_marks)
        rows.append(
            {
                "mark_id": mark.id,
                "student_id": mark.student_id,
                "name": f"{mark.student.profile.first_name} {mark.student.profile.last_name}".strip(),
                "enrollment_id": mark.student.enrollment_id,
                "old": old,
                "new": limited,
                "passed_before": before >= pass_marks,
                "passed_after": after >= pass_marks,
            }
        )

    before_all = [min(Decimal(m.marks_obtained) + Decimal(m.grace_marks or 0), max_marks) for m in marks]
    changed_to = {r["mark_id"]: r["new"] for r in rows}
    after_all = [
        min((changed_to.get(m.id, Decimal(m.marks_obtained))) + Decimal(m.grace_marks or 0), max_marks) for m in marks
    ]
    summary = {
        "students_with_marks": len(marks),
        "changed": len(rows),
        "capped": capped,
        "passed_before": sum(1 for v in before_all if v >= pass_marks),
        "passed_after": sum(1 for v in after_all if v >= pass_marks),
        "average_before": round(float(sum(before_all) / len(before_all)), 2) if before_all else None,
        "average_after": round(float(sum(after_all) / len(after_all)), 2) if after_all else None,
        "max_marks": max_marks,
        "pass_marks": pass_marks,
    }
    return rows, summary


def preview_moderation(schedule, *, method, value, step="1", below=None):
    rows, summary = _plan(schedule, method=method, value=value, step=step, below=below)
    return {"schedule": str(schedule.id), "summary": summary, "rows": rows}


@transaction.atomic
def apply_moderation(schedule, *, method, value, reason, user_id, request=None, step="1", below=None, expected_changed=None):
    """Make the preview's changes. ``expected_changed`` is the number the person saw in the preview: if the marks
    have moved since, nothing is applied and they are asked to preview again."""
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON:
        raise ModerationError("Give a reason for the moderation.")
    # Lock the marks so nobody edits them between working out the change and writing it.
    list(ExamMark.objects.select_for_update().filter(exam_schedule=schedule))
    rows, summary = _plan(schedule, method=method, value=value, step=step, below=below)
    if not rows:
        raise ModerationError("Nothing would change.")
    if expected_changed is not None and int(expected_changed) != len(rows):
        raise ModerationError("The marks have changed since the preview. Preview again before applying.")

    by_id = {m.id: m for m in ExamMark.objects.filter(pk__in=[r["mark_id"] for r in rows])}
    history = []
    for row in rows:
        mark = by_id[row["mark_id"]]
        mark.marks_obtained = row["new"]
        history.append(
            ExamMarkChange(
                mark=mark, kind=ExamMarkChange.Kind.MODERATION, old_marks=row["old"], new_marks=row["new"],
                old_attendance=mark.attendance, new_attendance=mark.attendance,
                old_grace=mark.grace_marks, new_grace=mark.grace_marks, reason=reason[:500], changed_by_user_id=user_id,
            )
        )
    ExamMark.objects.bulk_update(list(by_id.values()), ["marks_obtained", "updated_at"])
    ExamMarkChange.objects.bulk_create(history)
    log_action(
        request, "marks_moderated", "ExamSchedule", str(schedule.id),
        {"method": method, "value": str(value), "changed": len(rows), "reason": reason[:200]},
    )
    return {"changed": len(rows), "summary": summary}
