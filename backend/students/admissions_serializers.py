import os
from django.db import transaction, IntegrityError, connection
from rest_framework import serializers
from academics.models import AcademicLevel, Section, AcademicYear
from staff.models import StaffMember
from .models import (
    AdmissionEnquiry,
    AdmissionApplication,
    AdmissionDocument,
    AdmissionInterview,
    AdmissionActivityLog,
)
from .admissions_services import (
    generate_enquiry_number,
    generate_application_number,
)

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".doc", ".docx"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".bash", ".php", ".phtml", ".py", ".rb", ".pl",
    ".js", ".mjs", ".ts", ".html", ".htm", ".xhtml", ".svg", ".vbs", ".dll", ".so",
    ".jar", ".war", ".jsp", ".asp", ".aspx", ".cgi",
}


def validate_uploaded_document_file(value):
    """
    Strict server-side validation for public and staff document uploads:
    - Non-empty payload check
    - Strict file size limit (10MB)
    - Path traversal and null byte prevention
    - Whitelist extension matching
    - Double extension / disguised executable prevention
    - File magic byte / content-signature verification
    """
    if not value or value.size == 0:
        raise serializers.ValidationError("The uploaded file is empty.")

    if value.size > MAX_FILE_SIZE_BYTES:
        raise serializers.ValidationError(
            f"File size ({value.size / (1024 * 1024):.1f}MB) exceeds the maximum allowed limit of 10MB."
        )

    filename = getattr(value, "name", "") or ""
    # Path traversal check
    if "/" in filename or "\\" in filename or "\x00" in filename:
        raise serializers.ValidationError("File name contains invalid characters.")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise serializers.ValidationError(
            f"Unsupported file format '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}"
        )

    # Check for dangerous double extensions (e.g., exploit.php.pdf)
    name_parts = filename.lower().split(".")
    for part in name_parts[:-1]:
        if f".{part}" in DANGEROUS_EXTENSIONS:
            raise serializers.ValidationError("File name contains dangerous executable extensions.")

    # Inspect file header (magic bytes)
    pos = value.tell() if hasattr(value, "tell") else 0
    header = value.read(16)
    if hasattr(value, "seek"):
        value.seek(pos)

    if ext == ".pdf":
        if not header.startswith(b"%PDF"):
            raise serializers.ValidationError("Uploaded file is not a valid PDF document.")
    elif ext in {".jpg", ".jpeg"}:
        if not header.startswith(b"\xff\xd8\xff"):
            raise serializers.ValidationError("Uploaded file is not a valid JPEG image.")
    elif ext == ".png":
        if not header.startswith(b"\x89PNG\r\n\x1a\n"):
            raise serializers.ValidationError("Uploaded file is not a valid PNG image.")
    elif ext == ".webp":
        if not (header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP"):
            raise serializers.ValidationError("Uploaded file is not a valid WEBP image.")
    elif ext == ".docx":
        if not header.startswith(b"PK\x03\x04"):
            raise serializers.ValidationError("Uploaded file is not a valid DOCX document.")
    elif ext == ".doc":
        if not header.startswith(b"\xd0\xcf\x11\xe0"):
            raise serializers.ValidationError("Uploaded file is not a valid DOC document.")

    return value


class AdmissionEnquirySerializer(serializers.ModelSerializer):
    preferred_level_name = serializers.CharField(source="preferred_level.name", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = AdmissionEnquiry
        fields = [
            "id",
            "enquiry_number",
            "student_name",
            "date_of_birth",
            "gender",
            "guardian_name",
            "guardian_relationship",
            "guardian_phone",
            "guardian_email",
            "address",
            "previous_school",
            "academic_year",
            "academic_year_ref",
            "preferred_level",
            "preferred_level_name",
            "source",
            "status",
            "assigned_to",
            "assigned_to_name",
            "enquiry_date",
            "follow_up_date",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "enquiry_number", "created_at", "updated_at"]

    def get_assigned_to_name(self, obj):
        if obj.assigned_to and hasattr(obj.assigned_to, "profile"):
            return f"{obj.assigned_to.profile.first_name} {obj.assigned_to.profile.last_name}".strip()
        return None

    def create(self, validated_data):
        if not validated_data.get("enquiry_number"):
            validated_data["enquiry_number"] = generate_enquiry_number()
        return super().create(validated_data)


class AdmissionDocumentSerializer(serializers.ModelSerializer):
    verified_by_name = serializers.SerializerMethodField()
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = AdmissionDocument
        fields = [
            "id",
            "application",
            "document_type",
            "document_type_display",
            "title",
            "file",
            "file_name",
            "verification_status",
            "scan_status",
            "scan_details",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "rejection_reason",
            "uploaded_at",
        ]
        read_only_fields = [
            "id",
            "application",
            "verification_status",
            "scan_status",
            "scan_details",
            "verified_by",
            "verified_at",
            "uploaded_at",
        ]

    def get_verified_by_name(self, obj):
        if obj.verified_by and hasattr(obj.verified_by, "profile"):
            return f"{obj.verified_by.profile.first_name} {obj.verified_by.profile.last_name}".strip()
        return None

    def get_file_name(self, obj):
        if obj.file:
            return os.path.basename(obj.file.name)
        return ""

    def validate_file(self, value):
        if value:
            ext = os.path.splitext(value.name)[1].lower()
            if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
                raise serializers.ValidationError(
                    f"Unsupported file format '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}"
                )
            if value.size > MAX_FILE_SIZE_BYTES:
                raise serializers.ValidationError("File size exceeds maximum allowed limit of 10MB.")
        return value


class AdmissionInterviewSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.SerializerMethodField()
    interview_type_display = serializers.CharField(source="get_interview_type_display", read_only=True)

    class Meta:
        model = AdmissionInterview
        fields = [
            "id",
            "application",
            "interview_type",
            "interview_type_display",
            "scheduled_at",
            "completed_at",
            "interviewer",
            "interviewer_name",
            "status",
            "score",
            "recommendation",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["id", "application", "created_at"]

    def get_interviewer_name(self, obj):
        if obj.interviewer and hasattr(obj.interviewer, "profile"):
            return f"{obj.interviewer.profile.first_name} {obj.interviewer.profile.last_name}".strip()
        return None


class AdmissionActivityLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AdmissionActivityLog
        fields = [
            "id",
            "action",
            "from_status",
            "to_status",
            "performed_by",
            "performed_by_name",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_performed_by_name(self, obj):
        if obj.performed_by and hasattr(obj.performed_by, "profile"):
            return f"{obj.performed_by.profile.first_name} {obj.performed_by.profile.last_name}".strip()
        return None


class AdmissionApplicationListSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    assigned_reviewer_name = serializers.SerializerMethodField()
    student_enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            "id",
            "application_number",
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "date_of_birth",
            "phone",
            "email",
            "guardian_first_name",
            "guardian_last_name",
            "guardian_phone",
            "level",
            "level_name",
            "section",
            "section_name",
            "academic_year",
            "status",
            "submission_date",
            "assigned_reviewer",
            "assigned_reviewer_name",
            "decision_date",
            "enrolled_at",
            "student",
            "student_enrollment_id",
            "created_at",
        ]

    def get_assigned_reviewer_name(self, obj):
        if obj.assigned_reviewer and hasattr(obj.assigned_reviewer, "profile"):
            return f"{obj.assigned_reviewer.profile.first_name} {obj.assigned_reviewer.profile.last_name}".strip()
        return None


class AdmissionApplicationDetailSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    assigned_reviewer_name = serializers.SerializerMethodField()
    decision_by_name = serializers.SerializerMethodField()
    enrolled_by_name = serializers.SerializerMethodField()
    student_enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)
    documents = AdmissionDocumentSerializer(many=True, read_only=True)
    interviews = AdmissionInterviewSerializer(many=True, read_only=True)
    activities = AdmissionActivityLogSerializer(many=True, read_only=True)
    enquiry_number = serializers.CharField(source="enquiry.enquiry_number", read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            "id",
            "application_number",
            "enquiry",
            "enquiry_number",
            "student",
            "student_enrollment_id",
            "first_name",
            "middle_name",
            "last_name",
            "date_of_birth",
            "gender",
            "email",
            "phone",
            "address",
            "previous_school",
            "last_grade_passed",
            "guardian_first_name",
            "guardian_last_name",
            "guardian_relationship",
            "guardian_phone",
            "guardian_email",
            "guardian_occupation",
            "guardian_address",
            "secondary_guardian_name",
            "secondary_guardian_relationship",
            "secondary_guardian_phone",
            "academic_year",
            "academic_year_ref",
            "level",
            "level_name",
            "section",
            "section_name",
            "status",
            "submission_date",
            "assigned_reviewer",
            "assigned_reviewer_name",
            "decision_date",
            "decision_notice_sent_at",
            "documents_reminded_at",
            "decision_reason",
            "decision_by",
            "decision_by_name",
            "enrolled_at",
            "enrolled_by",
            "enrolled_by_name",
            "notes",
            "created_at",
            "updated_at",
            "documents",
            "interviews",
            "activities",
        ]
        read_only_fields = [
            "id",
            "application_number",
            "student",
            "status",
            "submission_date",
            "decision_date",
            "decision_notice_sent_at",
            "documents_reminded_at",
            "decision_by",
            "enrolled_at",
            "enrolled_by",
            "created_at",
            "updated_at",
        ]

    def get_assigned_reviewer_name(self, obj):
        if obj.assigned_reviewer and hasattr(obj.assigned_reviewer, "profile"):
            return f"{obj.assigned_reviewer.profile.first_name} {obj.assigned_reviewer.profile.last_name}".strip()
        return None

    def get_decision_by_name(self, obj):
        if obj.decision_by and hasattr(obj.decision_by, "profile"):
            return f"{obj.decision_by.profile.first_name} {obj.decision_by.profile.last_name}".strip()
        return None

    def get_enrolled_by_name(self, obj):
        if obj.enrolled_by and hasattr(obj.enrolled_by, "profile"):
            return f"{obj.enrolled_by.profile.first_name} {obj.enrolled_by.profile.last_name}".strip()
        return None


class AdmissionApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdmissionApplication
        fields = [
            "id",
            "enquiry",
            "first_name",
            "middle_name",
            "last_name",
            "date_of_birth",
            "gender",
            "email",
            "phone",
            "address",
            "previous_school",
            "last_grade_passed",
            "guardian_first_name",
            "guardian_last_name",
            "guardian_relationship",
            "guardian_phone",
            "guardian_email",
            "guardian_occupation",
            "guardian_address",
            "secondary_guardian_name",
            "secondary_guardian_relationship",
            "secondary_guardian_phone",
            "academic_year",
            "academic_year_ref",
            "level",
            "section",
            "assigned_reviewer",
            "notes",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        validated_data["application_number"] = generate_application_number()
        validated_data["status"] = "draft"
        return super().create(validated_data)


class AdmissionStatusTransitionSerializer(serializers.Serializer):
    status = serializers.CharField(max_length=30)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AdmissionDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approved", "rejected", "waitlisted"])
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs.get("decision") == "rejected" and not attrs.get("reason", "").strip():
            raise serializers.ValidationError({"reason": "A reason is mandatory when rejecting an application."})
        return attrs


class AdmissionEnrollSerializer(serializers.Serializer):
    section_id = serializers.UUIDField(required=False, allow_null=True)


class DocumentRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=True)


# =====================================================================
# Public Self-Service Admissions Serializers
# =====================================================================

import datetime
import hashlib
import secrets
from django.utils import timezone
from notifications.services import queue_email


PUBLIC_STATUS_MAPPING = {
    "draft": {
        "title": "Application Draft",
        "description": "Your application has been drafted and is awaiting submission.",
        "next_steps": "Complete all required fields and submit your application.",
    },
    "submitted": {
        "title": "Application Submitted",
        "description": "We have received your application. It is queued for review by the admissions committee.",
        "next_steps": "The admissions team will inspect your application. Check back here periodically for status updates.",
    },
    "under_review": {
        "title": "Application Under Review",
        "description": "Your application is currently being evaluated by our admissions department.",
        "next_steps": "No action is needed right now. If additional documents or an assessment are required, instructions will appear here.",
    },
    "documents_pending": {
        "title": "Documents Required",
        "description": "Additional or clearer documentation is needed before your application can proceed.",
        "next_steps": "Please upload the requested documents using the upload section below.",
    },
    "documents_verified": {
        "title": "Documents Verified",
        "description": "Your submitted academic and identification documents have been verified.",
        "next_steps": "Your application has moved to final evaluation or assessment scheduling.",
    },
    "assessment_pending": {
        "title": "Assessment / Interaction In Progress",
        "description": "An interaction or assessment has been scheduled as part of the admissions evaluation.",
        "next_steps": "Our admissions office will reach out regarding scheduled timings and instructions.",
    },
    "approved": {
        "title": "Admission Approved / Offer Extended",
        "description": "Congratulations! The school has approved your admission application.",
        "next_steps": "Please contact the school admissions office to complete admission formalities and fee settlement.",
    },
    "waitlisted": {
        "title": "Application Waitlisted",
        "description": "Your application has met our criteria and is currently placed on the admissions waitlist.",
        "next_steps": "You will be notified immediately as seats become available in your requested grade.",
    },
    "rejected": {
        "title": "Application Decision Finalized",
        "description": "Thank you for your interest. Unfortunately, we are unable to offer admission at this time.",
        "next_steps": "For enquiries regarding next academic sessions, please contact our admissions office.",
    },
    "offer_accepted": {
        "title": "Offer Accepted",
        "description": "Your admission acceptance has been confirmed. Student enrollment is in progress.",
        "next_steps": "The school administration is preparing student profile and class section allocation.",
    },
    "enrolled": {
        "title": "Enrolled",
        "description": "The student has been officially registered and enrolled at the institution.",
        "next_steps": "Welcome to the school! Access credentials and timetable details will be provided.",
    },
    "withdrawn": {
        "title": "Application Withdrawn",
        "description": "This application has been withdrawn.",
        "next_steps": "If you wish to re-apply, please submit a new enquiry or application.",
    },
}


class PublicAdmissionEnquiryCreateSerializer(serializers.ModelSerializer):
    consent = serializers.BooleanField(write_only=True, required=True)
    academic_year = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = AdmissionEnquiry
        fields = [
            "student_name",
            "guardian_name",
            "guardian_relationship",
            "guardian_phone",
            "guardian_email",
            "address",
            "previous_school",
            "academic_year",
            "academic_year_ref",
            "preferred_level",
            "notes",
            "consent",
        ]

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Consent to the privacy notice is required.")
        return value

    def validate(self, attrs):
        level = attrs.get("preferred_level")
        if level and hasattr(level, "program") and not level.program.is_active:
            raise serializers.ValidationError({"preferred_level": "The selected academic grade/level is currently not active for admissions."})

        year_ref = attrs.get("academic_year_ref")
        if year_ref:
            attrs["academic_year"] = year_ref.name
        elif not attrs.get("academic_year"):
            # Default to current active academic year
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                attrs["academic_year_ref"] = current_year
                attrs["academic_year"] = current_year.name
            else:
                raise serializers.ValidationError({"academic_year": "Academic year is required."})

        return attrs

    def create(self, validated_data):
        validated_data.pop("consent", None)

        # Check for immediate duplicate enquiry submission within 5 minutes (double-click prevention)
        student_name = (validated_data.get("student_name") or "").strip()
        guardian_phone = (validated_data.get("guardian_phone") or "").strip()
        if student_name and guardian_phone:
            recent_duplicate = (
                AdmissionEnquiry.objects.filter(
                    student_name__iexact=student_name,
                    guardian_phone=guardian_phone,
                    created_at__gte=timezone.now() - datetime.timedelta(minutes=5),
                )
                .order_by("-created_at")
                .first()
            )
            if recent_duplicate:
                return recent_duplicate

        with transaction.atomic():
            for _ in range(3):
                validated_data["enquiry_number"] = generate_enquiry_number()
                validated_data["source"] = "website"
                validated_data["status"] = "new"
                try:
                    enquiry = super().create(validated_data)
                    break
                except IntegrityError:
                    continue
            else:
                validated_data["enquiry_number"] = f"ENQ-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"
                enquiry = super().create(validated_data)

            # Queue safe notification email if guardian email is provided
            if enquiry.guardian_email:
                try:
                    queue_email(
                        to_email=enquiry.guardian_email,
                        subject=f"Admission Enquiry Received — Reference {enquiry.enquiry_number}",
                        body=(
                            f"Dear {enquiry.guardian_name},\n\n"
                            f"Thank you for contacting us regarding admissions for {enquiry.student_name}. "
                            f"Your enquiry has been logged with reference number: {enquiry.enquiry_number}.\n\n"
                            f"Our admissions office will review your enquiry and contact you shortly at {enquiry.guardian_phone}.\n\n"
                            f"Warm regards,\nAdmissions Office"
                        ),
                    )
                except Exception:
                    pass

        return enquiry


class PublicAdmissionApplicationCreateSerializer(serializers.ModelSerializer):
    consent = serializers.BooleanField(write_only=True, required=True)
    academic_year = serializers.CharField(required=False, allow_blank=True)
    enquiry_number = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "date_of_birth",
            "gender",
            "email",
            "phone",
            "address",
            "previous_school",
            "last_grade_passed",
            "guardian_first_name",
            "guardian_last_name",
            "guardian_relationship",
            "guardian_phone",
            "guardian_email",
            "guardian_occupation",
            "guardian_address",
            "secondary_guardian_name",
            "secondary_guardian_relationship",
            "secondary_guardian_phone",
            "academic_year",
            "academic_year_ref",
            "level",
            "consent",
            "enquiry_number",
        ]

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Consent to the admissions policy and privacy terms is required.")
        return value

    def validate_date_of_birth(self, value):
        if value > datetime.date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value

    def validate(self, attrs):
        level = attrs.get("level")
        if level and hasattr(level, "program") and not level.program.is_active:
            raise serializers.ValidationError({"level": "The selected academic grade/level is not active."})

        year_ref = attrs.get("academic_year_ref")
        if year_ref:
            attrs["academic_year"] = year_ref.name
        elif not attrs.get("academic_year"):
            current_year = AcademicYear.objects.filter(is_current=True).first()
            if current_year:
                attrs["academic_year_ref"] = current_year
                attrs["academic_year"] = current_year.name
            else:
                raise serializers.ValidationError({"academic_year": "Academic year is required."})

        # Match optional enquiry only if it is in an active open status
        enq_num = attrs.pop("enquiry_number", None)
        if enq_num:
            enquiry = AdmissionEnquiry.objects.filter(
                enquiry_number=enq_num.strip(),
                status__in=["new", "contacted"],
            ).first()
            if enquiry:
                attrs["enquiry"] = enquiry

        return attrs

    def create(self, validated_data):
        validated_data.pop("consent", None)

        first_name = (validated_data.get("first_name") or "").strip()
        last_name = (validated_data.get("last_name") or "").strip()
        dob = validated_data.get("date_of_birth")
        guardian_phone = (validated_data.get("guardian_phone") or "").strip()
        level = validated_data.get("level")

        with transaction.atomic():
            # Concurrency protection: serialize matching simultaneous submissions via PostgreSQL transaction advisory lock
            if connection.vendor == "postgresql" and first_name and last_name and dob and guardian_phone:
                lock_key = f"{connection.schema_name}:{first_name.lower()}:{last_name.lower()}:{dob}:{guardian_phone}"
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [lock_key])

            # Deduplication safety gate:
            # Reject duplicate submissions without leaking or re-issuing capability tokens.
            # An unauthenticated caller must NEVER receive or reset another applicant's token.
            if first_name and last_name and dob and guardian_phone and level:
                recent_existing = AdmissionApplication.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                    date_of_birth=dob,
                    guardian_phone=guardian_phone,
                    level=level,
                    created_at__gte=timezone.now() - datetime.timedelta(minutes=10),
                ).exists()

                if recent_existing:
                    raise serializers.ValidationError(
                        {
                            "non_field_errors": [
                                "An admission application for this student has already been submitted recently. "
                                "For security and privacy, access credentials cannot be re-issued through this form. "
                                "Please use your saved reference number and access token to check your status. "
                                "If you need assistance or misplaced your credentials, please contact the admissions office."
                            ]
                        }
                    )

            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            validated_data["access_token_hash"] = token_hash
            validated_data["access_token_expires_at"] = timezone.now() + datetime.timedelta(days=90)
            validated_data["status"] = "submitted"
            validated_data["submission_date"] = timezone.now()

            for _ in range(3):
                validated_data["application_number"] = generate_application_number()
                try:
                    app = super().create(validated_data)
                    break
                except IntegrityError:
                    continue
            else:
                validated_data["application_number"] = f"APP-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"
                app = super().create(validated_data)

            # Attach raw token to instance temporarily for the view response
            app._raw_access_token = raw_token

            # Update linked enquiry if present
            if app.enquiry:
                app.enquiry.status = "converted"
                app.enquiry.save(update_fields=["status"])

            # Record activity log
            AdmissionActivityLog.objects.create(
                application=app,
                action="submitted",
                from_status="",
                to_status="submitted",
                notes="Submitted online via public admissions portal.",
            )

            # Queue safe notification email if guardian email provided
            if app.guardian_email:
                try:
                    queue_email(
                        to_email=app.guardian_email,
                        subject=f"Admission Application Submitted — {app.application_number}",
                        body=(
                            f"Dear {app.guardian_first_name} {app.guardian_last_name},\n\n"
                            f"Your admission application for {app.first_name} {app.last_name} has been successfully submitted.\n\n"
                            f"Application Reference Number: {app.application_number}\n\n"
                            f"Please save this reference number. You can check the status of your application and upload required documents online anytime.\n\n"
                            f"Warm regards,\nAdmissions Committee"
                        ),
                    )
                except Exception:
                    pass

            return app


class PublicDocumentItemSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    file_name = serializers.SerializerMethodField()
    rejection_reason = serializers.SerializerMethodField()

    class Meta:
        model = AdmissionDocument
        fields = [
            "id",
            "document_type",
            "document_type_display",
            "title",
            "file_name",
            "verification_status",
            "scan_status",
            "rejection_reason",
            "uploaded_at",
        ]

    def get_file_name(self, obj):
        if obj.file:
            return os.path.basename(obj.file.name)
        return ""

    def get_rejection_reason(self, obj):
        # Only expose rejection notes when the document was explicitly rejected
        if obj.verification_status == "rejected":
            return (obj.rejection_reason or "").strip()
        return None


class PublicApplicationStatusSerializer(serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()
    status_description = serializers.SerializerMethodField()
    next_steps = serializers.SerializerMethodField()
    level_name = serializers.CharField(source="level.name", read_only=True)
    student_masked_name = serializers.SerializerMethodField()
    can_upload_documents = serializers.SerializerMethodField()
    documents = PublicDocumentItemSerializer(many=True, read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            "application_number",
            "submission_date",
            "first_name",
            "student_masked_name",
            "level_name",
            "academic_year",
            "status",
            "status_display",
            "status_description",
            "next_steps",
            "can_upload_documents",
            "documents",
        ]

    def get_status_display(self, obj):
        mapping = PUBLIC_STATUS_MAPPING.get(obj.status)
        return mapping["title"] if mapping else obj.get_status_display()

    def get_status_description(self, obj):
        mapping = PUBLIC_STATUS_MAPPING.get(obj.status)
        return mapping["description"] if mapping else ""

    def get_next_steps(self, obj):
        mapping = PUBLIC_STATUS_MAPPING.get(obj.status)
        return mapping["next_steps"] if mapping else ""

    def get_student_masked_name(self, obj):
        # Mask surname for applicant privacy e.g. "Aarav S****a"
        first = (obj.first_name or "").strip()
        last = (obj.last_name or "").strip()
        if not last:
            return first

        if len(last) > 2:
            masked_last = f"{last[0]}{'*' * (len(last) - 2)}{last[-1]}"
        elif len(last) == 2:
            masked_last = f"{last[0]}*"
        else:
            masked_last = last

        return f"{first} {masked_last}".strip()

    def get_can_upload_documents(self, obj):
        # Allow uploads strictly while application is in initial review stages
        return obj.status in ["draft", "submitted", "under_review", "documents_pending"]


class PublicAdmissionDocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdmissionDocument
        fields = [
            "document_type",
            "title",
            "file",
        ]

    def validate_title(self, value):
        if value:
            # Strip excessive whitespace and control characters
            clean = " ".join(value.strip().split())
            if len(clean) > 200:
                clean = clean[:200]
            return clean
        return value

    def validate_file(self, value):
        return validate_uploaded_document_file(value)


