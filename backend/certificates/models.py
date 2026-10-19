import secrets
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class CertificateSettings(models.Model):
    """Per-tenant singleton: who signs certificates. The school name and logo
    come from the Organization and InstitutionProfile; nothing is duplicated."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signatory_name = models.CharField(max_length=150, blank=True)
    signatory_title = models.CharField(max_length=150, blank=True)
    signature = models.ImageField(upload_to="certificates/signatures/", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Certificate settings"

    @classmethod
    def load(cls):
        obj = cls.objects.first()
        return obj or cls.objects.create()


class CertificateSequence(models.Model):
    """One row per (type, calendar year) in the tenant's own schema. Rows are
    row-locked (select_for_update) while a number is allocated, so concurrent
    issuance cannot hand out the same number. Being tenant-schema tables, the
    counters of one school are invisible to every other school."""

    certificate_type = models.CharField(max_length=20)
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["certificate_type", "year"], name="cert_sequence_type_year_uniq"),
        ]


def new_verification_id():
    return secrets.token_urlsafe(24)


class Certificate(models.Model):
    class Type(models.TextChoices):
        TRANSFER = "transfer", "Transfer Certificate"
        BONAFIDE = "bonafide", "Bonafide Certificate"
        CHARACTER = "character", "Character Certificate"
        EXPERIENCE = "experience", "Staff Experience Certificate"

    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        CANCELLED = "cancelled", "Cancelled"
        SUPERSEDED = "superseded", "Superseded"

    STUDENT_TYPES = (Type.TRANSFER, Type.BONAFIDE, Type.CHARACTER)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certificate_type = models.CharField(max_length=20, choices=Type.choices)
    certificate_number = models.CharField(max_length=40, unique=True, editable=False)
    verification_id = models.CharField(max_length=64, unique=True, default=new_verification_id, editable=False)

    # PROTECT: a certificate is a historical record and must never vanish with
    # the person it was issued for.
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="certificates"
    )
    staff_member = models.ForeignKey(
        "staff.StaffMember", null=True, blank=True, on_delete=models.PROTECT, related_name="certificates"
    )

    issue_date = models.DateField()
    academic_year = models.CharField(max_length=20, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    leaving_date = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    conduct = models.CharField(max_length=100, blank=True)
    # Staff-only context: never rendered on the PDF and never public.
    internal_notes = models.TextField(blank=True)

    # Everything printed on the document, frozen at issue time.
    snapshot = models.JSONField(default=dict)
    # "k<key id>:<hex>" (see services.seal). Legacy rows hold a bare 64-char digest.
    integrity_hash = models.CharField(max_length=128, editable=False)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ISSUED)
    issued_by_user_id = models.UUIDField()
    approved_by_user_id = models.UUIDField(null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    cancelled_by_user_id = models.UUIDField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)

    supersedes = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by"
    )
    reissue_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-issued_at", "-id"]
        constraints = [
            models.CheckConstraint(
                name="cert_exactly_one_subject",
                condition=(
                    (Q(student__isnull=False) & Q(staff_member__isnull=True))
                    | (Q(student__isnull=True) & Q(staff_member__isnull=False))
                ),
            ),
            # Duplicate-issuance guard: at most one live TC per student and one
            # live experience certificate per staff member. Cancel or reissue
            # to replace it.
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(certificate_type="transfer", status="issued"),
                name="cert_one_live_transfer_per_student",
            ),
            models.UniqueConstraint(
                fields=["staff_member"],
                condition=Q(certificate_type="experience", status="issued"),
                name="cert_one_live_experience_per_staff",
            ),
        ]
        indexes = [
            models.Index(fields=["certificate_type", "status"], name="cert_type_status_idx"),
            models.Index(fields=["student", "certificate_type"], name="cert_student_type_idx"),
        ]

    def clean(self):
        is_student_type = self.certificate_type in self.STUDENT_TYPES
        if is_student_type and not self.student_id:
            raise ValidationError("This certificate type requires a student.")
        if not is_student_type and not self.staff_member_id:
            raise ValidationError("This certificate type requires a staff member.")

    def __str__(self):
        return f"{self.certificate_number} ({self.get_certificate_type_display()})"


def new_card_token():
    return secrets.token_urlsafe(24)  # 192 bits, 32 URL-safe characters


class IdCardToken(models.Model):
    """Opaque public identifier printed (as a QR) on an ID card. It is random:
    it carries no record id, tenant name or personal data, and cannot be
    derived from anything. Rotating revokes the old token and issues a new one
    (a lost or reprinted card). One live token per card holder."""

    class Kind(models.TextChoices):
        STUDENT = "student", "Student"
        STAFF = "staff", "Staff"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True, default=new_card_token, editable=False)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.CASCADE, related_name="id_card_tokens"
    )
    staff_member = models.ForeignKey(
        "staff.StaffMember", null=True, blank=True, on_delete=models.CASCADE, related_name="id_card_tokens"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="idcard_exactly_one_subject",
                condition=(
                    (Q(student__isnull=False) & Q(staff_member__isnull=True))
                    | (Q(student__isnull=True) & Q(staff_member__isnull=False))
                ),
            ),
            models.UniqueConstraint(
                fields=["student"], condition=Q(revoked_at__isnull=True), name="idcard_one_live_token_per_student"
            ),
            models.UniqueConstraint(
                fields=["staff_member"], condition=Q(revoked_at__isnull=True), name="idcard_one_live_token_per_staff"
            ),
        ]
