import datetime
import hashlib
import logging
import secrets
import uuid
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied

from core.audit import log_action
from academics.models import AcademicLevel, Section, AcademicYear
from profiles.models import Profile
from families.models import Parent, StudentParentRelation
from .models import (
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
) -> AdmissionApplication:
    """
    Validates and executes an application status transition, logging history and audit.
    """
    current_status = application.status
    if current_status == new_status:
        return application

    allowed_targets = VALID_APPLICATION_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_targets:
        raise ValidationError(
            f"Cannot transition application from '{current_status}' to '{new_status}'. Allowed targets: {allowed_targets}"
        )

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

