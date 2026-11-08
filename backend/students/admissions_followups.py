"""The admissions follow-up desk: which enquiries are due a call, recording what happened, and the daily reminder.

An enquiry is "open" while it is new, contacted or qualified. Converted and closed enquiries are finished and never
appear here.
"""
from datetime import timedelta

from django.utils import timezone

from core.audit import log_action
from core.dates import school_today

from .models import AdmissionEnquiry

OPEN = ("new", "contacted", "qualified")
CATEGORY = "admissions"
LINK = "/dashboard/students/admissions/follow-ups"
OUTCOMES = ("contacted", "qualified", "lost")
UNSCHEDULED_AFTER_DAYS = 2  # an open enquiry with no follow-up date is flagged once it is this old
UPCOMING_DAYS = 7


class FollowUpError(Exception):
    """The follow-up cannot be recorded; the message is shown to the user."""


def _row(enquiry, today):
    assigned = None
    if enquiry.assigned_to_id and hasattr(enquiry.assigned_to, "profile"):
        profile = enquiry.assigned_to.profile
        assigned = f"{profile.first_name} {profile.last_name}".strip()
    due = enquiry.follow_up_date
    return {
        "id": enquiry.id,
        "enquiry_number": enquiry.enquiry_number,
        "student_name": enquiry.student_name,
        "guardian_name": enquiry.guardian_name,
        "guardian_phone": enquiry.guardian_phone,
        "level": enquiry.preferred_level.name if enquiry.preferred_level_id else "",
        "source": enquiry.source,
        "status": enquiry.status,
        "assigned_to": enquiry.assigned_to_id,
        "assigned_to_name": assigned,
        "enquiry_date": enquiry.enquiry_date,
        "follow_up_date": due,
        "days_overdue": (today - due).days if due and due < today else 0,
        "notes": enquiry.notes,
    }


def followups_data(*, assigned_to=None, today=None):
    """Open enquiries sorted into overdue, due today, upcoming (the next week) and unscheduled (old enough with no
    follow-up date). ``assigned_to`` narrows to one staff member's enquiries."""
    today = today or school_today()
    qs = AdmissionEnquiry.objects.filter(status__in=OPEN).select_related("preferred_level", "assigned_to__profile")
    if assigned_to is not None:
        qs = qs.filter(assigned_to=assigned_to)
    groups = {"overdue": [], "today": [], "upcoming": [], "unscheduled": []}
    for enquiry in qs.order_by("follow_up_date", "enquiry_date"):
        due = enquiry.follow_up_date
        if due is None:
            if enquiry.enquiry_date <= today - timedelta(days=UNSCHEDULED_AFTER_DAYS):
                groups["unscheduled"].append(_row(enquiry, today))
        elif due < today:
            groups["overdue"].append(_row(enquiry, today))
        elif due == today:
            groups["today"].append(_row(enquiry, today))
        elif due <= today + timedelta(days=UPCOMING_DAYS):
            groups["upcoming"].append(_row(enquiry, today))
    groups["summary"] = {key: len(value) for key, value in groups.items()}
    return groups


def record_followup(enquiry, *, outcome, note, next_date, user, request=None):
    """Note what happened on a call or visit and set when to follow up next.

    ``contacted`` and ``qualified`` move the enquiry on (never backwards) and may set the next date; ``lost`` closes
    it and needs the reason in the note. The note is added to the enquiry's notes with the date and who wrote it."""
    if enquiry.status not in OPEN:
        raise FollowUpError("This enquiry is already finished.")
    if outcome not in OUTCOMES:
        raise FollowUpError("Choose what happened: contacted, qualified or lost.")
    note = " ".join((note or "").split())
    if not note:
        raise FollowUpError("Write a short note of what was said." if outcome != "lost" else "Say why the enquiry is lost.")
    if len(note) > 500:
        raise FollowUpError("Keep the note under 500 characters.")
    today = school_today()
    if next_date is not None and outcome != "lost":
        if next_date < today:
            raise FollowUpError("The next follow-up cannot be in the past.")
        if next_date > today + timedelta(days=365):
            raise FollowUpError("The next follow-up is more than a year away.")
    else:
        next_date = None

    label = {"contacted": "Contacted", "qualified": "Qualified", "lost": "Closed as lost"}[outcome]
    who = user.get_username() if getattr(user, "is_authenticated", False) else ""
    line = f"[{today:%d %b %Y}, {who}] {label}: {note}"
    before = enquiry.status
    if outcome == "lost":
        enquiry.status = "closed"
    elif outcome == "qualified":
        enquiry.status = "qualified"
    elif enquiry.status == "new":
        enquiry.status = "contacted"
    enquiry.follow_up_date = next_date
    enquiry.notes = f"{enquiry.notes}\n{line}".strip()
    enquiry.save(update_fields=["status", "follow_up_date", "notes", "updated_at"])
    log_action(
        request, action="CHANGE", model_name="AdmissionEnquiry", object_id=enquiry.id,
        changes={"followup": outcome, "status": [before, enquiry.status],
                 "next": next_date.isoformat() if next_date else None},
    )
    return enquiry


def remind_followups(today=None):
    """One in-app notice per assigned staff member with follow-ups due today or overdue. Someone already reminded in
    the last 20 hours is not reminded again, so an overlapping run or a retry does not repeat it. Enquiries with
    nobody assigned are only counted: they show on the desk for whoever has the permission."""
    from notifications.models import Notification
    from notifications.services import notify

    today = today or school_today()
    summary = {"staff": 0, "enquiries": 0, "unassigned": 0, "already_reminded": 0}
    window = timezone.now() - timedelta(hours=20)
    per_staff = {}
    for enquiry in AdmissionEnquiry.objects.filter(
        status__in=OPEN, follow_up_date__isnull=False, follow_up_date__lte=today
    ).select_related("assigned_to__profile"):
        summary["enquiries"] += 1
        if enquiry.assigned_to_id is None:
            summary["unassigned"] += 1
            continue
        per_staff.setdefault(enquiry.assigned_to, []).append(enquiry)

    title = "Admission follow-ups due"
    for staff, enquiries in per_staff.items():
        user_id = staff.profile.user_id
        if not user_id:
            continue
        if Notification.objects.filter(
            recipient_user_id=user_id, category=CATEGORY, title=title, created_at__gte=window
        ).exists():
            summary["already_reminded"] += 1
            continue
        late = sum(1 for e in enquiries if e.follow_up_date < today)
        names = ", ".join(e.student_name for e in enquiries[:4])
        more = f" and {len(enquiries) - 4} more" if len(enquiries) > 4 else ""
        notify(
            recipient_user_id=user_id,
            title=title,
            body=f"{len(enquiries)} to call today or late ({late} overdue): {names}{more}."[:500],
            category=CATEGORY,
            link=LINK,
        )
        summary["staff"] += 1
    return summary
