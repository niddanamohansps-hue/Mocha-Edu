"""ID card data. Deliberately minimal: name, id number, class/designation,
photo. No date of birth, address, phone, blood group or guardian details."""

import base64
import io
import re

from django.conf import settings
from django.core import signing
from django.db import connection
from PIL import Image

from .services import CertificateError

SALT = "certificates.idcard.v1"  # legacy signed tokens only
KIND_STUDENT = "student"
KIND_STAFF = "staff"
OPAQUE_RE = re.compile(r"^[A-Za-z0-9_-]{32}$")


def card_token(kind, record):
    """The live opaque token for a card holder, created on first use. The
    token is random, so it reveals nothing about the record, tenant or person.
    Two requests racing to create it are resolved by the one-live-token
    unique constraint: the loser re-reads the winner's row."""
    from django.db import IntegrityError, transaction

    from .models import IdCardToken

    field = "student" if kind == KIND_STUDENT else "staff_member"
    live = IdCardToken.objects.filter(**{field: record, "revoked_at__isnull": True}).first()
    if live:
        return live.token
    for _ in range(3):  # a token collision is astronomically unlikely; retry rather than fail
        try:
            with transaction.atomic():
                return IdCardToken.objects.create(kind=kind, **{field: record}).token
        except IntegrityError:
            live = IdCardToken.objects.filter(**{field: record, "revoked_at__isnull": True}).first()
            if live:
                return live.token
    raise CertificateError("Could not create the ID card token. Please try again.")


def rotate_card_token(kind, record):
    """Revokes the live token (a lost card) and issues a new one. Returns
    (new token, revoked token row id) - never the old secret."""
    from django.db import transaction
    from django.utils import timezone

    from .models import IdCardToken

    field = "student" if kind == KIND_STUDENT else "staff_member"
    with transaction.atomic():
        old = IdCardToken.objects.select_for_update().filter(**{field: record, "revoked_at__isnull": True}).first()
        old_id = None
        if old:
            old.revoked_at = timezone.now()
            old.save(update_fields=["revoked_at"])
            old_id = old.id
        return card_token(kind, record), old_id


def read_legacy_token(token):
    """Old printed cards: a Django-signed token that embeds the record UUID and
    schema name. Accepted for verification only, and only while
    ID_CARD_ACCEPT_LEGACY_TOKENS is on. Never produced any more."""
    if not getattr(settings, "ID_CARD_ACCEPT_LEGACY_TOKENS", False):
        return None
    try:
        data = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
    if data.get("s") != connection.schema_name or data.get("k") not in (KIND_STUDENT, KIND_STAFF):
        return None
    return data


def frontend_url(request, path):
    host = request.get_host().split(":")[0]
    port = f":{settings.PASSWORD_RESET_FRONTEND_PORT}" if settings.PASSWORD_RESET_FRONTEND_PORT else ""
    return f"{settings.PASSWORD_RESET_FRONTEND_PROTOCOL}://{host}{port}{path}"


def _name(profile):
    return " ".join(p for p in (profile.first_name, profile.middle_name, profile.last_name) if p).strip()


def field_data_uri(field, max_px=240):
    """Small JPEG data URI of an ImageField file, or None. Embedded so the
    print view does not depend on the (unauthenticated) /media/ route."""
    try:
        if not field or not field.name:
            return None
        with field.open("rb") as fh:
            image = Image.open(io.BytesIO(fh.read()))
        image.thumbnail((max_px, max_px))
        out = io.BytesIO()
        image.convert("RGB").save(out, format="JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return None


def photo_data_uri(profile, max_px=240):
    return field_data_uri(profile.profile_image, max_px)


def ensure_printable(card):
    """The ID-card PDF uses the same font as certificates, which cannot draw
    most non-Latin scripts. Refuse instead of printing empty boxes (the
    on-screen print view uses the browser's fonts and is not affected)."""
    from .pdf import unsupported_characters

    text = " ".join([card["school_name"], card["holder_name"], card["id_number"]] + [v for _, v in card["details"] if v])
    bad = unsupported_characters(text)
    if bad:
        raise CertificateError(
            "The PDF font cannot print these characters: " + " ".join(bad)
            + ". Use the Print button for this card, or ask your administrator to add a font for this script."
        )


def build_student_card(student):
    if student.status != "active":
        raise CertificateError("An ID card can only be generated for an active student.")
    from students.models import StudentLevel

    enrollment = (
        StudentLevel.objects.filter(student=student).select_related("level", "section").order_by("-is_current", "-id").first()
    )
    klass = ""
    year = ""
    if enrollment:
        klass = " ".join(p for p in (enrollment.level.name if enrollment.level else "", enrollment.section.name if enrollment.section else "") if p)
        year = enrollment.academic_year
    return {
        "kind": KIND_STUDENT,
        "kind_label": "Student",
        "school_name": getattr(connection.tenant, "name", ""),
        "holder_name": _name(student.profile),
        "id_number": student.enrollment_id,
        "details": [("Class", klass), ("Year", year)],
    }


def build_staff_card(staff):
    if not staff.is_active:
        raise CertificateError("An ID card can only be generated for an active staff member.")
    return {
        "kind": KIND_STAFF,
        "kind_label": "Staff",
        "school_name": getattr(connection.tenant, "name", ""),
        "holder_name": _name(staff.profile),
        "id_number": staff.employee_id,
        "details": [("Designation", staff.designation), ("Dept", staff.department)],
    }


def public_card_verification(token):
    """Minimal public answer for a scanned ID card QR: is it a currently valid
    card of this school, and for whom (first name + last initial only). An
    unknown, malformed or revoked token all give the same answer."""
    from .models import IdCardToken

    invalid = {"valid": False, "kind": None, "school_name": "", "holder": "", "status": "invalid"}
    record = kind = None
    if OPAQUE_RE.match(token or ""):
        row = (
            IdCardToken.objects.select_related("student__profile", "staff_member__profile")
            .filter(token=token, revoked_at__isnull=True)
            .first()
        )
        if row is None:
            return invalid
        kind = row.kind
        record = row.student if kind == KIND_STUDENT else row.staff_member
    else:
        data = read_legacy_token(token or "")
        if data is None:
            return invalid
        kind = data["k"]
        if kind == KIND_STUDENT:
            from students.models import Student

            record = Student.objects.select_related("profile").filter(pk=data["i"]).first()
        else:
            from staff.models import StaffMember

            record = StaffMember.objects.select_related("profile").filter(pk=data["i"]).first()
    if record is None:
        return invalid
    active = record.status == "active" if kind == KIND_STUDENT else record.is_active
    last = record.profile.last_name
    holder = f"{record.profile.first_name} {last[:1]}." if last else record.profile.first_name
    return {
        "valid": bool(active),
        "kind": kind,
        "school_name": getattr(connection.tenant, "name", ""),
        "holder": holder,
        "status": "active" if active else "inactive",
    }
