import datetime
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac


from .cbse import check_student_fee_dues, date_to_words
from .models import Certificate, CertificateSequence

logger = logging.getLogger(__name__)

NUMBER_PREFIX = {
    Certificate.Type.TRANSFER: "TC",
    Certificate.Type.BONAFIDE: "BON",
    Certificate.Type.CHARACTER: "CHR",
    Certificate.Type.EXPERIENCE: "EXP",
}

# Types that need the approver to be recorded (and the stronger permission).
APPROVAL_TYPES = (Certificate.Type.TRANSFER, Certificate.Type.EXPERIENCE)

# A TC is only meaningful for a student who has actually left. There is no
# withdrawal/approval workflow in the repository, so Student.status is the only
# signal; see CERTIFICATES_IMPLEMENTATION_REPORT.md.
TRANSFER_ELIGIBLE_STATUSES = ("transferred", "withdrawn")
BONAFIDE_ELIGIBLE_STATUSES = ("active",)
CHARACTER_ELIGIBLE_STATUSES = ("active", "graduated", "transferred", "withdrawn")


class CertificateError(ValidationError):
    """A business-rule failure (rendered as HTTP 400)."""


def _full_name(profile):
    return " ".join(p for p in (profile.first_name, profile.middle_name, profile.last_name) if p).strip()


def _school_name():
    return getattr(connection.tenant, "name", "") or ""


def _require(condition, message):
    if not condition:
        raise CertificateError(message)


# --- Integrity ---------------------------------------------------------------

def _canonical(cert):
    payload = {
        "schema": connection.schema_name,
        "id": str(cert.id),
        "number": cert.certificate_number,
        "verification_id": cert.verification_id,
        "type": cert.certificate_type,
        "student": str(cert.student_id) if cert.student_id else None,
        "staff": str(cert.staff_member_id) if cert.staff_member_id else None,
        "issue_date": cert.issue_date.isoformat(),
        "academic_year": cert.academic_year,
        "period_start": cert.period_start.isoformat() if cert.period_start else None,
        "period_end": cert.period_end.isoformat() if cert.period_end else None,
        "leaving_date": cert.leaving_date.isoformat() if cert.leaving_date else None,
        "reason": cert.reason,
        "conduct": cert.conduct,
        "snapshot": cert.snapshot,
        "status": cert.status,
        "issued_by": str(cert.issued_by_user_id),
        "approved_by": str(cert.approved_by_user_id) if cert.approved_by_user_id else None,
        "supersedes": str(cert.supersedes_id) if cert.supersedes_id else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class IntegrityKeyError(CertificateError):
    """A certificate cannot be sealed because no usable integrity key is configured."""


def _parse_keys():
    """{key id: secret bytes} from settings. In local development (DEBUG) with
    nothing configured, a single clearly labelled "dev" key is derived from
    SECRET_KEY; outside DEBUG the settings module refuses to start without
    real keys, and this function never invents one."""
    keys = {}
    for part in (getattr(settings, "CERTIFICATE_INTEGRITY_KEYS", "") or "").split(","):
        part = part.strip()
        if not part:
            continue
        key_id, sep, secret = part.partition(":")
        key_id, secret = key_id.strip(), secret.strip()
        if sep and key_id and secret:
            keys[key_id] = secret.encode("utf-8")
    if not keys and settings.DEBUG:
        keys["dev"] = hashlib.sha256(b"certificates.integrity.dev:" + settings.SECRET_KEY.encode("utf-8")).digest()
    return keys


def _active_key():
    keys = _parse_keys()
    active = (getattr(settings, "CERTIFICATE_INTEGRITY_ACTIVE_KEY", "") or "").strip()
    if not active and settings.DEBUG and "dev" in keys:
        active = "dev"
    if not active or active not in keys:
        raise IntegrityKeyError(
            "Certificates cannot be issued: the active integrity key is not configured. Contact your administrator."
        )
    return active, keys[active]


def _digest(secret, cert):
    return hmac.new(secret, _canonical(cert).encode("utf-8"), hashlib.sha256).hexdigest()


def compute_integrity_hash(cert):
    """Keyed HMAC-SHA256 over the printed content and status, stored as
    "k<key id>:<hex>". It detects a record edited outside the issuing workflow
    only while the key stays secret; it is not tamper-proof on its own. The
    real protection is permissions, audited services and database constraints.
    Raises IntegrityKeyError (fail closed) when no active key is configured."""
    key_id, secret = _active_key()
    return f"k{key_id}:{_digest(secret, cert)}"


def verify_integrity(cert):
    """True only if the stored seal matches. Verifies with the key the seal
    names; an unknown/retired key, a missing key or any other format fails
    closed. Unversioned legacy digests (SECRET_KEY, pre-rotation) are accepted
    only while CERTIFICATE_ACCEPT_LEGACY_SEALS is on."""
    stored = cert.integrity_hash or ""
    if stored.startswith("k") and ":" in stored:
        key_id, _, digest = stored[1:].partition(":")
        secret = _parse_keys().get(key_id)
        if secret is None:
            return False
        return constant_time_compare(digest, _digest(secret, cert))
    if len(stored) == 64 and getattr(settings, "CERTIFICATE_ACCEPT_LEGACY_SEALS", False):
        legacy = salted_hmac("certificates.integrity.v1", _canonical(cert), algorithm="sha256").hexdigest()
        return constant_time_compare(stored, legacy)
    return False


def seal_key_id(cert):
    """Which key sealed this record ("legacy" for unversioned digests)."""
    stored = cert.integrity_hash or ""
    if stored.startswith("k") and ":" in stored:
        return stored[1:].partition(":")[0]
    return "legacy"


def _seal(cert):
    cert.integrity_hash = compute_integrity_hash(cert)


# --- Numbering ---------------------------------------------------------------

def allocate_number(certificate_type, year):
    """Next number for (type, year) in this tenant. Must run inside a
    transaction; the sequence row stays locked until it commits, so concurrent
    issuers queue instead of colliding."""
    try:
        with transaction.atomic():
            CertificateSequence.objects.get_or_create(certificate_type=certificate_type, year=year)
    except IntegrityError:
        pass  # another issuer created the row first
    sequence = CertificateSequence.objects.select_for_update().get(certificate_type=certificate_type, year=year)
    sequence.last_number += 1
    sequence.save(update_fields=["last_number"])
    return f"{NUMBER_PREFIX[certificate_type]}-{year}-{sequence.last_number:05d}"


# --- Subject data -------------------------------------------------------------

def _latest_enrollment(student):
    from students.models import StudentLevel

    return (
        StudentLevel.objects.filter(student=student)
        .select_related("level", "section")
        .order_by("-is_current", "-id")
        .first()
    )


def _student_snapshot(student, certificate_type, extra):
    from profiles.models import InstitutionProfile

    enrollment = _latest_enrollment(student)
    profile = student.profile
    snap = {
        "school_name": _school_name(),
        "holder_name": _full_name(profile),
        "enrollment_id": student.enrollment_id,
        "admission_date": student.admission_date.isoformat() if student.admission_date else None,
        "level_name": enrollment.level.name if enrollment and enrollment.level else "",
        "section_name": enrollment.section.name if enrollment and enrollment.section else "",
    }
    if certificate_type == Certificate.Type.TRANSFER:
        institution = InstitutionProfile.objects.first()
        snap["affiliation_number"] = getattr(institution, "affiliation_number", "") or ""
        snap["school_code"] = getattr(institution, "school_code", "") or ""
        snap["udise_code"] = getattr(institution, "udise_code", "") or ""
        snap["board_name"] = getattr(institution, "board_name", "CBSE") or "CBSE"

        snap["pen"] = getattr(student, "pen", "") or ""
        snap["apaar_id"] = getattr(student, "apaar_id", "") or ""
        caste_cat = getattr(student, "caste_category", "GEN")
        snap["caste_category"] = caste_cat
        snap["caste_category_label"] = getattr(student, "get_caste_category_display", lambda: caste_cat)()
        snap["is_rte"] = getattr(student, "is_rte", False)

        snap["mother_name"] = extra.get("mother_name") or getattr(student, "get_mother_name", lambda: "")()
        snap["father_name"] = extra.get("father_name") or getattr(student, "get_father_name", lambda: "")()
        snap["guardian_name"] = extra.get("guardian_name") or getattr(student, "get_guardian_name", lambda: "")()

        if profile.date_of_birth:
            snap["date_of_birth"] = profile.date_of_birth.isoformat()
            snap["dob_figures"] = profile.date_of_birth.strftime("%d-%m-%Y")
            snap["dob_words"] = date_to_words(profile.date_of_birth)
        else:
            snap["date_of_birth"] = None
            snap["dob_figures"] = ""
            snap["dob_words"] = ""

        auto_dues, auto_concession = check_student_fee_dues(student)
        snap["dues_paid_up_to"] = extra.get("dues_paid_up_to") or auto_dues
        snap["fee_concession"] = extra.get("fee_concession") or auto_concession

        if enrollment and enrollment.level:
            subjects_qs = enrollment.level.subjects.values_list("name", flat=True)
            auto_subjects = ", ".join(subjects_qs)
        else:
            auto_subjects = ""
        snap["subjects_studied"] = extra.get("subjects_studied") or auto_subjects

        snap["nationality"] = extra.get("nationality") or "Indian"
        snap["admission_class"] = extra.get("admission_class") or (enrollment.level.name if enrollment and enrollment.level else "")
        snap["class_last_studied"] = extra.get("class_last_studied") or (enrollment.level.name if enrollment and enrollment.level else "")
        snap["last_exam_result"] = extra.get("last_exam_result") or "Passed"
        snap["failed_status"] = extra.get("failed_status") or "No"
        snap["qualified_for_promotion"] = extra.get("qualified_for_promotion") or "Yes"
        snap["promoted_to_class"] = extra.get("promoted_to_class") or ""
        snap["total_working_days"] = extra.get("total_working_days") or ""
        snap["working_days_present"] = extra.get("working_days_present") or ""
        snap["ncc_scout_guide"] = extra.get("ncc_scout_guide") or "No"
        snap["games_activities"] = extra.get("games_activities") or ""
        snap["application_date"] = extra.get("application_date") or timezone.localdate().isoformat()
        snap["remarks"] = extra.get("remarks") or ""

    snap.update(extra)
    return snap, (enrollment.academic_year if enrollment else "")


def _staff_snapshot(staff, extra):
    profile = staff.profile
    snap = {
        "school_name": _school_name(),
        "holder_name": _full_name(profile),
        "employee_id": staff.employee_id,
        "designation": staff.designation,
        "department": staff.department,
    }
    snap.update(extra)
    return snap


def _parse_date(value, label):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        raise CertificateError(f"{label} must be a valid date (YYYY-MM-DD).")


def _build_content(certificate_type, subject, data):
    """Validates type-specific rules and returns the field values and snapshot.
    Raises CertificateError; never writes."""
    from .pdf import unsupported_characters

    fields, snapshot = _build_content_unchecked(certificate_type, subject, data)
    text = " ".join(str(v) for v in snapshot.values() if isinstance(v, str))
    bad = unsupported_characters(text)
    _require(
        not bad,
        "The certificate font cannot print these characters: " + " ".join(bad)
        + ". Use Latin characters, or ask your administrator to add a font for this script.",
    )
    return fields, snapshot


def authoritative_exit_record(student):
    """The Promotion & Transfer workflow record that proves this student left
    through an authorized process, or None. It is append-only and an exit
    cannot be reversed (only promoted/retained can), so the newest
    transferred/withdrawn record for THIS student must also agree with the
    student's current status. Students whose status was set outside that
    workflow (Django admin, direct database edits, legacy imports) have no
    such record and are deliberately not eligible; see the Phase 6
    remediation report for the proposed audited override."""
    from students.models import PromotionRecord

    record = (
        PromotionRecord.objects.filter(student=student, action__in=TRANSFER_ELIGIBLE_STATUSES)
        .order_by("-created_at", "-id")
        .first()
    )
    if record is None or record.action != student.status:
        return None
    return record


def _build_content_unchecked(certificate_type, subject, data):
    today = timezone.localdate()
    reason = (data.get("reason") or "").strip()
    conduct = (data.get("conduct") or "").strip()
    fields = {"reason": reason, "conduct": conduct, "academic_year": "", "leaving_date": None,
              "period_start": None, "period_end": None}

    if certificate_type in Certificate.STUDENT_TYPES:
        student = subject
        status = student.status
        if certificate_type == Certificate.Type.TRANSFER:
            _require(
                status in TRANSFER_ELIGIBLE_STATUSES,
                "A transfer certificate can only be issued for a student whose status is Transferred or Withdrawn.",
            )
            exit_record = authoritative_exit_record(student)
            _require(
                exit_record is not None,
                "This student's exit is not recorded in the Promotion & Transfer workflow, so a transfer "
                "certificate cannot be issued. Record the transfer or withdrawal there first, or ask the "
                "school owner to authorize an exception.",
            )
            leaving = _parse_date(data.get("leaving_date"), "Leaving date")
            _require(leaving is not None, "Leaving date is required.")
            _require(leaving <= today, "Leaving date cannot be in the future.")
            if student.admission_date:
                _require(leaving >= student.admission_date, "Leaving date cannot be before the admission date.")
            _require(reason, "Reason for leaving is required.")
            fields["leaving_date"] = leaving
            extra = {
                "leaving_date": leaving.isoformat(), "reason": reason, "conduct": conduct,
                "exit_action": exit_record.action, "exit_recorded_on": exit_record.created_at.date().isoformat(),
            }
            cbse_tc_keys = [
                "mother_name", "father_name", "guardian_name", "nationality",
                "caste_category", "admission_class", "class_last_studied",
                "last_exam_result", "failed_status", "subjects_studied",
                "qualified_for_promotion", "promoted_to_class", "dues_paid_up_to",
                "fee_concession", "total_working_days", "working_days_present",
                "ncc_scout_guide", "games_activities", "remarks", "application_date",
            ]
            for k in cbse_tc_keys:
                if k in data and data[k] not in (None, ""):
                    extra[k] = str(data[k]).strip() if not isinstance(data[k], datetime.date) else data[k].isoformat()
        elif certificate_type == Certificate.Type.BONAFIDE:
            _require(status in BONAFIDE_ELIGIBLE_STATUSES, "A bonafide certificate requires a currently active student.")
            extra = {"purpose": reason}
        else:
            _require(status in CHARACTER_ELIGIBLE_STATUSES, "A character certificate cannot be issued for an inactive student.")
            _require(conduct, "Conduct is required.")
            extra = {"conduct": conduct}
        snapshot, enrolled_year = _student_snapshot(student, certificate_type, extra)
        fields["academic_year"] = (data.get("academic_year") or enrolled_year or "").strip()
        _require(fields["academic_year"], "Academic year is required because the student has no enrollment record.")
        snapshot["academic_year"] = fields["academic_year"]
        return fields, snapshot

    staff = subject
    _require(
        not staff.is_active,
        "This staff member is still active. An experience certificate covers a finished period of employment; "
        "mark the staff member inactive first. ('Employed to date' wording needs the school owner's approval.)",
    )
    _require(
        staff.joining_date is not None,
        "The staff record has no joining date, so the employment start cannot be certified. "
        "Add the joining date to the staff record first.",
    )
    start = staff.joining_date
    typed_start = _parse_date(data.get("period_start"), "Employment start date")
    _require(
        typed_start is None or typed_start == start,
        "The employment start date always comes from the staff record's joining date and cannot be overridden here.",
    )
    end = _parse_date(data.get("period_end"), "Employment end date")
    # The staff record stores no exit date, so the end date is entered by the
    # issuer. It is labelled as such in the snapshot and the audit log.
    _require(end is not None, "Employment end date is required (the staff record stores no exit date).")
    _require(end >= start, "Employment end date cannot be before the joining date.")
    _require(end <= today, "Employment end date cannot be in the future.")
    fields["period_start"], fields["period_end"] = start, end
    snapshot = _staff_snapshot(
        staff,
        {
            "period_start": start.isoformat(), "period_end": end.isoformat(), "reason": reason, "conduct": conduct,
            "end_date_source": "issuer_entered",
        },
    )
    return fields, snapshot


# --- Issue / cancel / reissue ---------------------------------------------------

def _live_certificate(certificate_type, subject):
    qs = Certificate.objects.filter(certificate_type=certificate_type, status=Certificate.Status.ISSUED)
    if certificate_type in Certificate.STUDENT_TYPES:
        return qs.filter(student=subject).first()
    return qs.filter(staff_member=subject).first()


def _create(certificate_type, subject, data, issued_by_user_id, approved_by_user_id, supersedes=None, reissue_reason=""):
    fields, snapshot = _build_content(certificate_type, subject, data)
    issue_date = timezone.localdate()
    try:
        with transaction.atomic():
            cert = Certificate(
                certificate_type=certificate_type,
                certificate_number=allocate_number(certificate_type, issue_date.year),
                issue_date=issue_date,
                snapshot=snapshot,
                issued_by_user_id=issued_by_user_id,
                approved_by_user_id=approved_by_user_id,
                supersedes=supersedes,
                reissue_reason=reissue_reason,
                internal_notes=(data.get("internal_notes") or "").strip(),
                **fields,
            )
            if certificate_type in Certificate.STUDENT_TYPES:
                cert.student = subject
            else:
                cert.staff_member = subject
            cert.clean()
            _seal(cert)
            cert.save()
    except IntegrityError:
        # The partial unique indexes: someone else issued the same live TC or
        # experience certificate first. The savepoint rolled the number back.
        raise CertificateError("A live certificate of this type already exists. Cancel or reissue it instead.")
    return cert


@transaction.atomic
def issue_certificate(*, certificate_type, subject, data, issued_by_user_id, approved_by_user_id=None):
    if certificate_type in APPROVAL_TYPES:
        _require(approved_by_user_id is not None, "This certificate type requires an approver.")
    # Serialize concurrent issuance for the same person (also covers the
    # non-unique bonafide/character types); the partial unique indexes remain
    # the final guard for TC and experience.
    type(subject).objects.select_for_update().get(pk=subject.pk)
    existing = _live_certificate(certificate_type, subject)
    if existing and certificate_type in APPROVAL_TYPES:
        raise CertificateError(
            f"A live certificate ({existing.certificate_number}) already exists. Cancel or reissue it instead."
        )
    return _create(certificate_type, subject, data, issued_by_user_id, approved_by_user_id)


@transaction.atomic
def cancel_certificate(*, certificate_id, user_id, reason):
    reason = (reason or "").strip()
    _require(reason, "A cancellation reason is required.")
    cert = Certificate.objects.select_for_update().get(pk=certificate_id)
    _require(cert.status == Certificate.Status.ISSUED, "Only an issued certificate can be cancelled.")
    cert.status = Certificate.Status.CANCELLED
    cert.cancelled_by_user_id = user_id
    cert.cancelled_at = timezone.now()
    cert.cancellation_reason = reason[:255]
    _seal(cert)
    cert.save(update_fields=["status", "cancelled_by_user_id", "cancelled_at", "cancellation_reason", "integrity_hash"])
    return cert


@transaction.atomic
def reissue_certificate(*, certificate_id, user_id, approved_by_user_id, reason, data):
    """Replaces a certificate with a new, freshly numbered one. The old record
    stays (superseded, or cancelled if it already was) and is linked to the
    replacement; the student/staff record is not touched."""
    reason = (reason or "").strip()
    _require(reason, "A reissue reason is required.")
    old = Certificate.objects.select_for_update().get(pk=certificate_id)
    _require(
        old.status in (Certificate.Status.ISSUED, Certificate.Status.CANCELLED),
        "This certificate has already been replaced.",
    )
    _require(not hasattr(old, "superseded_by"), "This certificate has already been replaced.")
    subject = old.student or old.staff_member
    type(subject).objects.select_for_update().get(pk=subject.pk)

    # Pre-fill from the original so a reissue only needs the corrected fields.
    merged = {
        "reason": old.reason, "conduct": old.conduct, "academic_year": old.academic_year,
        "leaving_date": old.leaving_date, "period_start": old.period_start, "period_end": old.period_end,
        "internal_notes": old.internal_notes,
    }
    merged.update({k: v for k, v in data.items() if v not in (None, "")})

    if old.status == Certificate.Status.ISSUED:
        # Frees the partial unique index slot for the replacement.
        old.status = Certificate.Status.SUPERSEDED
        _seal(old)
        old.save(update_fields=["status", "integrity_hash"])
    new = _create(
        old.certificate_type, subject, merged, user_id, approved_by_user_id,
        supersedes=old, reissue_reason=reason[:255],
    )
    return old, new


# --- Public verification ----------------------------------------------------------

def public_verification(cert):
    """The only certificate data that leaves the tenant unauthenticated. No
    address, date of birth, contact data, enrollment/employee ids, reason,
    conduct, notes or internal ids."""
    intact = verify_integrity(cert)
    replaced_by = None
    if hasattr(cert, "superseded_by"):
        replaced_by = cert.superseded_by.certificate_number
    return {
        "valid": intact and cert.status == Certificate.Status.ISSUED,
        "status": cert.status if intact else "integrity_failed",
        "certificate_type": cert.certificate_type,
        "certificate_type_label": cert.get_certificate_type_display(),
        "certificate_number": cert.certificate_number,
        "issue_date": cert.issue_date.isoformat(),
        "school_name": cert.snapshot.get("school_name", ""),
        "holder_name": cert.snapshot.get("holder_name", "") if intact else "",
        "replaced_by_number": replaced_by,
    }
