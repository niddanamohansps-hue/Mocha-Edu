"""Malpractice cases: reporting a student, adding evidence, and the decision.

Reporting changes nothing about the student's marks. Only a decision that cancels marks does, and it does so through
the ordinary marks code (recording the student as "malpractice", which clears their score) so the change appears in
the marks history with the case as its reason. Results cannot be published while a case is undecided, and nothing
can be reported or cancelled once results are published.
"""
from django.db import transaction
from django.utils import timezone

from core.audit import log_action

from .models import ExamMarkChange, ExamSchedule, Examination, MalpracticeCase
from .marks import record_marks

MIN_TEXT = 10
MIN_NOTES = 5
CANCELLING = (MalpracticeCase.Decision.MARKS_CANCELLED, MalpracticeCase.Decision.ALL_PAPERS_CANCELLED)


class MalpracticeError(Exception):
    """The request cannot be done. Nothing was changed."""


def _name(user):
    return user.get_username() if getattr(user, "is_authenticated", False) else ""


def _published(examination_id):
    return Examination.objects.filter(pk=examination_id, is_published=True).exists()


@transaction.atomic
def report_case(schedule, student, *, description, evidence_notes="", user, request=None):
    from .services import get_section_roster_student_ids

    description = (description or "").strip()
    if len(description) < MIN_TEXT:
        raise MalpracticeError("Describe what happened (at least a sentence).")
    if _published(schedule.examination_id):
        raise MalpracticeError("The results are published, so a case can no longer be reported for this examination.")
    if str(student.id) not in get_section_roster_student_ids(schedule.section_id):
        raise MalpracticeError("That student is not in the class sitting this paper.")
    if MalpracticeCase.objects.filter(schedule=schedule, student=student).exists():
        raise MalpracticeError("A case has already been reported for this student in this paper.")

    case = MalpracticeCase.objects.create(
        examination_id=schedule.examination_id, schedule=schedule, student=student, description=description,
        evidence_notes=(evidence_notes or "").strip(), reported_by_user_id=getattr(user, "id", None),
        reported_by_name=_name(user),
    )
    log_action(request, "malpractice_reported", "MalpracticeCase", str(case.id), {"schedule": str(schedule.id)})
    _tell_deciders(case)
    return case


@transaction.atomic
def update_case(case, *, description=None, evidence_notes=None, user, is_decider, request=None):
    """Add to a case while it is undecided: only whoever reported it, or a decider, may."""
    case = MalpracticeCase.objects.select_for_update().get(pk=case.pk)
    if case.status != MalpracticeCase.Status.REPORTED:
        raise MalpracticeError("A decided case can no longer be changed.")
    if not is_decider and case.reported_by_user_id != getattr(user, "id", None):
        raise MalpracticeError("Only the person who reported the case, or a decider, can change it.")
    changed = {}
    if description is not None:
        description = description.strip()
        if len(description) < MIN_TEXT:
            raise MalpracticeError("Describe what happened (at least a sentence).")
        case.description = changed["description"] = description
    if evidence_notes is not None:
        case.evidence_notes = changed["evidence_notes"] = evidence_notes.strip()
    if not changed:
        raise MalpracticeError("Nothing to change.")
    case.save(update_fields=[*changed, "updated_at"])
    log_action(request, "malpractice_updated", "MalpracticeCase", str(case.id), {"fields": sorted(changed)})
    return case


def _cancel_marks(case, schedules, user):
    reason = f"Malpractice case decided ({case.get_decision_display()})"
    for schedule in schedules:
        record_marks(
            schedule,
            [{"student": str(case.student_id), "attendance": "malpractice", "is_absent": True, "marks_obtained": None}],
            entered_by=None, user_id=getattr(user, "id", None), kind=ExamMarkChange.Kind.CORRECTION, reason=reason,
        )


@transaction.atomic
def decide_case(case, *, decision, notes, user, request=None):
    case = MalpracticeCase.objects.select_for_update().select_related("schedule").get(pk=case.pk)
    if case.status != MalpracticeCase.Status.REPORTED:
        raise MalpracticeError("This case has already been decided.")
    if decision not in MalpracticeCase.Decision.values:
        raise MalpracticeError("Choose a decision.")
    notes = (notes or "").strip()
    if len(notes) < MIN_NOTES:
        raise MalpracticeError("Give the reasons for the decision.")
    if decision in CANCELLING and _published(case.examination_id):
        raise MalpracticeError("The results are published, so marks can no longer be cancelled.")

    if decision == MalpracticeCase.Decision.MARKS_CANCELLED:
        _cancel_marks(case, [case.schedule], user)
    elif decision == MalpracticeCase.Decision.ALL_PAPERS_CANCELLED:
        papers = ExamSchedule.objects.filter(examination_id=case.examination_id, section_id=case.schedule.section_id)
        _cancel_marks(case, list(papers), user)

    case.status = MalpracticeCase.Status.DECIDED
    case.decision = decision
    case.decision_notes = notes
    case.decided_by_user_id = getattr(user, "id", None)
    case.decided_by_name = _name(user)
    case.decided_at = timezone.now()
    case.save()
    log_action(request, "malpractice_decided", "MalpracticeCase", str(case.id), {"decision": decision})
    return case


def undecided_count(examination):
    return MalpracticeCase.objects.filter(examination=examination, status=MalpracticeCase.Status.REPORTED).count()


def _tell_deciders(case):
    """An in-app notice to everyone who may decide cases, once the report has been saved."""
    from django.db.models import Q

    from roles.models import UserRole

    ids = set(
        UserRole.objects.filter(Q(role__slug="owner") | Q(role__permissions__codename="decide_exam_malpractice"))
        .values_list("user_id", flat=True)
    ) - {case.reported_by_user_id}
    if not ids:
        return

    def send():
        from notifications.services import notify_many

        try:
            notify_many(
                recipient_user_ids=list(ids), title=f"Malpractice reported: {case.examination.name}",
                body="A case needs a decision before the results can be published.", category="examinations",
                link="/dashboard/examinations/malpractice",
            )
        except Exception:  # pragma: no cover - best effort
            pass

    transaction.on_commit(send)


def case_data(case):
    student = case.student
    return {
        "id": case.id,
        "examination": case.examination_id,
        "examination_name": case.examination.name,
        "schedule": case.schedule_id,
        "subject": case.schedule.subject.name,
        "class": f"{case.schedule.section.level.name} {case.schedule.section.name}",
        "student_id": case.student_id,
        "student": f"{student.profile.first_name} {student.profile.last_name}".strip(),
        "enrollment_id": student.enrollment_id,
        "description": case.description,
        "evidence_notes": case.evidence_notes,
        "reported_by": case.reported_by_name,
        "reported_by_user_id": case.reported_by_user_id,
        "reported_at": case.created_at,
        "status": case.status,
        "decision": case.decision,
        "decision_label": case.get_decision_display() if case.decision else "",
        "decision_notes": case.decision_notes,
        "decided_by": case.decided_by_name,
        "decided_at": case.decided_at,
    }
