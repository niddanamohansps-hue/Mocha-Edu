import uuid

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class VisitorLog(models.Model):
    """
    Log of campus visitors, parents, vendors, and guests checked in at the school gate.
    """

    class IdProof(models.TextChoices):
        AADHAAR = "aadhaar", "Aadhaar Card"
        VOTER_ID = "voter_id", "Voter ID"
        DRIVING_LICENSE = "driving_license", "Driving License"
        PAN = "pan", "PAN Card"
        PASSPORT = "passport", "Passport"
        OTHER = "other", "Other"

    class Purpose(models.TextChoices):
        PARENT_MEETING = "parent_meeting", "Meet Teacher / Staff"
        PRINCIPAL_MEETING = "principal_meeting", "Meet Principal / Management"
        ADMISSION_INQUIRY = "admission_inquiry", "Admission Inquiry / Campus Tour"
        FEE_PAYMENT = "fee_payment", "Fee Payment / Accounts"
        VENDOR_DELIVERY = "vendor_delivery", "Vendor / Delivery / Contractor"
        DOCUMENT_SUBMISSION = "document_submission", "Document Submission / Verification"
        OFFICIAL_INSPECTION = "official_inspection", "Education Dept / Board Inspection"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Inside Campus"
        CHECKED_OUT = "checked_out", "Checked Out"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pass_number = models.CharField(max_length=50, unique=True)
    visitor_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    id_proof_type = models.CharField(max_length=50, choices=IdProof.choices, default=IdProof.AADHAAR)
    id_proof_number = models.CharField(max_length=50, blank=True)
    organization = models.CharField(max_length=150, blank=True, help_text="Company or residential area")
    purpose = models.CharField(max_length=50, choices=Purpose.choices, default=Purpose.PARENT_MEETING)
    purpose_details = models.CharField(max_length=255, blank=True)

    person_to_meet_staff = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitor_meetings",
    )
    person_to_meet_name = models.CharField(max_length=150, blank=True)
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitor_visits",
    )

    number_of_visitors = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    badge_number = models.CharField(max_length=50, blank=True, help_text="Badge or tag ID given at security gate")
    vehicle_number = models.CharField(max_length=30, blank=True)

    check_in_time = models.DateTimeField(default=timezone.now)
    check_out_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    remarks = models.TextField(blank=True)

    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-check_in_time"]
        indexes = [
            models.Index(fields=["status", "-check_in_time"], name="visitor_status_time_idx"),
            models.Index(fields=["phone"], name="visitor_phone_idx"),
            models.Index(fields=["pass_number"], name="visitor_pass_idx"),
        ]

    def __str__(self):
        return f"{self.pass_number} - {self.visitor_name} ({self.status})"


class StudentGatePass(models.Model):
    """
    Authorized gate pass permitting a student to leave campus before regular dismissal.
    Mandatory safety protocol in Indian schools.
    """

    class ReasonCategory(models.TextChoices):
        ILLNESS = "illness", "Medical / Sickness / Fever"
        FAMILY_EMERGENCY = "family_emergency", "Family Emergency"
        DOCTOR_APPOINTMENT = "doctor_appointment", "Doctor / Dental Appointment"
        EVENT_TOURNAMENT = "event_tournament", "External Competition / Sports Tournament"
        AUTHORIZED_EARLY_LEAVE = "authorized_early_leave", "Authorized Early Departure"
        OTHER = "other", "Other"

    class Relationship(models.TextChoices):
        FATHER = "father", "Father"
        MOTHER = "mother", "Mother"
        GUARDIAN = "guardian", "Guardian"
        SIBLING = "sibling", "Brother / Sister"
        AUTHORIZED_RELATIVE = "authorized_relative", "Authorized Relative / Driver"
        SELF = "self", "Self (Parent Consent Provided)"

    class Status(models.TextChoices):
        ISSUED = "issued", "Issued / Pending Gate Exit"
        DEPARTED = "departed", "Departed Campus"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pass_number = models.CharField(max_length=50, unique=True)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="gate_passes")
    departure_date = models.DateField(default=timezone.localdate)
    departure_time = models.DateTimeField(default=timezone.now)
    actual_exit_time = models.DateTimeField(null=True, blank=True)

    reason_category = models.CharField(max_length=50, choices=ReasonCategory.choices, default=ReasonCategory.ILLNESS)
    reason_details = models.TextField(blank=True)

    picked_up_by_name = models.CharField(max_length=150, help_text="Full name of person picking up the student")
    relationship = models.CharField(max_length=50, choices=Relationship.choices, default=Relationship.FATHER)
    picked_up_by_phone = models.CharField(max_length=20)

    authorized_by_staff = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authorized_gate_passes",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ISSUED)
    gate_security_note = models.CharField(max_length=255, blank=True, help_text="Gate guard remarks on departure")

    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-departure_time"]
        indexes = [
            models.Index(fields=["status", "-departure_time"], name="gatepass_status_time_idx"),
            models.Index(fields=["departure_date"], name="gatepass_date_idx"),
            models.Index(fields=["student", "-departure_time"], name="gatepass_student_idx"),
        ]

    def __str__(self):
        return f"{self.pass_number} - {self.student} ({self.status})"


class PostalRecord(models.Model):
    """
    Log of inward and outward speed post, courier parcels, and official dispatches.
    """

    class RecordType(models.TextChoices):
        INWARD = "inward", "Inward / Received"
        OUTWARD = "outward", "Outward / Dispatched"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tracking_number = models.CharField(max_length=100, blank=True, help_text="Consignment or speed post barcode number")
    record_type = models.CharField(max_length=20, choices=RecordType.choices, default=RecordType.INWARD)
    title = models.CharField(max_length=200, help_text="Subject or parcel contents")
    from_title = models.CharField(max_length=150, help_text="Sender name or department")
    to_title = models.CharField(max_length=150, help_text="Recipient name or department")
    courier_company = models.CharField(max_length=100, blank=True, help_text="India Post, BlueDart, DTDC, etc.")
    dispatch_date = models.DateField(default=timezone.localdate)
    reference_number = models.CharField(max_length=100, blank=True)

    recipient_staff = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="postal_records",
    )
    notes = models.TextField(blank=True)

    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-dispatch_date", "-created_at"]
        indexes = [
            models.Index(fields=["record_type", "-dispatch_date"], name="postal_type_date_idx"),
            models.Index(fields=["tracking_number"], name="postal_tracking_idx"),
        ]

    def __str__(self):
        return f"{self.record_type.upper()}: {self.title} ({self.dispatch_date})"

