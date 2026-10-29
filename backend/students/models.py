from django.db import models
from django.utils import timezone
import uuid


class Student(models.Model):
    """
    Academic Domain: Stores data specific to a person's life as a student.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.OneToOneField(
        "profiles.Profile", on_delete=models.CASCADE, related_name="student_record"
    )

    enrollment_id = models.CharField(max_length=50, unique=True)
    admission_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("graduated", "Graduated"),
            ("withdrawn", "Withdrawn"),
            ("transferred", "Transferred"),
        ],
        default="active",
    )

    # Statutory Indian School Compliance & Identity
    apaar_id = models.CharField(
        max_length=12,
        blank=True,
        default="",
        help_text="12-digit Automated Permanent Academic Account Registry ID",
    )
    pen = models.CharField(
        max_length=11,
        blank=True,
        default="",
        help_text="11-digit Permanent Education Number from UDISE+",
    )
    caste_category = models.CharField(
        max_length=10,
        choices=[
            ("GEN", "General"),
            ("OBC", "OBC"),
            ("SC", "SC"),
            ("ST", "ST"),
            ("EWS", "EWS"),
        ],
        default="GEN",
    )
    is_rte = models.BooleanField(
        default=False,
        help_text="Right to Education Act Section 12(1)(c) 25% quota student",
    )
    aadhaar_last_4 = models.CharField(
        max_length=4,
        blank=True,
        default="",
        help_text="Last 4 digits of Aadhaar (masked for UIDAI compliance)",
    )
    aadhaar_verified = models.BooleanField(default=False)
    mother_tongue = models.CharField(max_length=50, blank=True, default="Hindi")
    social_category = models.CharField(max_length=50, blank=True, default="")
    religion = models.CharField(max_length=50, blank=True, default="")
    cwsn_status = models.CharField(max_length=50, blank=True, default="", help_text="Children with Special Needs status")
    bpl_status = models.BooleanField(default=False, help_text="Below Poverty Line")

    # Cached parent names for instant board/statutory certificates and imports
    mother_name = models.CharField(max_length=100, blank=True, default="")
    father_name = models.CharField(max_length=100, blank=True, default="")
    guardian_name = models.CharField(max_length=100, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "admission_date"], name="student_status_date_idx"
            ),
            models.Index(fields=["pen"], name="student_pen_idx"),
            models.Index(fields=["apaar_id"], name="student_apaar_idx"),
        ]

    def __str__(self):
        return f"{self.profile.first_name} - {self.enrollment_id}"

    def get_father_name(self):
        if self.father_name:
            return self.father_name
        rel = self.parent_links.filter(relation_type="father").select_related("parent__profile").first()
        if rel and rel.parent and rel.parent.profile:
            p = rel.parent.profile
            return f"{p.first_name} {p.last_name}".strip()
        return ""

    def get_mother_name(self):
        if self.mother_name:
            return self.mother_name
        rel = self.parent_links.filter(relation_type="mother").select_related("parent__profile").first()
        if rel and rel.parent and rel.parent.profile:
            p = rel.parent.profile
            return f"{p.first_name} {p.last_name}".strip()
        return ""

    def get_guardian_name(self):
        if self.guardian_name:
            return self.guardian_name
        rel = self.parent_links.filter(relation_type="guardian").select_related("parent__profile").first()
        if rel and rel.parent and rel.parent.profile:
            p = rel.parent.profile
            return f"{p.first_name} {p.last_name}".strip()
        return ""


class AcademicHistory(models.Model):
    """
    Stores previous schooling information.
    """

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="academic_history"
    )
    previous_school = models.CharField(max_length=255)
    last_grade_passed = models.CharField(max_length=50)
    completion_year = models.IntegerField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Academic Histories"


class StudentLevel(models.Model):
    """
    Tracks which level (Grade/Class) and section a student is in for a given year.
    """

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="enrollments"
    )
    # Link to the Academic Structure
    level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        related_name="student_enrollments",
        null=True,  # Temporarily null for migration safety if needed, or strict if new
    )
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.SET_NULL,
        related_name="student_enrollments",
        null=True,
        blank=True,
    )

    academic_year = models.CharField(max_length=20)  # e.g., 2081 or 2024
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    is_current = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "academic_year")


PROMOTION_ACTION_CHOICES = [
    ("promoted", "Promoted"),
    ("retained", "Retained"),
    ("transferred", "Transferred"),
    ("withdrawn", "Withdrawn"),
    ("graduated", "Graduated"),
    ("reversed", "Reversed"),
]


class PromotionRecord(models.Model):
    """
    Append-only history of every student lifecycle transition performed by
    the Promotion & Transfer workflow. Never updated after creation, and
    never deleted directly - the only way a row disappears is the same
    on_delete=CASCADE already used by AcademicHistory when the parent
    Student is hard-deleted via the existing (untouched) delete endpoint,
    since both are supplementary per-student history rather than
    source-of-truth enrollment data.

    A correction is represented by a NEW row with action="reversed"
    (linked via `reverses`), never by editing an existing row.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="promotion_records"
    )
    action = models.CharField(max_length=20, choices=PROMOTION_ACTION_CHOICES)

    source_academic_year = models.CharField(max_length=20, blank=True)
    source_academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    target_academic_year = models.CharField(max_length=20, blank=True)
    target_academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    source_level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_source",
    )
    target_level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_target",
    )
    source_section = models.ForeignKey(
        "academics.Section",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_source",
    )
    target_section = models.ForeignKey(
        "academics.Section",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_target",
    )

    # Exact StudentLevel row references, so a reversal can restore precisely
    # the row that was current before this action - not just "some row
    # matching this level/year".
    source_student_level = models.ForeignKey(
        StudentLevel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_source",
    )
    target_student_level = models.ForeignKey(
        StudentLevel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotion_records_as_target",
    )

    reason = models.CharField(max_length=255, blank=True)

    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal",
        help_text="Set only on a reversal record - points at the original PromotionRecord it reverses.",
    )

    created_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotion_records_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["student", "-created_at"], name="promorec_student_history_idx"),
            models.Index(fields=["action"], name="promorec_action_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_id} - {self.action} - {self.source_academic_year} -> {self.target_academic_year}"


# =====================================================================
# Admissions Management Pipeline Models
# =====================================================================

ENQUIRY_SOURCE_CHOICES = [
    ("website", "Website"),
    ("walk_in", "Walk-in"),
    ("phone", "Phone Call"),
    ("referral", "Referral"),
    ("campaign", "Social/Ad Campaign"),
    ("other", "Other"),
]

ENQUIRY_STATUS_CHOICES = [
    ("new", "New"),
    ("contacted", "Contacted"),
    ("qualified", "Qualified"),
    ("converted", "Converted to Application"),
    ("closed", "Closed / Lost"),
]


class AdmissionEnquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enquiry_number = models.CharField(max_length=50, unique=True, db_index=True)

    student_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
        blank=True,
        default="",
    )

    guardian_name = models.CharField(max_length=200)
    guardian_relationship = models.CharField(max_length=50, default="father")
    guardian_phone = models.CharField(max_length=30)
    guardian_email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    previous_school = models.CharField(max_length=255, blank=True, default="")

    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    preferred_level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admission_enquiries",
    )

    source = models.CharField(
        max_length=50, choices=ENQUIRY_SOURCE_CHOICES, default="walk_in"
    )
    status = models.CharField(
        max_length=30, choices=ENQUIRY_STATUS_CHOICES, default="new"
    )
    assigned_to = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_enquiries",
    )

    enquiry_date = models.DateField(default=timezone.localdate)
    follow_up_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-enquiry_date"], name="enq_status_date_idx"),
            models.Index(fields=["academic_year"], name="enq_academic_year_idx"),
        ]

    def __str__(self):
        return f"{self.enquiry_number} - {self.student_name} ({self.get_status_display()})"


APPLICATION_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("under_review", "Under Review"),
    ("documents_pending", "Documents Pending"),
    ("documents_verified", "Documents Verified"),
    ("assessment_pending", "Assessment Pending"),
    ("approved", "Approved"),
    ("waitlisted", "Waitlisted"),
    ("rejected", "Rejected"),
    ("offer_accepted", "Offer Accepted"),
    ("enrolled", "Enrolled"),
    ("withdrawn", "Withdrawn"),
]


class AdmissionApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_number = models.CharField(max_length=50, unique=True, db_index=True)

    enquiry = models.ForeignKey(
        AdmissionEnquiry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )
    student = models.OneToOneField(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_application",
    )

    # Student Details
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, default="")
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(
        max_length=20,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
    )
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, default="")
    address = models.TextField(blank=True, default="")
    previous_school = models.CharField(max_length=255, blank=True, default="")
    last_grade_passed = models.CharField(max_length=50, blank=True, default="")

    # Primary Guardian
    guardian_first_name = models.CharField(max_length=100)
    guardian_last_name = models.CharField(max_length=100)
    guardian_relationship = models.CharField(max_length=50, default="father")
    guardian_phone = models.CharField(max_length=30)
    guardian_email = models.EmailField(blank=True, null=True)
    guardian_occupation = models.CharField(max_length=100, blank=True, default="")
    guardian_address = models.TextField(blank=True, default="")

    # Secondary Guardian (Optional)
    secondary_guardian_name = models.CharField(max_length=200, blank=True, default="")
    secondary_guardian_relationship = models.CharField(max_length=50, blank=True, default="")
    secondary_guardian_phone = models.CharField(max_length=30, blank=True, default="")

    # Academic Placement
    academic_year = models.CharField(max_length=20)
    academic_year_ref = models.ForeignKey(
        "academics.AcademicYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        related_name="admission_applications",
    )
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_applications",
    )

    # Workflow Status
    status = models.CharField(
        max_length=30, choices=APPLICATION_STATUS_CHOICES, default="draft"
    )
    submission_date = models.DateTimeField(null=True, blank=True)
    assigned_reviewer = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_applications",
    )
    decision_date = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True, default="")
    decision_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_applications",
    )
    enrolled_at = models.DateTimeField(null=True, blank=True)
    enrolled_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrolled_applications",
    )
    notes = models.TextField(blank=True, default="")
    # Public Self-Service Capability Token (SHA-256 hash stored for secure status & document uploads)
    access_token_hash = models.CharField(max_length=128, blank=True, default="", db_index=True)
    access_token_expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="app_status_created_idx"),
            models.Index(fields=["academic_year"], name="app_academic_year_idx"),
            models.Index(fields=["level"], name="app_level_idx"),
        ]

    def __str__(self):
        return f"{self.application_number} - {self.first_name} {self.last_name} ({self.get_status_display()})"


DOCUMENT_TYPE_CHOICES = [
    ("birth_certificate", "Birth Certificate"),
    ("transfer_certificate", "Transfer Certificate (TC)"),
    ("previous_marksheet", "Previous Academic Marksheet / Report Card"),
    ("photo", "Passport Size Photograph"),
    ("address_proof", "Address Proof"),
    ("medical_record", "Medical Record"),
    ("other", "Other Document"),
]

DOCUMENT_VERIFICATION_STATUS_CHOICES = [
    ("pending", "Pending Verification"),
    ("verified", "Verified"),
    ("rejected", "Rejected / Resubmission Required"),
]

DOCUMENT_SCAN_STATUS_CHOICES = [
    ("pending", "Pending Antivirus Scan"),
    ("clean", "Clean / Passed Scan"),
    ("infected", "Infected / Malware Detected"),
    ("error", "Scan Error / Failed Closed"),
]


class AdmissionDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="admission_documents/%Y/%m/")
    verification_status = models.CharField(
        max_length=20,
        choices=DOCUMENT_VERIFICATION_STATUS_CHOICES,
        default="pending",
    )
    scan_status = models.CharField(
        max_length=20,
        choices=DOCUMENT_SCAN_STATUS_CHOICES,
        default="pending",
        db_index=True,
        help_text="Antivirus quarantine state: newly uploaded files are quarantined until scan succeeds.",
    )
    scanned_at = models.DateTimeField(null=True, blank=True)
    scan_details = models.CharField(max_length=255, blank=True, default="")
    verified_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_admission_documents",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.application.application_number}"


INTERVIEW_TYPE_CHOICES = [
    ("written_test", "Written Assessment"),
    ("student_interview", "Student Interview"),
    ("parent_interaction", "Parent Interaction"),
    ("portfolio_review", "Portfolio Review"),
    ("other", "Other Evaluation"),
]

INTERVIEW_STATUS_CHOICES = [
    ("scheduled", "Scheduled"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

RECOMMENDATION_CHOICES = [
    ("recommended", "Recommended for Admission"),
    ("conditional", "Conditional Acceptance"),
    ("waitlist", "Waitlist Recommended"),
    ("not_recommended", "Not Recommended"),
]


class AdmissionInterview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name="interviews",
    )
    interview_type = models.CharField(
        max_length=50, choices=INTERVIEW_TYPE_CHOICES, default="student_interview"
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    interviewer = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conducted_admission_interviews",
    )
    status = models.CharField(
        max_length=20, choices=INTERVIEW_STATUS_CHOICES, default="scheduled"
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recommendation = models.CharField(
        max_length=30, choices=RECOMMENDATION_CHOICES, blank=True, default=""
    )
    feedback = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_at", "-created_at"]

    def __str__(self):
        return f"{self.get_interview_type_display()} for {self.application.application_number}"


class AdmissionActivityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    action = models.CharField(max_length=50)
    from_status = models.CharField(max_length=30, blank=True, default="")
    to_status = models.CharField(max_length=30, blank=True, default="")
    performed_by = models.ForeignKey(
        "staff.StaffMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.application.application_number} - {self.action} at {self.created_at}"

