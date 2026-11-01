"""How far marks entry has got, paper by paper, and reminders for the teachers who have not finished."""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from core.dates import school_today

from .models import ExamMark, ExamSchedule, Examination

logger = logging.getLogger(__name__)
CATEGORY = "exam_marks"
LINK = "/dashboard/examinations/marks"


def _expected_by_section(section_ids):
    """``{section_id: number of currently enrolled, active students}``."""
    from students.models import Student

    rows = (
        Student.objects.filter(enrollments__is_current=True, enrollments__section_id__in=section_ids, status="active")
        .values("enrollments__section_id")
        .annotate(n=Count("id", distinct=True))
    )
    return {row["enrollments__section_id"]: row["n"] for row in rows}


def _teachers_by_paper(schedules):
    """``{(section_id, subject_id): [Instructor]}`` from the subject assignments."""
    from academics.models import SubjectAssignment

    out = defaultdict(list)
    rows = SubjectAssignment.objects.filter(
        section_id__in={s.section_id for s in schedules}, subject_id__in={s.subject_id for s in schedules}
    ).select_related("instructor__staff_member__profile")
    for row in rows:
        out[(row.section_id, row.subject_id)].append(row.instructor)
    return out


def _name(instructor):
    profile = instructor.staff_member.profile
    return f"{profile.first_name} {profile.last_name}".strip()


def schedule_progress(examination, today=None):
    """Rows for every paper of the examination plus a summary. A paper's mark counts as entered once it has a score
    or the student is recorded as absent, on medical leave, in malpractice or exempt."""
    today = today or school_today()
    schedules = list(
        ExamSchedule.objects.filter(examination=examination)
        .select_related("subject", "section__level")
        .annotate(
            entered=Count(
                "marks",
                filter=Q(marks__marks_obtained__isnull=False) | ~Q(marks__attendance=ExamMark.Attendance.PRESENT),
            )
        )
        .order_by("date", "section__level__name", "section__name", "subject__name")
    )
    expected = _expected_by_section({s.section_id for s in schedules})
    teachers = _teachers_by_paper(schedules)
    due = examination.marks_due_date

    rows, summary = [], {"papers": 0, "complete": 0, "in_progress": 0, "not_started": 0, "overdue": 0}
    for schedule in schedules:
        total = expected.get(schedule.section_id, 0)
        entered = min(schedule.entered, total) if total else schedule.entered
        if total and entered >= total:
            state = "complete"
        elif entered > 0:
            state = "in_progress"
        else:
            state = "not_started"
        # A locked paper has been signed off, so it is never chased.
        overdue = bool(due and today > due and state != "complete" and not schedule.is_locked)
        rows.append(
            {
                "schedule": schedule.id,
                "subject": schedule.subject.name,
                "class": f"{schedule.section.level.name} {schedule.section.name}",
                "date": schedule.date,
                "teachers": [_name(t) for t in teachers.get((schedule.section_id, schedule.subject_id), [])],
                "expected": total,
                "entered": entered,
                "state": state,
                "locked": schedule.is_locked,
                "overdue": overdue,
            }
        )
        summary["papers"] += 1
        summary[state] += 1
        summary["overdue"] += int(overdue)
    return {"due_date": due, "summary": summary, "rows": rows}


def remind_pending_marks(examination, today=None):
    """One in-app notice to each assigned teacher who still has papers to finish, listing them. A teacher who was
    already reminded about this examination in the last 20 hours is not reminded again, so pressing the button twice
    or an overlapping daily run does not repeat it. Returns a summary."""
    from notifications.models import Notification
    from notifications.services import notify

    today = today or school_today()
    progress = schedule_progress(examination, today)
    pending = [r for r in progress["rows"] if r["state"] != "complete" and not r["locked"]]
    summary = {"teachers": 0, "papers": len(pending), "unassigned": 0, "already_reminded": 0}
    if not pending:
        return summary

    schedules = {s.id: s for s in ExamSchedule.objects.filter(pk__in=[r["schedule"] for r in pending])}
    teachers = _teachers_by_paper(list(schedules.values()))
    per_teacher = defaultdict(list)
    for row in pending:
        schedule = schedules[row["schedule"]]
        assigned = teachers.get((schedule.section_id, schedule.subject_id), [])
        if not assigned:
            summary["unassigned"] += 1
        for instructor in assigned:
            per_teacher[instructor].append(row)

    due = examination.marks_due_date
    window = timezone.now() - timedelta(hours=20)
    for instructor, rows in per_teacher.items():
        user_id = instructor.staff_member.profile.user_id
        if not user_id:
            continue
        title = f"Marks pending: {examination.name}"
        if Notification.objects.filter(
            recipient_user_id=user_id, category=CATEGORY, title=title, created_at__gte=window
        ).exists():
            summary["already_reminded"] += 1
            continue
        listed = ", ".join(f"{r['subject']} {r['class']} ({r['entered']}/{r['expected']})" for r in rows[:5])
        more = f" and {len(rows) - 5} more" if len(rows) > 5 else ""
        if due:
            when = f" It was due on {due:%d %b %Y}." if today > due else f" Due on {due:%d %b %Y}."
        else:
            when = ""
        notify(
            recipient_user_id=user_id,
            title=title[:200],
            body=f"Please finish entering marks for {listed}{more}.{when}"[:500],
            category=CATEGORY,
            link=LINK,
        )
        summary["teachers"] += 1
    return summary


def remind_all_schools():
    """The daily job body for one school: chase every unpublished examination whose marks are due within a day or
    already late."""
    today = school_today()
    totals = {"examinations": 0, "teachers": 0}
    for examination in Examination.objects.filter(is_published=False, marks_due_date__isnull=False,
                                                 marks_due_date__lte=today + timedelta(days=1)):
        result = remind_pending_marks(examination, today)
        totals["examinations"] += 1
        totals["teachers"] += result["teachers"]
    return totals
