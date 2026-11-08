import datetime
import hashlib
import logging
import secrets
import uuid
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied

from core.audit import log_action
from academics.models import AcademicLevel, Section, AcademicYear
from profiles.models import Profile
from families.models import Parent, StudentParentRelation
from .models import (
    ENQUIRY_SOURCE_CHOICES,
    DOCUMENT_TYPE_CHOICES,
    Student,
    StudentLevel,
    AcademicHistory,
    AdmissionEnquiry,
    AdmissionApplication,
    AdmissionDocument,
    AdmissionInterview,
    AdmissionActivityLog,
)
from .services import get_staff_member_for_user

logger = logging.getLogger(__name__)

# Valid state machine transitions
VALID_APPLICATION_TRANSITIONS = {
    "draft": ["submitted", "withdrawn"],
    "submitted": ["under_review", "documents_pending", "withdrawn", "rejected"],
    "under_review": [
        "documents_pending",
        "documents_verified",
        "assessment_pending",
        "approved",
        "waitlisted",
        "rejected",
        "withdrawn",
    ],
    "documents_pending": [
        "under_review",
        "documents_verified",
        "withdrawn",
        "rejected",
    ],
    "documents_verified": [
        "under_review",
        "assessment_pending",
        "approved",
        "waitlisted",
        "rejected",
        "withdrawn",
    ],
    "assessment_pending": [
        "under_review",
        "approved",
        "waitlisted",
        "rejected",
        "withdrawn",
    ],
    "approved": ["offer_accepted", "enrolled", "withdrawn", "rejected"],
    "waitlisted": ["under_review", "approved", "rejected", "withdrawn"],
    "offer_accepted": ["enrolled", "withdrawn", "rejected"],
    "enrolled": [],  # Terminal state - cannot transition out of enrolled!
    "rejected": ["under_review"],  # Appeal / re-evaluation allowed
    "withdrawn": ["draft", "under_review"],  # Re-opening allowed
}


def generate_enquiry_number():
    """Generates an sequential/unique enquiry number e.g. ENQ-2026-0001."""
    year = timezone.now().year
    prefix = f"ENQ-{year}-"
    # Find max existing in current year
    last = (
        AdmissionEnquiry.objects.filter(enquiry_number__startswith=prefix)
        .order_by("-enquiry_number")
        .first()
    )
    if last:
        try:
            seq = int(last.enquiry_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    candidate = f"{prefix}{seq:04d}"
    # Safety check for collision
    if AdmissionEnquiry.objects.filter(enquiry_number=candidate).exists():
        candidate = f"{prefix}{uuid.uuid4().hex[:6].upper()}"
    return candidate


def generate_application_number():
    """Generates a sequential/unique application number e.g. APP-2026-0001."""
    year = timezone.now().year
    prefix = f"APP-{year}-"
    last = (
        AdmissionApplication.objects.filter(application_number__startswith=prefix)
        .order_by("-application_number")
        .first()
    )
    if last:
        try:
            seq = int(last.application_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    candidate = f"{prefix}{seq:04d}"
    if AdmissionApplication.objects.filter(application_number=candidate).exists():
        candidate = f"{prefix}{uuid.uuid4().hex[:6].upper()}"
    return candidate


def transition_application_status(
    application: AdmissionApplication,
    new_status: str,
    user=None,
    notes: str = "",
    reason: str = "",
    request=None,
    confirm_over_limit: bool = False,
) -> AdmissionApplication:
    """
    Validates and executes an application status transition, logging history and audit.
    Approving into a class that is already full is refused unless ``confirm_over_limit`` is set.
    """
    current_status = application.status
    if current_status == new_status:
        return application

    allowed_targets = VALID_APPLICATION_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_targets:
        raise ValidationError(
            f"Cannot transition application from '{current_status}' to '{new_status}'. Allowed targets: {allowed_targets}"
        )

    if new_status == "approved":
        check_seat_available(application, confirm_over_limit)

    staff_member = get_staff_member_for_user(user) if user and user.is_authenticated else None

    # Status-specific side effects & validations
    now = timezone.now()
    if new_status == "submitted" and not application.submission_date:
        application.submission_date = now

    if new_status in ["approved", "rejected", "waitlisted"]:
        application.decision_date = now
        application.decision_by = staff_member
        if reason:
            application.decision_reason = reason
        elif new_status == "rejected" and not application.decision_reason:
            raise ValidationError("A reason is required when rejecting an application.")

    old_status = application.status
    application.status = new_status
    if notes:
        application.notes = f"{application.notes}\n[{now.strftime('%Y-%m-%d %H:%M')}] {notes}".strip()
    application.save()

    # Log internal activity
    AdmissionActivityLog.objects.create(
        application=application,
        action="status_changed",
        from_status=old_status,
        to_status=new_status,
        performed_by=staff_member,
        notes=notes or reason,
    )

    if request:
        log_action(
            request,
            action="CHANGE",
            model_name="AdmissionApplication",
            object_id=application.id,
            changes={"status": {"old": old_status, "new": new_status}, "reason": reason},
        )

    # Tell the family. A failure to queue the email must never undo the status change itself.
    try:
        notify_family_of_status(application, new_status)
    except Exception:
        logger.exception("Could not queue the admission update email for %s", application.application_number)

    return application


@transaction.atomic
def enroll_application_as_student(
    application_id,
    user=None,
    section_id=None,
    request=None,
) -> Student:
    """
    Idempotent transactional conversion of an approved/offer_accepted application
    into an active Student record.
    """
    # Concurrency guard: select for update
    application = (
        AdmissionApplication.objects.select_for_update()
        .filter(id=application_id)
        .first()
    )
    if not application:
        raise ValidationError("Admission application not found.")

    if application.status == "enrolled" or application.student_id is not None:
        raise ValidationError(
            f"Application {application.application_number} is already enrolled as student {application.student.enrollment_id}."
        )

    if application.status not in ["approved", "offer_accepted"]:
        raise ValidationError(
            f"Cannot enroll application with status '{application.status}'. Application must be 'approved' or 'offer_accepted'."
        )

    staff_member = get_staff_member_for_user(user) if user and user.is_authenticated else None

    # Resolve Section
    section = None
    if section_id:
        section = Section.objects.filter(id=section_id, level=application.level).first()
        if not section:
            raise ValidationError("Specified section not found or does not belong to the application's grade level.")
    elif application.section:
        section = application.section

    from billing.enforcement import check_student_capacity

    check_student_capacity()

    # 1. Create Student Profile
    student_profile = Profile.objects.create(
        user_id=None,
        first_name=application.first_name,
        middle_name=application.middle_name,
        last_name=application.last_name,
        gender=application.gender,
        date_of_birth=application.date_of_birth,
        phone=application.phone,
        address=application.address,
    )

    # 2. Create Student Record
    enrollment_id = f"STD-{uuid.uuid4().hex[:8].upper()}"
    student = Student.objects.create(
        profile=student_profile,
        enrollment_id=enrollment_id,
        admission_date=timezone.now().date(),
        status="active",
    )

    # 3. Create Academic Placement (StudentLevel)
    StudentLevel.objects.create(
        student=student,
        level=application.level,
        section=section,
        academic_year=application.academic_year,
        academic_year_ref=application.academic_year_ref,
        is_current=True,
    )

    # 4. Create Academic History if previous school provided
    if application.previous_school:
        AcademicHistory.objects.create(
            student=student,
            previous_school=application.previous_school,
            last_grade_passed=application.last_grade_passed,
        )

    # 5. Create Guardian Profile & Parent Record
    guardian_profile = Profile.objects.create(
        user_id=None,
        first_name=application.guardian_first_name,
        last_name=application.guardian_last_name,
        phone=application.guardian_phone,
        address=application.guardian_address or application.address,
    )
    primary_parent = Parent.objects.create(
        profile=guardian_profile,
        occupation=application.guardian_occupation,
    )
    StudentParentRelation.objects.create(
        student=student,
        parent=primary_parent,
        relation_type=application.guardian_relationship or "guardian",
        is_primary_contact=True,
    )

    # Secondary Guardian if provided
    if application.secondary_guardian_name:
        parts = application.secondary_guardian_name.strip().split(" ", 1)
        sec_first = parts[0]
        sec_last = parts[1] if len(parts) > 1 else ""
        sec_profile = Profile.objects.create(
            user_id=None,
            first_name=sec_first,
            last_name=sec_last,
            phone=application.secondary_guardian_phone,
            address=application.address,
        )
        sec_parent = Parent.objects.create(profile=sec_profile)
        StudentParentRelation.objects.create(
            student=student,
            parent=sec_parent,
            relation_type=application.secondary_guardian_relationship or "other",
            is_primary_contact=False,
        )

    # 6. Update Application status to ENROLLED
    old_status = application.status
    application.student = student
    application.status = "enrolled"
    application.enrolled_at = timezone.now()
    application.enrolled_by = staff_member
    if section:
        application.section = section
    application.save()

    # 7. Record Activity and Audit Log
    AdmissionActivityLog.objects.create(
        application=application,
        action="enrolled",
        from_status=old_status,
        to_status="enrolled",
        performed_by=staff_member,
        notes=f"Converted to active student {enrollment_id}",
    )

    if request:
        log_action(
            request,
            action="CREATE",
            model_name="Student",
            object_id=student.id,
            changes={"enrollment_id": enrollment_id, "application_id": str(application.id)},
        )

    return student


@transaction.atomic
def convert_enquiry_to_application(
    enquiry_id,
    user=None,
    request=None,
) -> AdmissionApplication:
    """
    Converts an enquiry into an active draft AdmissionApplication.
    """
    enquiry = AdmissionEnquiry.objects.select_for_update().filter(id=enquiry_id).first()
    if not enquiry:
        raise ValidationError("Enquiry not found.")

    if enquiry.status == "converted":
        existing_app = AdmissionApplication.objects.filter(enquiry=enquiry).first()
        if existing_app:
            return existing_app

    # Split student name
    name_parts = enquiry.student_name.strip().split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else "."

    # Split guardian name
    g_parts = enquiry.guardian_name.strip().split(" ", 1)
    g_first = g_parts[0]
    g_last = g_parts[1] if len(g_parts) > 1 else "."

    # Level
    level = enquiry.preferred_level
    if not level:
        # Pick the lowest order level
        level = AcademicLevel.objects.order_by("order").first()
        if not level:
            raise ValidationError("No Academic Level configured in system.")

    staff_member = get_staff_member_for_user(user) if user and user.is_authenticated else None

    app_number = generate_application_number()
    application = AdmissionApplication.objects.create(
        application_number=app_number,
        enquiry=enquiry,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=enquiry.date_of_birth or timezone.now().date(),
        gender=enquiry.gender or "other",
        phone=enquiry.guardian_phone,
        address=enquiry.address,
        previous_school=enquiry.previous_school,
        guardian_first_name=g_first,
        guardian_last_name=g_last,
        guardian_relationship=enquiry.guardian_relationship,
        guardian_phone=enquiry.guardian_phone,
        guardian_email=enquiry.guardian_email,
        guardian_address=enquiry.address,
        academic_year=enquiry.academic_year,
        academic_year_ref=enquiry.academic_year_ref,
        level=level,
        status="draft",
        assigned_reviewer=enquiry.assigned_to,
        notes=f"Converted from enquiry {enquiry.enquiry_number}. {enquiry.notes}".strip(),
    )

    enquiry.status = "converted"
    enquiry.save()

    AdmissionActivityLog.objects.create(
        application=application,
        action="created",
        from_status="",
        to_status="draft",
        performed_by=staff_member,
        notes=f"Created from enquiry {enquiry.enquiry_number}",
    )

    if request:
        log_action(
            request,
            action="CREATE",
            model_name="AdmissionApplication",
            object_id=application.id,
            changes={"application_number": app_number, "enquiry_id": str(enquiry.id)},
        )

    return application


def get_admissions_dashboard_stats():
    """
    Computes summary metrics for admissions management dashboard.
    """
    total_enquiries = AdmissionEnquiry.objects.count()
    enquiries_new = AdmissionEnquiry.objects.filter(status="new").count()
    enquiries_contacted = AdmissionEnquiry.objects.filter(status="contacted").count()
    enquiries_converted = AdmissionEnquiry.objects.filter(status="converted").count()

    total_applications = AdmissionApplication.objects.count()
    apps_submitted = AdmissionApplication.objects.filter(status="submitted").count()
    apps_under_review = AdmissionApplication.objects.filter(status="under_review").count()
    apps_docs_pending = AdmissionApplication.objects.filter(status="documents_pending").count()
    apps_assessment = AdmissionApplication.objects.filter(status="assessment_pending").count()
    apps_approved = AdmissionApplication.objects.filter(status__in=["approved", "offer_accepted"]).count()
    apps_enrolled = AdmissionApplication.objects.filter(status="enrolled").count()
    apps_rejected = AdmissionApplication.objects.filter(status="rejected").count()

    pending_docs = AdmissionDocument.objects.filter(verification_status="pending").count()
    scheduled_interviews = AdmissionInterview.objects.filter(status="scheduled").count()

    conversion_rate = 0.0
    if total_applications > 0:
        conversion_rate = round((apps_enrolled / total_applications) * 100, 1)

    return {
        "total_enquiries": total_enquiries,
        "enquiries_new": enquiries_new,
        "enquiries_contacted": enquiries_contacted,
        "enquiries_converted": enquiries_converted,
        "total_applications": total_applications,
        "applications_submitted": apps_submitted,
        "applications_under_review": apps_under_review,
        "applications_documents_pending": apps_docs_pending,
        "applications_assessment_pending": apps_assessment,
        "applications_approved": apps_approved,
        "applications_enrolled": apps_enrolled,
        "applications_rejected": apps_rejected,
        "pending_document_verifications": pending_docs,
        "scheduled_interviews": scheduled_interviews,
        "conversion_rate": conversion_rate,
    }


def rotate_application_access_token(application: AdmissionApplication, user=None, reason: str = "") -> str:
    """
    Atomically generates a fresh capability token, replacing and invalidating the previous token.
    Returns the unhashed raw token string for one-time delivery to the applicant.
    """
    with transaction.atomic():
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        application.access_token_hash = token_hash
        application.access_token_expires_at = timezone.now() + datetime.timedelta(days=90)
        application.save(update_fields=["access_token_hash", "access_token_expires_at", "updated_at"])

        staff_member = get_staff_member_for_user(user) if user and getattr(user, "is_authenticated", False) else None
        note = f"Access token rotated. {reason}".strip()
        AdmissionActivityLog.objects.create(
            application=application,
            action="token_rotated",
            performed_by=staff_member,
            notes=note,
        )

        if user and getattr(user, "is_authenticated", False):
            try:
                from core.models import AuditLog
                AuditLog.objects.create(
                    actor_id=user.id,
                    actor_username=user.username,
                    action="UPDATE",
                    model_name="AdmissionApplication",
                    object_id=str(application.id),
                    changes={"detail": f"Rotated access token for application {application.application_number}"},
                )
            except Exception:
                pass

    return raw_token


def revoke_application_access_token(application: AdmissionApplication, user=None, reason: str = ""):
    """
    Revokes the application's capability token immediately, preventing further self-service access.
    """
    with transaction.atomic():
        application.access_token_hash = ""
        application.access_token_expires_at = None
        application.save(update_fields=["access_token_hash", "access_token_expires_at", "updated_at"])

        staff_member = get_staff_member_for_user(user) if user and getattr(user, "is_authenticated", False) else None
        note = f"Access token revoked. {reason}".strip()
        AdmissionActivityLog.objects.create(
            application=application,
            action="token_revoked",
            performed_by=staff_member,
            notes=note,
        )

        if user and getattr(user, "is_authenticated", False):
            try:
                from core.models import AuditLog
                AuditLog.objects.create(
                    actor_id=user.id,
                    actor_username=user.username,
                    action="UPDATE",
                    model_name="AdmissionApplication",
                    object_id=str(application.id),
                    changes={"detail": f"Revoked access token for application {application.application_number}"},
                )
            except Exception:
                pass



# ---- telling the family -----------------------------------------------------------------------------------

# Statuses the family is emailed about as soon as they happen. A rejection is deliberately absent: it is sent only
# when a person presses the button (send_decision_notice), so staff can speak to the family first if they want to.
FAMILY_UPDATES = {
    "documents_pending": (
        "Documents needed for the admission application",
        "We need some documents before we can take {student}'s application further. Please open the link below to "
        "see what is missing and upload it.",
    ),
    "approved": (
        "Good news about the admission application",
        "We are pleased to tell you that the admission of {student} has been approved. The school will contact you "
        "shortly about the next steps.",
    ),
    "waitlisted": (
        "Update on the admission application",
        "Thank you for applying. {student} has been placed on our waiting list. We will contact you if a seat becomes "
        "available.",
    ),
}
REJECTION_TEXT = (
    "Update on the admission application",
    "Thank you for your interest in our school and for the time you gave to the application for {student}. After "
    "careful consideration we are unable to offer a place on this occasion. We wish {student} every success.",
)


def _family_message(application, subject, body):
    from notifications.services import queue_email

    from core.links import portal_link
    from django.db import connection

    to = (application.guardian_email or "").strip()
    if not to:
        return False
    school = getattr(connection.tenant, "name", "") or "The school"
    student = f"{application.first_name} {application.last_name}".strip()
    queue_email(
        to_email=to,
        subject=f"{subject} - {application.application_number}",
        body=(
            f"Dear {application.guardian_first_name} {application.guardian_last_name},\n\n"
            + body.format(student=student)
            + f"\n\nApplication number: {application.application_number}\n"
            f"Follow it here: {portal_link('/admissions/status')}\n\n"
            f"{school}\n"
        ),
    )
    return True


def notify_family_of_status(application, new_status):
    """Email the guardian about a status that has a message of its own. Returns whether one was queued. Never
    includes the internal decision reason, scores or notes."""
    message = FAMILY_UPDATES.get(new_status)
    if message is None:
        return False
    sent = _family_message(application, *message)
    if sent and new_status in ("approved", "waitlisted"):
        application.decision_notice_sent_at = timezone.now()
        application.save(update_fields=["decision_notice_sent_at", "updated_at"])
    return sent


def send_decision_notice(application, user=None, request=None):
    """Email the guardian the outcome of a rejected application, on the say-so of a person. Once only."""
    if application.status != "rejected":
        raise ValidationError("Only a rejected application needs this notice; others are sent automatically.")
    if application.decision_notice_sent_at:
        raise ValidationError("The family has already been told.")
    if not (application.guardian_email or "").strip():
        raise ValidationError("This family has no email address. Tell them by phone.")
    _family_message(application, *REJECTION_TEXT)
    application.decision_notice_sent_at = timezone.now()
    application.save(update_fields=["decision_notice_sent_at", "updated_at"])
    AdmissionActivityLog.objects.create(
        application=application,
        action="decision_notice_sent",
        from_status="rejected",
        to_status="rejected",
        performed_by=get_staff_member_for_user(user) if user and user.is_authenticated else None,
        notes="Rejection email sent to the family",
    )
    if request:
        log_action(request, action="CHANGE", model_name="AdmissionApplication", object_id=application.id,
                   changes={"decision_notice": "sent"})
    return application


# ---- chasing missing documents ----------------------------------------------------------------------------

REMINDER_GAP_DAYS = 7  # the first nudge comes this long after the family was asked, then once a week


def documents_family_must_send(application):
    """What the family still has to do about documents, as short lines for an email. Empty when the ball is with the
    school (everything sent is simply waiting to be checked), in which case nobody should be nagged.

    The school has no fixed list of required documents, so "missing" means only what we can see: nothing uploaded at
    all, a document that was rejected and has not been replaced by one of the same type, or a file that failed the
    virus scan."""
    docs = list(application.documents.all())
    labels = dict(DOCUMENT_TYPE_CHOICES)
    required = document_checklist(application)
    if required:
        # The school has said exactly what it needs: ask only for what is still missing or has to be re-sent.
        lines = []
        for item in required:
            if item["status"] == "missing":
                lines.append(f"{item['label']}: not received yet.")
            elif item["status"] == "rejected":
                lines.append(f"{item['label']}: please upload a clearer or corrected copy.")
        return lines
    if not docs:
        return ["No documents have been received yet."]
    lines = []
    for doc in docs:
        kind = labels.get(doc.document_type, doc.document_type)
        if doc.scan_status in ("infected", "error"):
            lines.append(f"{kind}: the file could not be accepted. Please upload it again.")
            continue
        if doc.verification_status != "rejected":
            continue
        replaced = any(
            other.pk != doc.pk
            and other.document_type == doc.document_type
            and other.verification_status != "rejected"
            and other.scan_status not in ("infected", "error")
            and other.uploaded_at > doc.uploaded_at
            for other in docs
        )
        if not replaced:
            lines.append(f"{kind}: please upload a clearer or corrected copy.")
    return list(dict.fromkeys(lines))  # one line per problem, in order


def _entered_documents_pending(application):
    """When the application last became 'documents pending', from its history; the last change otherwise."""
    log = (
        AdmissionActivityLog.objects.filter(application=application, to_status="documents_pending")
        .order_by("-created_at")
        .first()
    )
    return log.created_at if log else application.updated_at


def remind_missing_documents(now=None):
    """The daily job body for one school: email the guardian of each application still at 'documents pending' that
    needs something from them, at most once a week. Returns counts."""
    now = now or timezone.now()
    cutoff = now - datetime.timedelta(days=REMINDER_GAP_DAYS)
    summary = {"reminded": 0, "waiting_on_school": 0, "too_soon": 0, "no_email": 0}
    for application in AdmissionApplication.objects.filter(status="documents_pending").prefetch_related("documents"):
        last = max(filter(None, [application.documents_reminded_at, _entered_documents_pending(application)]))
        if last > cutoff:
            summary["too_soon"] += 1
            continue
        lines = documents_family_must_send(application)
        if not lines:
            summary["waiting_on_school"] += 1
            continue
        if not (application.guardian_email or "").strip():
            summary["no_email"] += 1
            continue
        body = (
            "This is a reminder that we are still waiting for the following before we can take "
            "{student}'s application further:\n\n" + "\n".join(f"  - {line}" for line in lines)
            + "\n\nPlease open the link below to upload them."
        )
        _family_message(application, "Reminder: documents needed for the admission application", body)
        application.documents_reminded_at = now
        application.save(update_fields=["documents_reminded_at", "updated_at"])
        summary["reminded"] += 1
    return summary


# ---- seats and reports ------------------------------------------------------------------------------------

SEAT_HOLDING = ("approved", "offer_accepted", "enrolled")


def seats_taken(academic_year, level_id, exclude_application_id=None):
    """Applications that already hold a seat in this class and year."""
    qs = AdmissionApplication.objects.filter(academic_year=academic_year, level_id=level_id, status__in=SEAT_HOLDING)
    if exclude_application_id is not None:
        qs = qs.exclude(pk=exclude_application_id)
    return qs.count()


def check_seat_available(application, confirm_over_limit=False):
    """Refuse to approve past the class limit unless the person has said they mean to. A class with no limit set is
    never refused. The error carries the numbers so the screen can ask 'approve anyway?'."""
    from .models import AdmissionSeatLimit

    limit = AdmissionSeatLimit.objects.filter(academic_year=application.academic_year, level_id=application.level_id).first()
    if limit is None or confirm_over_limit:
        return
    taken = seats_taken(application.academic_year, application.level_id, exclude_application_id=application.pk)
    if taken >= limit.seats:
        raise ValidationError({
            "seat_limit": [
                f"{application.level.name} already has {taken} of {limit.seats} seats taken for {application.academic_year}. "
                "Confirm to approve past the limit."
            ]
        })


def seats_overview(academic_year):
    """One row for every class of the school: its limit (if any), seats taken, waitlist and open applications."""
    from .models import AdmissionSeatLimit

    limits = {l.level_id: l.seats for l in AdmissionSeatLimit.objects.filter(academic_year=academic_year)}
    apps = AdmissionApplication.objects.filter(academic_year=academic_year)
    rows = []
    for level in AcademicLevel.objects.order_by("order", "name"):
        mine = apps.filter(level=level)
        taken = mine.filter(status__in=SEAT_HOLDING).count()
        seats = limits.get(level.id)
        rows.append({
            "level": level.id,
            "level_name": level.name,
            "seats": seats,
            "taken": taken,
            "free": None if seats is None else max(seats - taken, 0),
            "over_by": 0 if seats is None else max(taken - seats, 0),
            "waitlisted": mine.filter(status="waitlisted").count(),
            "in_progress": mine.exclude(status__in=SEAT_HOLDING + ("waitlisted", "rejected", "withdrawn", "draft")).count(),
        })
    return rows


def set_seat_limit(academic_year, level_id, seats, request=None):
    from .models import AdmissionSeatLimit

    academic_year = (academic_year or "").strip()
    if not academic_year:
        raise ValidationError({"academic_year": ["Choose the academic year."]})
    try:
        seats = int(seats)
    except (TypeError, ValueError):
        raise ValidationError({"seats": ["Enter the number of seats."]})
    if not 0 <= seats <= 5000:
        raise ValidationError({"seats": ["Seats must be between 0 and 5000."]})
    level = AcademicLevel.objects.filter(pk=level_id).first()
    if level is None:
        raise ValidationError({"level": ["Choose a class."]})
    limit, _ = AdmissionSeatLimit.objects.update_or_create(academic_year=academic_year, level=level, defaults={"seats": seats})
    if request:
        log_action(request, action="CHANGE", model_name="AdmissionSeatLimit", object_id=limit.id,
                   changes={"academic_year": academic_year, "level": level.name, "seats": seats})
    return limit


def admissions_report(academic_year):
    """Where enquiries come from and how far they get, by source and by class, and how long it takes from the first
    enquiry to enrolment (only for applications that began as an enquiry)."""
    from django.db.models import Avg, Count, ExpressionWrapper, F, DurationField, Q

    enquiries = AdmissionEnquiry.objects.filter(academic_year=academic_year)
    apps = AdmissionApplication.objects.filter(academic_year=academic_year)
    labels = dict(ENQUIRY_SOURCE_CHOICES)

    by_source = []
    for row in enquiries.values("source").annotate(
        total=Count("id"), converted=Count("id", filter=Q(status="converted")), lost=Count("id", filter=Q(status="closed"))
    ).order_by("-total"):
        enrolled = apps.filter(enquiry__source=row["source"], status="enrolled").count()
        by_source.append({
            "source": row["source"], "label": labels.get(row["source"], row["source"]), "enquiries": row["total"],
            "applied": row["converted"], "lost": row["lost"], "enrolled": enrolled,
        })

    by_level = []
    for level in AcademicLevel.objects.order_by("order", "name"):
        enq = enquiries.filter(preferred_level=level).count()
        mine = apps.filter(level=level)
        total = mine.count()
        if enq or total:
            by_level.append({
                "level": level.id, "level_name": level.name, "enquiries": enq, "applications": total,
                "approved": mine.filter(status__in=("approved", "offer_accepted")).count(),
                "enrolled": mine.filter(status="enrolled").count(),
            })

    spans = apps.filter(status="enrolled", enrolled_at__isnull=False, enquiry__isnull=False).annotate(
        span=ExpressionWrapper(F("enrolled_at") - F("enquiry__created_at"), output_field=DurationField())
    ).aggregate(avg=Avg("span"), n=Count("id"))
    avg_days = round(spans["avg"].total_seconds() / 86400, 1) if spans["avg"] is not None else None

    return {
        "academic_year": academic_year,
        "totals": {
            "enquiries": enquiries.count(),
            "applications": apps.count(),
            "enrolled": apps.filter(status="enrolled").count(),
        },
        "by_source": by_source,
        "by_level": by_level,
        "average_days_to_enrol": avg_days,
        "enrolled_with_enquiry": spans["n"],
    }


# ---- required documents per class -------------------------------------------------------------------------


def required_types_for(application):
    """The document types this applicant must hand in: those asked of every class plus those asked of their class."""
    from .models import AdmissionRequiredDocument

    wanted = AdmissionRequiredDocument.objects.filter(Q(level__isnull=True) | Q(level_id=application.level_id))
    return [t for t, _ in DOCUMENT_TYPE_CHOICES if t in set(wanted.values_list("document_type", flat=True))]


def document_checklist(application):
    """One line per required document with where it stands: verified, received (waiting to be checked), rejected (a
    new copy is needed) or missing. Empty when the school has not set a list for this class."""
    labels = dict(DOCUMENT_TYPE_CHOICES)
    docs = list(application.documents.all())
    out = []
    for kind in required_types_for(application):
        mine = [d for d in docs if d.document_type == kind and d.scan_status not in ("infected", "error")]
        if any(d.verification_status == "verified" for d in mine):
            state = "verified"
        elif any(d.verification_status == "pending" for d in mine):
            state = "received"
        elif any(d.verification_status == "rejected" for d in mine):
            state = "rejected"
        else:
            state = "missing"
        out.append({"document_type": kind, "label": labels.get(kind, kind), "status": state})
    return out


def required_documents_overview():
    """Everything the school has set: the types it can ask for, what is asked of every class, and per class."""
    from .models import AdmissionRequiredDocument

    rows = list(AdmissionRequiredDocument.objects.select_related("level"))
    return {
        "types": [{"value": value, "label": label} for value, label in DOCUMENT_TYPE_CHOICES],
        "all_classes": sorted(r.document_type for r in rows if r.level_id is None),
        "by_level": [
            {
                "level": level.id,
                "level_name": level.name,
                "document_types": sorted(r.document_type for r in rows if r.level_id == level.id),
            }
            for level in AcademicLevel.objects.order_by("order", "name")
        ],
    }


def set_required_documents(level_id, document_types, request=None):
    """Replace the documents asked of one class (or of every class when ``level_id`` is empty)."""
    from .models import AdmissionRequiredDocument

    valid = {value for value, _ in DOCUMENT_TYPE_CHOICES}
    if not isinstance(document_types, (list, tuple)) or any(t not in valid for t in document_types):
        raise ValidationError({"document_types": ["Choose from the known document types."]})
    level = None
    if level_id:
        level = AcademicLevel.objects.filter(pk=level_id).first()
        if level is None:
            raise ValidationError({"level": ["Choose a class."]})
    wanted = set(document_types)
    scope = AdmissionRequiredDocument.objects.filter(level=level) if level else AdmissionRequiredDocument.objects.filter(level__isnull=True)
    scope.exclude(document_type__in=wanted).delete()
    have = set(scope.values_list("document_type", flat=True))
    for kind in wanted - have:
        AdmissionRequiredDocument.objects.create(level=level, document_type=kind)
    if request:
        log_action(request, action="CHANGE", model_name="AdmissionRequiredDocument", object_id=str(level.id) if level else "all",
                   changes={"level": level.name if level else "all classes", "document_types": sorted(wanted)})
