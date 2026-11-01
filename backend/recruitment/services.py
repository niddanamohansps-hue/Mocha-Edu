import hashlib
import hmac
import secrets

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.audit import log_action
from core.dates import school_today

from .models import Applicant, ApplicantEvent, JobOpening, new_reference

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
        "joining_date": overrides.get("joining_date"),
        "qualification": applicant.qualification,
        "experience_years": applicant.experience_years,
    }
    if opening.position_type == JobOpening.PositionType.INSTRUCTOR:
        data["specialization"] = overrides.get("specialization") or opening.specialization or "General"
        serializer = InstructorOnboardingSerializer(data=data)
    else:
        data["designation"] = overrides.get("designation") or opening.title
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
