import hashlib
import hmac
import secrets

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.audit import log_action
from core.dates import school_today

from .models import Applicant, ApplicantEvent, Interview, InterviewPanelist, JobOpening, new_reference

Stage = Applicant.Stage

# Where an applicant may go next. HIRED is absent on purpose: it is reached only through hire_applicant(),
# which creates the staff record, so the pipeline can never say "hired" without a person on the payroll side.
ALLOWED_MOVES = {
    Stage.APPLIED: {Stage.SHORTLISTED, Stage.REJECTED},
    Stage.SHORTLISTED: {Stage.INTERVIEW, Stage.REJECTED, Stage.APPLIED},
    Stage.INTERVIEW: {Stage.OFFERED, Stage.REJECTED, Stage.SHORTLISTED},
    Stage.OFFERED: {Stage.REJECTED, Stage.INTERVIEW},
    Stage.HIRED: set(),
    Stage.REJECTED: {Stage.APPLIED},
}


def _actor_name(user):
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    return user.get_username()


def record_event(applicant, from_stage, to_stage, user, note=""):
    return ApplicantEvent.objects.create(
        applicant=applicant,
        from_stage=from_stage,
        to_stage=to_stage,
        note=note,
        actor_id=getattr(user, "id", None),
        actor_name=_actor_name(user),
    )


def is_accepting_applications(opening):
    if opening.status != JobOpening.Status.OPEN:
        return False
    return not (opening.last_date and opening.last_date < school_today())


@transaction.atomic
def open_opening(opening, request=None):
    if opening.status == JobOpening.Status.OPEN:
        return opening
    if opening.status == JobOpening.Status.CLOSED:
        raise ValidationError("A closed opening cannot be reopened; create a new one.")
    opening.status = JobOpening.Status.OPEN
    opening.save(update_fields=["status", "updated_at"])
    log_action(request, "opening_published", "JobOpening", str(opening.id), {"status": "open"})
    return opening


@transaction.atomic
def close_opening(opening, request=None):
    if opening.status == JobOpening.Status.CLOSED:
        return opening
    opening.status = JobOpening.Status.CLOSED
    opening.closed_at = timezone.now()
    opening.save(update_fields=["status", "closed_at", "updated_at"])
    log_action(request, "opening_closed", "JobOpening", str(opening.id), {"status": "closed"})
    return opening


@transaction.atomic
def move_stage(applicant, to_stage, user, note="", rejection_reason="", request=None):
    # Lock the row so two people moving the same applicant cannot both act on the stage they saw.
    applicant = Applicant.objects.select_for_update().get(pk=applicant.pk)
    from_stage = applicant.stage
    if to_stage == Stage.HIRED:
        raise ValidationError("Use the hire action to hire an applicant.")
    if to_stage not in Stage.values:
        raise ValidationError("Unknown stage.")
    if to_stage not in ALLOWED_MOVES[from_stage]:
        raise ValidationError(f"An applicant cannot move from {from_stage} to {to_stage}.")
    if to_stage == Stage.REJECTED and not (rejection_reason or "").strip():
        raise ValidationError("Give a reason when rejecting an applicant.")

    applicant.stage = to_stage
    applicant.stage_changed_at = timezone.now()
    applicant.rejection_reason = rejection_reason.strip() if to_stage == Stage.REJECTED else ""
    applicant.save(update_fields=["stage", "stage_changed_at", "rejection_reason", "updated_at"])
    record_event(applicant, from_stage, to_stage, user, note or rejection_reason)
    log_action(request, "applicant_stage_changed", "Applicant", str(applicant.id), {"stage": [from_stage, to_stage]})
    return applicant


@transaction.atomic
def hire_applicant(applicant, user, overrides=None, request=None):
    """Turn an offered applicant into a staff or instructor record using the existing onboarding rules."""
    from staff.serializers import InstructorOnboardingSerializer, StaffOnboardingSerializer

    overrides = overrides or {}
    applicant = Applicant.objects.select_for_update().select_related("opening").get(pk=applicant.pk)
    opening = JobOpening.objects.select_for_update().get(pk=applicant.opening_id)

    if applicant.stage != Stage.OFFERED:
        raise ValidationError("Only an applicant who has been offered the job can be hired.")
    hired = Applicant.objects.filter(opening=opening, stage=Stage.HIRED).count()
    if hired >= opening.vacancies:
        raise ValidationError("All vacancies for this opening are already filled.")

    gender = overrides.get("gender") or applicant.gender
    if not gender:
        raise ValidationError("Gender is needed to create the staff record; supply it when hiring.")

    data = {
        "first_name": applicant.first_name,
        "last_name": applicant.last_name,
        "gender": gender,
        "date_of_birth": applicant.date_of_birth,
        "phone": applicant.phone,
        "address": applicant.address,
        "email": applicant.email or None,
        "joining_date": overrides.get("joining_date") or applicant.offered_joining_date,
        "qualification": applicant.qualification,
        "experience_years": applicant.experience_years,
    }
    if opening.position_type == JobOpening.PositionType.INSTRUCTOR:
        data["specialization"] = overrides.get("specialization") or opening.specialization or "General"
        serializer = InstructorOnboardingSerializer(data=data)
    else:
        data["designation"] = overrides.get("designation") or applicant.offered_designation or opening.title
        data["department"] = overrides.get("department") or opening.department
        serializer = StaffOnboardingSerializer(data=data)
    if not serializer.is_valid():
        raise ValidationError(serializer.errors)
    created = serializer.save()
    staff = getattr(created, "staff_member", created)

    applicant.hired_staff = staff
    applicant.stage = Stage.HIRED
    applicant.stage_changed_at = timezone.now()
    applicant.save(update_fields=["hired_staff", "stage", "stage_changed_at", "updated_at"])
    record_event(applicant, Stage.OFFERED, Stage.HIRED, user, f"Hired as {staff.employee_id}")
    log_action(request, "applicant_hired", "Applicant", str(applicant.id), {"staff_member": str(staff.id), "employee_id": staff.employee_id})

    if hired + 1 >= opening.vacancies:
        close_opening(opening, request)
    return applicant


def _hash_token(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_access_token(applicant):
    """Give the candidate a secret for checking their application. Only its hash is stored, so the raw value
    exists in this return value alone (shown once and emailed)."""
    raw = secrets.token_urlsafe(24)
    applicant.access_token_hash = _hash_token(raw)
    applicant.save(update_fields=["access_token_hash", "updated_at"])
    return raw


def decoy_credentials():
    """A reference and secret that look real but match nothing, handed to someone who applied twice so the form
    reveals nothing about who has already applied."""
    return new_reference(), secrets.token_urlsafe(24)


def find_applicant_by_credentials(reference, token):
    applicant = Applicant.objects.filter(reference=(reference or "").strip().upper()).select_related("opening").first()
    if applicant is None or not applicant.access_token_hash:
        # Same work either way, so response time does not say whether the reference exists.
        hmac.compare_digest(_hash_token(token or ""), "0" * 64)
        return None
    return applicant if hmac.compare_digest(_hash_token(token or ""), applicant.access_token_hash) else None


CANDIDATE_STATUS = {
    Applicant.Stage.APPLIED: "Received",
    Applicant.Stage.SHORTLISTED: "Shortlisted",
    Applicant.Stage.INTERVIEW: "Interview stage",
    Applicant.Stage.OFFERED: "Offer in progress",
    Applicant.Stage.HIRED: "Selected",
    Applicant.Stage.REJECTED: "Not selected",
}


def send_application_confirmation(applicant, raw_token, status_url, school_name):
    from notifications.services import queue_email

    queue_email(
        to_email=applicant.email,
        subject=f"Application received - {applicant.opening.title}",
        body=(
            f"Dear {applicant.first_name},\n\n"
            f"{school_name} has received your application for {applicant.opening.title}.\n\n"
            f"To check its progress, open {status_url} and enter:\n"
            f"  Reference: {applicant.reference}\n"
            f"  Access code: {raw_token}\n\n"
            "Keep the access code private; anyone who has it can see this application's status.\n"
        ),
    )


def _school_name():
    from django.db import connection

    return getattr(connection.tenant, "name", "") or "The school"


# What a candidate is told when their application reaches a stage. The reason for a rejection is an internal note
# and is never sent. Moving back to "applied" or on to "hired" (done through hiring) sends nothing here.
STAGE_MESSAGES = {
    Stage.SHORTLISTED: (
        "Your application has been shortlisted",
        "We are pleased to tell you that your application for {title} has been shortlisted. "
        "We will be in touch about the next step.",
    ),
    Stage.INTERVIEW: (
        "Your application is moving to interview",
        "Your application for {title} is moving to the interview stage. You will receive the date and time separately.",
    ),
    Stage.OFFERED: (
        "An update on your application",
        "We would like to take your application for {title} forward to an offer. The school will contact you shortly "
        "with the details.",
    ),
    Stage.REJECTED: (
        "An update on your application",
        "Thank you for your interest in {title} and for the time you gave to the process. After careful "
        "consideration we will not be taking your application forward on this occasion. We wish you well.",
    ),
}


def send_stage_update(applicant, stage):
    """Email the candidate that their application reached ``stage``. Nothing is sent without an email address or
    for a stage that has no message."""
    from notifications.services import queue_email

    message = STAGE_MESSAGES.get(stage)
    if not message or not applicant.email:
        return False
    subject, body = message
    queue_email(
        to_email=applicant.email,
        subject=f"{subject} - {applicant.opening.title}",
        body=(
            f"Dear {applicant.first_name},\n\n"
            + body.format(title=applicant.opening.title)
            + f"\n\nYou can follow your application with reference {applicant.reference} on the careers status page.\n\n"
            f"{_school_name()}\n"
        ),
    )
    return True


def send_interview_invitation(interview):
    """Email the candidate the date, time and place of a scheduled interview."""
    from core.links import portal_link
    from notifications.services import queue_email

    applicant = interview.applicant
    if not applicant.email:
        return False
    where = {
        Interview.Mode.IN_PERSON: "In person",
        Interview.Mode.ONLINE: "Online",
        Interview.Mode.PHONE: "By phone",
    }.get(interview.mode, "")
    when = timezone.localtime(interview.scheduled_at)
    detail = f"  {where}" + (f": {interview.location_or_url}" if interview.location_or_url else "")
    queue_email(
        to_email=applicant.email,
        subject=f"Interview invitation - {applicant.opening.title}",
        body=(
            f"Dear {applicant.first_name},\n\n"
            f"You are invited to an interview ({interview.round_name}) for {applicant.opening.title}.\n\n"
            f"  Date: {when:%A, %d %B %Y}\n"
            f"  Time: {when:%I:%M %p}\n"
            f"{detail}\n\n"
            f"If you cannot attend, please reply to this message as soon as you can.\n"
            f"Your application: {portal_link('/careers/status')}\n\n"
            f"{_school_name()}\n"
        ),
    )
    return True


def save_offer(applicant, *, designation, salary, joining_date, valid_until, notes, user, request=None):
    """Record the terms of the offer. Only while the applicant is at the offered stage; replaces earlier terms and
    clears the 'sent' mark, because a changed offer has to be sent again."""
    from decimal import Decimal, InvalidOperation

    applicant = Applicant.objects.select_for_update().select_related("opening").get(pk=applicant.pk)
    if applicant.stage != Stage.OFFERED:
        raise ValidationError("Offer terms can be set only for an applicant at the offered stage.")
    designation = (designation or "").strip() or applicant.opening.title
    try:
        amount = Decimal(str(salary)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Enter the monthly salary as a number.")
    if not amount.is_finite() or amount <= 0 or amount >= Decimal("10000000"):
        raise ValidationError("The monthly salary must be above zero.")
    today = school_today()
    if joining_date is None:
        raise ValidationError("Give the joining date.")
    if joining_date < today:
        raise ValidationError("The joining date cannot be in the past.")
    if valid_until is not None and (valid_until < today or valid_until > joining_date):
        raise ValidationError("The offer must stay open from today until the joining date at most.")

    applicant.offered_designation = designation[:100]
    applicant.offered_salary = amount
    applicant.offered_joining_date = joining_date
    applicant.offer_valid_until = valid_until
    applicant.offer_notes = (notes or "").strip()
    applicant.offer_sent_at = None
    applicant.save(update_fields=[
        "offered_designation", "offered_salary", "offered_joining_date", "offer_valid_until", "offer_notes",
        "offer_sent_at", "updated_at",
    ])
    record_event(applicant, Stage.OFFERED, Stage.OFFERED, user, f"Offer terms saved: {designation}, {amount} a month")
    log_action(request, "applicant_offer_saved", "Applicant", str(applicant.id), {"salary": str(amount)})
    return applicant


def offer_letter(applicant):
    """The text of the offer letter, built only from the saved terms. Nothing about the applicant's expected salary,
    scores or internal notes goes in it."""
    if applicant.offered_salary is None or applicant.offered_joining_date is None:
        raise ValidationError("Save the offer terms first.")
    school = _school_name()
    lines = [
        f"{school}",
        "",
        f"Date: {school_today():%d %B %Y}",
        f"Reference: {applicant.reference}",
        "",
        f"To: {applicant.full_name}",
    ]
    if applicant.address:
        lines.append(applicant.address)
    lines += [
        "",
        f"Subject: Offer of appointment - {applicant.offered_designation}",
        "",
        f"Dear {applicant.first_name},",
        "",
        f"Following the selection process, we are pleased to offer you the position of {applicant.offered_designation} "
        f"at {school}.",
        "",
        f"  Monthly salary: {applicant.offered_salary:,.2f}",
        f"  Date of joining: {applicant.offered_joining_date:%d %B %Y}",
    ]
    if applicant.offer_valid_until:
        lines.append(f"  This offer is open until: {applicant.offer_valid_until:%d %B %Y}")
    if applicant.offer_notes:
        lines += ["", applicant.offer_notes]
    lines += [
        "",
        "Please sign and return a copy of this letter to confirm that you accept the offer.",
        "",
        "Yours sincerely,",
        "",
        f"Principal, {school}",
    ]
    return {
        "subject": f"Offer of appointment - {applicant.offered_designation}",
        "body": "\n".join(lines),
        "school": school,
        "candidate": applicant.full_name,
        "designation": applicant.offered_designation,
        "salary": str(applicant.offered_salary),
        "joining_date": applicant.offered_joining_date.isoformat(),
        "valid_until": applicant.offer_valid_until.isoformat() if applicant.offer_valid_until else None,
        "sent_at": applicant.offer_sent_at.isoformat() if applicant.offer_sent_at else None,
    }


def send_offer(applicant, user, request=None):
    """Email the offer letter to the candidate and note when it went out."""
    from notifications.services import queue_email

    applicant = Applicant.objects.select_for_update().select_related("opening").get(pk=applicant.pk)
    if applicant.stage != Stage.OFFERED:
        raise ValidationError("Only an offered applicant can be sent an offer.")
    if not applicant.email:
        raise ValidationError("This applicant has no email address. Print the letter instead.")
    letter = offer_letter(applicant)
    queue_email(to_email=applicant.email, subject=letter["subject"], body=letter["body"])
    applicant.offer_sent_at = timezone.now()
    applicant.save(update_fields=["offer_sent_at", "updated_at"])
    record_event(applicant, Stage.OFFERED, Stage.OFFERED, user, "Offer letter emailed")
    log_action(request, "applicant_offer_sent", "Applicant", str(applicant.id), {})
    return applicant


def staff_for_user(user):
    """The staff record behind a login, or None. Filtered through the profile's user link, so a user with
    duplicate profiles is still resolved to the one that has a staff record."""
    from staff.models import StaffMember

    if not user or not getattr(user, "is_authenticated", False):
        return None
    return StaffMember.objects.filter(profile__user_id=user.id).select_related("profile").first()


INTERVIEW_MINUTES = 60  # an interview has no end time of its own; clashes are checked over this long


def panel_conflicts(staff_ids, scheduled_at, exclude_interview=None):
    """Why each of these staff members may not be free at ``scheduled_at``: on approved leave that day, on exam
    duty at that time, teaching a timetabled class then, or on another interview panel at an overlapping time.
    Returns ``[{"staff": id, "name": ..., "reason": ...}]``; empty when everyone looks free. A warning only:
    HR decides whether to go ahead."""
    import datetime

    from academics.models import AcademicYear
    from examinations.models import ExamInvigilation
    from staff.models import LeaveApplication, StaffMember
    from timetable.models import TimetableEntry

    ids = set(staff_ids)
    if not ids:
        return []
    from core.dates import school_zone

    start = scheduled_at.astimezone(school_zone())
    end = start + datetime.timedelta(minutes=INTERVIEW_MINUTES)
    day = start.date()
    names = {
        m.pk: f"{m.profile.first_name} {m.profile.last_name}".strip()
        for m in StaffMember.objects.filter(pk__in=ids).select_related("profile")
    }
    found = {}

    def flag(staff_id, reason):
        found.setdefault(staff_id, []).append(reason)

    for staff_id in LeaveApplication.objects.filter(
        status="approved", start_date__lte=day, end_date__gte=day, staff_id__in=ids
    ).values_list("staff_id", flat=True):
        flag(staff_id, "on approved leave that day")

    start_t, end_t = start.time(), end.time() if end.date() == start.date() else datetime.time(23, 59, 59)
    for duty in ExamInvigilation.objects.filter(
        staff_id__in=ids, sitting__date=day, sitting__start_time__lt=end_t, sitting__end_time__gt=start_t
    ).select_related("sitting__examination"):
        flag(duty.staff_id, f"on exam duty for {duty.sitting.examination.name}")

    current = AcademicYear.objects.filter(is_current=True).values_list("name", flat=True).first()
    if current:
        for entry in TimetableEntry.objects.filter(
            academic_year=current, day_of_week=day.weekday(), instructor__staff_member_id__in=ids,
            period__start_time__lt=end_t, period__end_time__gt=start_t,
        ).select_related("section", "subject"):
            flag(entry.instructor.staff_member_id, f"teaching {entry.subject.name} in {entry.section}")

    earliest = scheduled_at - datetime.timedelta(minutes=INTERVIEW_MINUTES)
    latest = scheduled_at + datetime.timedelta(minutes=INTERVIEW_MINUTES)
    others = InterviewPanelist.objects.filter(
        staff_id__in=ids, interview__status=Interview.Status.SCHEDULED,
        interview__scheduled_at__gt=earliest, interview__scheduled_at__lt=latest,
    ).select_related("interview__applicant")
    if exclude_interview is not None:
        others = others.exclude(interview=exclude_interview)
    for panelist in others:
        flag(panelist.staff_id, f"already on the panel for {panelist.interview.applicant.full_name}'s interview at that time")

    return [
        {"staff": staff_id, "name": names.get(staff_id, ""), "reason": "; ".join(reasons)}
        for staff_id, reasons in found.items()
    ]


@transaction.atomic
def set_panel(interview, staff_ids, request=None):
    """Make the panel exactly these staff members. Someone who has already submitted a score stays, whatever
    the list says, so a recorded judgement is never silently dropped. Returns the staff newly added."""
    from staff.models import StaffMember

    wanted = set(staff_ids)
    found = set(StaffMember.objects.filter(pk__in=wanted, is_active=True).values_list("pk", flat=True))
    if found != wanted:
        raise ValidationError("One or more panelists are not active staff members.")
    existing = {p.staff_id: p for p in interview.panelists.all()}
    for staff_id, panelist in existing.items():
        if staff_id not in wanted and panelist.submitted_at is None:
            panelist.delete()
    added = []
    for staff_id in wanted - set(existing):
        InterviewPanelist.objects.create(interview=interview, staff_id=staff_id)
        added.append(staff_id)
    if added:
        log_action(request, "interview_panel_changed", "Interview", str(interview.id), {"added": [str(a) for a in added]})
    return added


def notify_panelists(interview, staff_ids):
    """Tell newly assigned panelists, where they have a login, that they have an interview to judge."""
    from notifications.services import notify_many
    from staff.models import StaffMember

    user_ids = [
        uid
        for uid in StaffMember.objects.filter(pk__in=staff_ids).values_list("profile__user_id", flat=True)
        if uid
    ]
    if user_ids:
        notify_many(
            recipient_user_ids=user_ids,
            title=f"Interview panel: {interview.applicant.full_name}",
            body=f"{interview.round_name} on {interview.scheduled_at:%d %b %Y, %H:%M}. Open My Interviews to record your score.",
            category="recruitment",
            link="/dashboard/hr/interviews",
        )


def _finish(interview, score, feedback=""):
    interview.status = Interview.Status.COMPLETED
    interview.score = score
    interview.feedback = feedback
    interview.save(update_fields=["status", "score", "feedback", "updated_at"])
    return interview


def _panel_average(interview):
    scores = [p.score for p in interview.panelists.all() if p.submitted_at is not None and p.score is not None]
    return round(sum(scores) / len(scores), 1)


@transaction.atomic
def submit_panelist_feedback(interview, staff, score, feedback="", request=None):
    """A panelist records their own score. The last one to submit completes the interview with the average."""
    interview = Interview.objects.select_for_update().get(pk=interview.pk)
    if interview.status != Interview.Status.SCHEDULED:
        raise ValidationError("This interview is no longer open for feedback.")
    panelist = interview.panelists.filter(staff=staff).first()
    if panelist is None:
        raise ValidationError("You are not on this interview's panel.")
    if panelist.submitted_at is not None:
        raise ValidationError("You have already recorded your feedback for this interview.")
    panelist.score = score
    panelist.feedback = feedback
    panelist.submitted_at = timezone.now()
    panelist.save(update_fields=["score", "feedback", "submitted_at"])
    log_action(request, "interview_feedback_recorded", "Interview", str(interview.id), {"panelist": str(staff.id)})
    if not interview.panelists.filter(submitted_at=None).exists():
        _finish(interview, _panel_average(interview))
    return interview


@transaction.atomic
def complete_interview(interview, score=None, feedback="", request=None):
    """HR closes an interview. With a panel, the result is the average of the scores submitted so far (at least
    one is needed); without one, HR supplies the score."""
    interview = Interview.objects.select_for_update().get(pk=interview.pk)
    if interview.status != Interview.Status.SCHEDULED:
        raise ValidationError("Only a scheduled interview can be completed.")
    if interview.panelists.exists():
        if not interview.panelists.exclude(submitted_at=None).exists():
            raise ValidationError("No panelist has recorded a score yet.")
        _finish(interview, _panel_average(interview))
    else:
        if score is None:
            raise ValidationError("A score is required.")
        _finish(interview, score, feedback)
    log_action(request, "interview_completed", "Interview", str(interview.id), {"score": str(interview.score)})
    return interview
