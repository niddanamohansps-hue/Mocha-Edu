import hashlib
import mimetypes
import os
import posixpath
import secrets
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_tenants.utils import get_public_schema_name
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.audit import log_action
from core.pagination import StandardResultsPagination
from academics.models import AcademicYear, AcademicLevel
from roles.permissions import HasPermission
from staff.models import StaffMember
from .models import (
    AdmissionEnquiry,
    AdmissionApplication,
    AdmissionDocument,
    AdmissionInterview,
    AdmissionActivityLog,
    DOCUMENT_TYPE_CHOICES,
)
from .admissions_serializers import (
    AdmissionEnquirySerializer,
    AdmissionApplicationListSerializer,
    AdmissionApplicationDetailSerializer,
    AdmissionApplicationCreateSerializer,
    AdmissionDocumentSerializer,
    AdmissionInterviewSerializer,
    AdmissionStatusTransitionSerializer,
    AdmissionDecisionSerializer,
    AdmissionEnrollSerializer,
    DocumentRejectSerializer,
    PublicAdmissionEnquiryCreateSerializer,
    PublicAdmissionApplicationCreateSerializer,
    PublicApplicationStatusSerializer,
    PublicAdmissionDocumentUploadSerializer,
    ALLOWED_DOCUMENT_EXTENSIONS,
)
from .admissions_services import (
    transition_application_status,
    enroll_application_as_student,
    convert_enquiry_to_application,
    get_admissions_dashboard_stats,
    rotate_application_access_token,
    revoke_application_access_token,
)
from .services import get_staff_member_for_user
from .admissions_tasks import scan_admission_document_task


class AdmissionDashboardStatsView(APIView):
    """
    Returns aggregated metrics and pipeline status counts for admissions.
    """
    permission_classes = [IsAuthenticated, HasPermission("view_admissions")]

    def get(self, request):
        stats = get_admissions_dashboard_stats()
        return Response(stats, status=status.HTTP_200_OK)


class AdmissionEnquiryListView(APIView):
    """
    List, search, filter, and create admission enquiries.
    """
    permission_classes = [IsAuthenticated, HasPermission("view_admissions")]
    pagination_class = StandardResultsPagination

    def get(self, request):
        queryset = AdmissionEnquiry.objects.select_related(
            "preferred_level", "academic_year_ref", "assigned_to__profile"
        ).order_by("-enquiry_date", "-created_at")

        status_param = request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        academic_year = request.query_params.get("academic_year")
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)

        level_id = request.query_params.get("level")
        if level_id:
            queryset = queryset.filter(preferred_level_id=level_id)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(student_name__icontains=search)
                | Q(guardian_name__icontains=search)
                | Q(guardian_phone__icontains=search)
                | Q(enquiry_number__icontains=search)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdmissionEnquirySerializer(page or queryset, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def post(self, request):
        if not HasPermission("manage_admission_enquiries")().has_permission(request, self):
            return Response(
                {"error": "You do not have permission to create admission enquiries."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AdmissionEnquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enquiry = serializer.save()

        log_action(
            request,
            action="CREATE",
            model_name="AdmissionEnquiry",
            object_id=enquiry.id,
            changes={"enquiry_number": enquiry.enquiry_number, "student_name": enquiry.student_name},
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdmissionEnquiryDetailView(APIView):
    """
    Retrieve, update, or delete a specific admission enquiry.
    """
    permission_classes = [IsAuthenticated, HasPermission("view_admissions")]

    def get(self, request, pk):
        enquiry = get_object_or_404(
            AdmissionEnquiry.objects.select_related(
                "preferred_level", "academic_year_ref", "assigned_to__profile"
            ),
            pk=pk,
        )
        serializer = AdmissionEnquirySerializer(enquiry)
        return Response(serializer.data)

    def patch(self, request, pk):
        enquiry = get_object_or_404(AdmissionEnquiry, pk=pk)
        serializer = AdmissionEnquirySerializer(enquiry, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_action(
            request,
            action="CHANGE",
            model_name="AdmissionEnquiry",
            object_id=updated.id,
            changes=request.data,
        )

        return Response(serializer.data)

    def delete(self, request, pk):
        enquiry = get_object_or_404(AdmissionEnquiry, pk=pk)
        log_action(
            request,
            action="DELETE",
            model_name="AdmissionEnquiry",
            object_id=enquiry.id,
            changes={"enquiry_number": enquiry.enquiry_number},
        )
        enquiry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdmissionEnquiryConvertView(APIView):
    """
    Converts an enquiry into an active draft AdmissionApplication.
    """
    permission_classes = [IsAuthenticated, HasPermission("manage_admission_applications")]

    def post(self, request, pk):
        application = convert_enquiry_to_application(pk, user=request.user, request=request)
        serializer = AdmissionApplicationDetailSerializer(application)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdmissionApplicationListView(APIView):
    """
    List and create admission applications.
    """
    permission_classes = [IsAuthenticated, HasPermission("view_admissions")]
    pagination_class = StandardResultsPagination

    def get(self, request):
        queryset = AdmissionApplication.objects.select_related(
            "level", "section", "academic_year_ref", "assigned_reviewer__profile", "student"
        ).order_by("-created_at")

        status_param = request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        academic_year = request.query_params.get("academic_year")
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)

        level_id = request.query_params.get("level")
        if level_id:
            queryset = queryset.filter(level_id=level_id)

        reviewer_id = request.query_params.get("reviewer")
        if reviewer_id:
            queryset = queryset.filter(assigned_reviewer_id=reviewer_id)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(application_number__icontains=search)
                | Q(phone__icontains=search)
                | Q(guardian_phone__icontains=search)
                | Q(guardian_first_name__icontains=search)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdmissionApplicationListSerializer(page or queryset, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def post(self, request):
        serializer = AdmissionApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()

        staff_member = get_staff_member_for_user(request.user)
        AdmissionActivityLog.objects.create(
            application=application,
            action="created",
            from_status="",
            to_status="draft",
            performed_by=staff_member,
            notes="Application initiated",
        )

        log_action(
            request,
            action="CREATE",
            model_name="AdmissionApplication",
            object_id=application.id,
            changes={"application_number": application.application_number},
        )

        detail_serializer = AdmissionApplicationDetailSerializer(application)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class AdmissionApplicationDetailView(APIView):
    """
    Retrieve or update an admission application.
    """
    permission_classes = [IsAuthenticated, HasPermission("view_admissions")]

    def get(self, request, pk):
        application = get_object_or_404(
            AdmissionApplication.objects.select_related(
                "level",
                "section",
                "academic_year_ref",
                "assigned_reviewer__profile",
                "decision_by__profile",
                "enrolled_by__profile",
                "student",
                "enquiry",
            ).prefetch_related(
                "documents__verified_by__profile",
                "interviews__interviewer__profile",
                "activities__performed_by__profile",
            ),
            pk=pk,
        )
        serializer = AdmissionApplicationDetailSerializer(application)
        return Response(serializer.data)

    def patch(self, request, pk):
        application = get_object_or_404(AdmissionApplication, pk=pk)
        if application.status == "enrolled":
            return Response(
                {"error": "Cannot edit an already enrolled application."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AdmissionApplicationCreateSerializer(application, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_action(
            request,
            action="CHANGE",
            model_name="AdmissionApplication",
            object_id=updated.id,
            changes=request.data,
        )

        detail_serializer = AdmissionApplicationDetailSerializer(updated)
        return Response(detail_serializer.data)


class AdmissionApplicationStatusView(APIView):
    """
    Transitions the application status through the lifecycle state machine.
    """
    permission_classes = [IsAuthenticated, HasPermission("manage_admission_applications")]

    def post(self, request, pk):
        application = get_object_or_404(AdmissionApplication, pk=pk)
        serializer = AdmissionStatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]
        notes = serializer.validated_data.get("notes", "")
        reason = serializer.validated_data.get("reason", "")

        # If transition is a decision action (approved/rejected/waitlisted), require make_admission_decisions
        if new_status in ["approved", "rejected", "waitlisted"]:
            if not HasPermission("make_admission_decisions")().has_permission(request, self):
                return Response(
                    {"error": "You do not have permission to make admission decisions."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        updated_app = transition_application_status(
            application=application,
            new_status=new_status,
            user=request.user,
            notes=notes,
            reason=reason,
            request=request,
        )

        detail_serializer = AdmissionApplicationDetailSerializer(updated_app)
        return Response(detail_serializer.data, status=status.HTTP_200_OK)


class AdmissionApplicationAssignView(APIView):
    """
    Assigns an admissions staff member or instructor as the reviewer.
    """
    permission_classes = [IsAuthenticated, HasPermission("manage_admission_applications")]

    def post(self, request, pk):
        application = get_object_or_404(AdmissionApplication, pk=pk)
        staff_id = request.data.get("staff_id")
        reviewer = None
        if staff_id:
            reviewer = get_object_or_404(StaffMember, pk=staff_id)

        old_reviewer = str(application.assigned_reviewer_id) if application.assigned_reviewer else None
        application.assigned_reviewer = reviewer
        application.save()

        staff_member = get_staff_member_for_user(request.user)
        rev_name = f"{reviewer.profile.first_name} {reviewer.profile.last_name}" if reviewer else "None"
        AdmissionActivityLog.objects.create(
            application=application,
            action="reviewer_assigned",
            performed_by=staff_member,
            notes=f"Assigned reviewer: {rev_name}",
        )

        log_action(
            request,
            action="CHANGE",
            model_name="AdmissionApplication",
            object_id=application.id,
            changes={"assigned_reviewer": {"old": old_reviewer, "new": str(reviewer.id) if reviewer else None}},
        )

        detail_serializer = AdmissionApplicationDetailSerializer(application)
        return Response(detail_serializer.data, status=status.HTTP_200_OK)


class AdmissionApplicationDecisionView(APIView):
    """
    Records an official admission decision: approve, reject, or waitlist.
    """
    permission_classes = [IsAuthenticated, HasPermission("make_admission_decisions")]

    def post(self, request, pk):
        application = get_object_or_404(AdmissionApplication, pk=pk)
        serializer = AdmissionDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        decision = serializer.validated_data["decision"]
        reason = serializer.validated_data.get("reason", "")
        notes = serializer.validated_data.get("notes", "")

        updated_app = transition_application_status(
            application=application,
            new_status=decision,
            user=request.user,
            notes=notes,
            reason=reason,
            request=request,
        )

        detail_serializer = AdmissionApplicationDetailSerializer(updated_app)
        return Response(detail_serializer.data, status=status.HTTP_200_OK)


class AdmissionApplicationEnrollView(APIView):
    """
    Converts an approved or offer-accepted application into an active Student record.
    """
    permission_classes = [IsAuthenticated, HasPermission("enroll_admitted_students")]

    def post(self, request, pk):
        serializer = AdmissionEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section_id = serializer.validated_data.get("section_id")

        student = enroll_application_as_student(
            application_id=pk,
            user=request.user,
            section_id=section_id,
            request=request,
        )

        application = AdmissionApplication.objects.get(pk=pk)
        detail_serializer = AdmissionApplicationDetailSerializer(application)
        return Response(
            {
                "message": "Applicant successfully enrolled as student.",
                "student_id": str(student.id),
                "enrollment_id": student.enrollment_id,
                "application": detail_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class AdmissionDocumentUploadView(APIView):
    """
    Upload a document attachment for an admission application.
    """
    permission_classes = [IsAuthenticated, HasPermission("manage_admission_applications")]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        application = get_object_or_404(AdmissionApplication, pk=pk)
        serializer = AdmissionDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(application=application)

        staff_member = get_staff_member_for_user(request.user)
        AdmissionActivityLog.objects.create(
            application=application,
            action="document_uploaded",
            performed_by=staff_member,
            notes=f"Uploaded document: {document.get_document_type_display()} - {document.title}",
        )

        log_action(
            request,
            action="CREATE",
            model_name="AdmissionDocument",
            object_id=document.id,
            changes={"title": document.title, "document_type": document.document_type},
        )

        # Trigger asynchronous fail-closed antivirus scan
        schema_name = connection.schema_name
        doc_id = str(document.id)
        transaction.on_commit(lambda: scan_admission_document_task.delay(schema_name, doc_id))

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdmissionDocumentVerifyView(APIView):
    """
    Marks a document as verified.
    """
    permission_classes = [IsAuthenticated, HasPermission("review_admission_documents")]

    def post(self, request, pk):
        document = get_object_or_404(AdmissionDocument.objects.select_related("application"), pk=pk)

        # Antivirus quarantine gate: uninspected or infected documents cannot be verified
        if document.scan_status != "clean":
            return Response(
                {
                    "error": (
                        f"Cannot verify document: antivirus inspection state is '{document.get_scan_status_display()}'. "
                        "Only documents that have successfully passed malware inspection can be verified."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        staff_member = get_staff_member_for_user(request.user)

        document.verification_status = "verified"
        document.verified_by = staff_member
        document.verified_at = timezone.now()
        document.rejection_reason = ""
        document.save()

        AdmissionActivityLog.objects.create(
            application=document.application,
            action="document_verified",
            performed_by=staff_member,
            notes=f"Verified {document.get_document_type_display()} ({document.title})",
        )

        log_action(
            request,
            action="CHANGE",
            model_name="AdmissionDocument",
            object_id=document.id,
            changes={"verification_status": "verified"},
        )

        serializer = AdmissionDocumentSerializer(document)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdmissionDocumentRejectView(APIView):
    """
    Rejects a document and records mandatory rejection reason.
    """
    permission_classes = [IsAuthenticated, HasPermission("review_admission_documents")]

    def post(self, request, pk):
        document = get_object_or_404(AdmissionDocument.objects.select_related("application"), pk=pk)
        serializer = DocumentRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        staff_member = get_staff_member_for_user(request.user)
        document.verification_status = "rejected"
        document.verified_by = staff_member
        document.verified_at = timezone.now()
        document.rejection_reason = reason
        document.save()

        AdmissionActivityLog.objects.create(
            application=document.application,
            action="document_rejected",
            performed_by=staff_member,
            notes=f"Rejected {document.get_document_type_display()}: {reason}",
        )

        log_action(
            request,
            action="CHANGE",
            model_name="AdmissionDocument",
            object_id=document.id,
            changes={"verification_status": "rejected", "rejection_reason": reason},
        )

        doc_serializer = AdmissionDocumentSerializer(document)
        return Response(doc_serializer.data, status=status.HTTP_200_OK)


class AdmissionDocumentDownloadView(APIView):
    """
    Secured file download endpoint. Enforces:
    - Staff authorization: Authenticated user with 'view_admissions' permission.
    - Applicant authorization: Matching capability token via X-Application-Token header.
    - Quarantine verification: Scan status must be 'clean'.
    - Optional X-Accel-Redirect accelerated delivery.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        document = get_object_or_404(AdmissionDocument.objects.select_related("application"), pk=pk)

        # 1. Check staff authorization
        is_authorized = False
        is_staff_user = bool(request.user and request.user.is_authenticated)

        if is_staff_user:
            if HasPermission("view_admissions")().has_permission(request, self):
                is_authorized = True

        # 2. Check applicant capability token authorization
        token = request.headers.get("X-Application-Token", "").strip()
        if not token:
            token = request.query_params.get("token", "").strip()

        token_provided = bool(token)
        token_valid = False

        if token and document.application and document.application.access_token_hash:
            provided_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if secrets.compare_digest(document.application.access_token_hash, provided_hash):
                if not (document.application.access_token_expires_at and timezone.now() > document.application.access_token_expires_at):
                    token_valid = True
                    is_authorized = True
        else:
            hashlib.sha256(token.encode("utf-8") if token else b"").hexdigest()

        if not is_authorized:
            # If user is staff without permissions, return 403 Forbidden
            if is_staff_user and not token_valid:
                return Response(
                    {"error": "You do not have permission to access admission documents."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # If token was supplied but invalid/expired, return uniform 404 to resist enumeration
            if token_provided:
                return Response(
                    {"error": "Document not found or access credentials invalid."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            # If no authentication or token was supplied, return 401 Unauthorized
            return Response(
                {"error": "Authentication required. Please log in or provide a valid capability token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not document.file:
            raise Http404("Document file not found.")

        # Fail-closed quarantine gate: uninspected, infected, or error files cannot be downloaded
        if document.scan_status != "clean":
            return Response(
                {
                    "error": (
                        f"Document download blocked: file is quarantined with scan status '{document.get_scan_status_display()}'. "
                        "Access is prohibited until malware inspection passes cleanly."
                    )
                },
                status=status.HTTP_423_LOCKED,
            )

        filename = os.path.basename(document.file.name)
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

        # Check if reverse-proxy accelerated delivery (X-Accel-Redirect) is enabled
        use_x_accel = getattr(settings, "USE_X_ACCEL_REDIRECT", False)
        if use_x_accel:
            x_accel_prefix = getattr(settings, "X_ACCEL_PREFIX", "/protected_media/").rstrip("/") + "/"
            rel_name = posixpath.normpath(str(document.file.name)).lstrip("/")
            if ".." in rel_name.split("/") or rel_name.startswith("/"):
                raise Http404("Invalid file path.")

            internal_path = f"{x_accel_prefix}{rel_name}"
            response = HttpResponse(content_type=content_type)
            response["X-Accel-Redirect"] = internal_path
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response["Content-Security-Policy"] = "default-src 'none'; sandbox"
            return response

        try:
            file_handle = document.file.open("rb")
        except (FileNotFoundError, OSError):
            raise Http404("File not found on storage.")

        response = FileResponse(file_handle, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response


class AdmissionInterviewListCreateView(APIView):
    """
    List or schedule an assessment / interview for an application.
    """
    permission_classes = [IsAuthenticated, HasPermission("review_admission_applications")]

    def post(self, request, pk):
        application = get_object_or_404(AdmissionApplication, pk=pk)
        serializer = AdmissionInterviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        interview = serializer.save(application=application)

        staff_member = get_staff_member_for_user(request.user)
        AdmissionActivityLog.objects.create(
            application=application,
            action="interview_scheduled",
            performed_by=staff_member,
            notes=f"Scheduled {interview.get_interview_type_display()}",
        )

        log_action(
            request,
            action="CREATE",
            model_name="AdmissionInterview",
            object_id=interview.id,
            changes={"interview_type": interview.interview_type},
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdmissionInterviewDetailView(APIView):
    """
    Update results, recommendation, feedback for an interview / assessment.
    """
    permission_classes = [IsAuthenticated, HasPermission("review_admission_applications")]

    def patch(self, request, pk):
        interview = get_object_or_404(AdmissionInterview.objects.select_related("application"), pk=pk)
        serializer = AdmissionInterviewSerializer(interview, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        if updated.status == "completed" and not updated.completed_at:
            updated.completed_at = timezone.now()
            updated.save()

        staff_member = get_staff_member_for_user(request.user)
        AdmissionActivityLog.objects.create(
            application=interview.application,
            action="interview_evaluated",
            performed_by=staff_member,
            notes=f"Updated interview result: {updated.recommendation or updated.status}",
        )

        log_action(
            request,
            action="CHANGE",
            model_name="AdmissionInterview",
            object_id=updated.id,
            changes=request.data,
        )

        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================================
# Public Self-Service Admissions Views
# =====================================================================

class PublicAdmissionsInfoView(APIView):
    """
    Returns public admissions metadata for the resolved tenant:
    - Institution branding (name, contact info)
    - Available active academic years
    - Available active academic levels/grades
    - Required documents and upload specifications
    - Admission instructions
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_admissions_info"

    def get(self, request):
        if connection.schema_name == get_public_schema_name():
            return Response(
                {"error": "Public admissions are only available on individual school domains."},
                status=status.HTTP_404_NOT_FOUND,
            )

        tenant = getattr(request, "tenant", None)
        institution_info = {
            "name": tenant.name if tenant else "EduSekai Partner School",
            "address": getattr(tenant, "address", ""),
            "phone": getattr(tenant, "phone", ""),
            "email": getattr(tenant, "email", ""),
        }

        years = [
            {
                "id": str(y.id),
                "name": y.name,
                "is_current": y.is_current,
                "start_date": y.start_date.isoformat(),
                "end_date": y.end_date.isoformat(),
            }
            for y in AcademicYear.objects.all().order_by("-start_date")
        ]

        levels = [
            {
                "id": str(lvl.id),
                "name": lvl.name,
                "program_name": lvl.program.name,
                "program_code": lvl.program.code,
                "order": lvl.order,
            }
            for lvl in AcademicLevel.objects.filter(program__is_active=True).select_related("program").order_by("order")
        ]

        document_requirements = [
            {
                "document_type": "birth_certificate",
                "label": "Birth Certificate",
                "description": "Official birth certificate or proof of age issued by local civil authority.",
                "required": True,
            },
            {
                "document_type": "previous_marksheet",
                "label": "Previous Grade Marksheet / Report Card",
                "description": "Latest academic report card or marksheet from the previous school.",
                "required": True,
            },
            {
                "document_type": "transfer_certificate",
                "label": "Transfer Certificate (TC)",
                "description": "School Leaving Certificate / Transfer Certificate (if applicable).",
                "required": False,
            },
            {
                "document_type": "photo",
                "label": "Student Passport Photograph",
                "description": "Recent passport-sized colour photograph of the student.",
                "required": True,
            },
            {
                "document_type": "address_proof",
                "label": "Proof of Address",
                "description": "Utility bill, parent identification, or residential proof.",
                "required": False,
            },
            {
                "document_type": "medical_record",
                "label": "Immunization / Medical Record",
                "description": "Blood group and immunization records.",
                "required": False,
            },
        ]

        resp = Response(
            {
                "institution": institution_info,
                "academic_years": years,
                "levels": levels,
                "document_requirements": document_requirements,
                "upload_policy": {
                    "max_file_size_mb": 10,
                    "allowed_extensions": sorted(list(ALLOWED_DOCUMENT_EXTENSIONS)),
                },
                "instructions": (
                    "Please fill out the application form with accurate prospective student and guardian details. "
                    "Upon submission, you will receive a reference number and a private access token. "
                    "Keep your access token safe as it is required to track your application status and upload documents."
                ),
            },
            status=status.HTTP_200_OK,
        )
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        return resp


class PublicAdmissionEnquiryCreateView(APIView):
    """
    Submits a prospective student enquiry without staff authentication.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_admissions_enquiry"

    def post(self, request):
        if connection.schema_name == get_public_schema_name():
            return Response(
                {"error": "Public admissions are only available on individual school domains."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PublicAdmissionEnquiryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enquiry = serializer.save()

        return Response(
            {
                "success": True,
                "enquiry_number": enquiry.enquiry_number,
                "enquiry_date": enquiry.enquiry_date.isoformat(),
                "message": (
                    f"Thank you! Your enquiry has been received under reference {enquiry.enquiry_number}. "
                    "Our admissions office will reach out shortly."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class PublicAdmissionApplicationCreateView(APIView):
    """
    Submits a new admission application without staff authentication.
    Returns the reference number and high-entropy capability token for future status checks.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_admissions_apply"

    def post(self, request):
        if connection.schema_name == get_public_schema_name():
            return Response(
                {"error": "Public admissions are only available on individual school domains."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PublicAdmissionApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        app = serializer.save()

        raw_token = getattr(app, "_raw_access_token", "")

        resp = Response(
            {
                "success": True,
                "application_number": app.application_number,
                "access_token": raw_token,
                "access_token_expires_at": app.access_token_expires_at.isoformat() if app.access_token_expires_at else None,
                "submission_date": app.submission_date.isoformat() if app.submission_date else None,
                "status": app.status,
                "message": (
                    f"Application {app.application_number} submitted successfully! "
                    "Please save your reference number and access token to check application status and upload documents."
                ),
            },
            status=status.HTTP_201_CREATED,
        )
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        return resp


class PublicApplicationStatusView(APIView):
    """
    Retrieves safe applicant-facing status information.
    Requires the matching secret capability token for authorization.
    Uniform 404 response eliminates application enumeration attacks.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_admissions_status"

    def get(self, request, application_number):
        if connection.schema_name == get_public_schema_name():
            return Response(
                {"error": "Public admissions are only available on individual school domains."},
                status=status.HTTP_404_NOT_FOUND,
            )

        token = request.headers.get("X-Application-Token", "").strip()
        if not token:
            # Fall back to legacy query parameter if header missing
            token = request.query_params.get("token", "").strip()

        if not token:
            return Response(
                {"error": "Access token is required. Please provide it via X-Application-Token header."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        app = AdmissionApplication.objects.filter(application_number=application_number).first()

        is_valid = False
        if app and app.access_token_hash:
            provided_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if secrets.compare_digest(app.access_token_hash, provided_hash):
                if not (app.access_token_expires_at and timezone.now() > app.access_token_expires_at):
                    is_valid = True
        else:
            # Constant-time dummy computation to resist timing analysis
            hashlib.sha256(token.encode("utf-8")).hexdigest()

        # Return uniform 404 to prevent application enumeration
        if not is_valid:
            resp = Response(
                {"error": "Application not found or access credentials invalid."},
                status=status.HTTP_404_NOT_FOUND,
            )
            resp["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            resp["Pragma"] = "no-cache"
            return resp

        serializer = PublicApplicationStatusSerializer(app)
        resp = Response(serializer.data, status=status.HTTP_200_OK)
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        resp["Pragma"] = "no-cache"
        return resp


class PublicAdmissionDocumentUploadView(APIView):
    """
    Uploads a verification document for an existing application using its capability token.
    Uniform 404 response prevents application enumeration.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_admissions_upload"

    def post(self, request, application_number):
        if connection.schema_name == get_public_schema_name():
            return Response(
                {"error": "Public admissions are only available on individual school domains."},
                status=status.HTTP_404_NOT_FOUND,
            )

        token = request.headers.get("X-Application-Token", "").strip()
        if not token:
            token = (request.query_params.get("token") or request.data.get("token", "")).strip()

        if not token:
            return Response(
                {"error": "Access token is required for document upload."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        with transaction.atomic():
            app = (
                AdmissionApplication.objects.select_for_update()
                .filter(application_number=application_number)
                .first()
            )

            is_valid = False
            if app and app.access_token_hash:
                provided_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                if secrets.compare_digest(app.access_token_hash, provided_hash):
                    if not (app.access_token_expires_at and timezone.now() > app.access_token_expires_at):
                        is_valid = True
            else:
                hashlib.sha256(token.encode("utf-8")).hexdigest()

            if not is_valid:
                return Response(
                    {"error": "Application not found or access credentials invalid."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if app.status not in ["draft", "submitted", "under_review", "documents_pending"]:
                return Response(
                    {"error": f"Cannot upload documents when application is in '{app.get_status_display()}' status."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = PublicAdmissionDocumentUploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            doc_type = serializer.validated_data["document_type"]
            title = serializer.validated_data.get("title") or dict(DOCUMENT_TYPE_CHOICES).get(doc_type, doc_type)
            file_obj = serializer.validated_data["file"]

            doc = AdmissionDocument.objects.create(
                application=app,
                document_type=doc_type,
                title=title,
                file=file_obj,
                verification_status="pending",
                scan_status="pending",
            )

            AdmissionActivityLog.objects.create(
                application=app,
                action="document_uploaded",
                notes=f"Document '{doc.title}' uploaded via public portal.",
            )

            # Queue asynchronous fail-closed antivirus scan
            schema_name = connection.schema_name
            doc_id = str(doc.id)
            transaction.on_commit(lambda: scan_admission_document_task.delay(schema_name, doc_id))

            resp = Response(
                {
                    "success": True,
                    "document_id": str(doc.id),
                    "document_type": doc.document_type,
                    "title": doc.title,
                    "file_name": os.path.basename(doc.file.name) if doc.file else "",
                    "verification_status": doc.verification_status,
                    "scan_status": doc.scan_status,
                    "uploaded_at": doc.uploaded_at.isoformat(),
                    "message": f"Document '{doc.title}' uploaded successfully and is pending verification.",
                },
                status=status.HTTP_201_CREATED,
            )
            resp["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            return resp


class PublicApplicationTokenRotateView(APIView):
    """
    Self-service rotation endpoint for applicant capability tokens.
    Requires current valid token via X-Application-Token header.
    Invalidates the old token and returns a fresh high-entropy capability token.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_admissions_rotate"

    def post(self, request, application_number):
        if connection.schema_name == get_public_schema_name():
            return Response(
                {"error": "Public admissions are only available on individual school domains."},
                status=status.HTTP_404_NOT_FOUND,
            )

        token = request.headers.get("X-Application-Token", "").strip()
        if not token:
            token = request.data.get("token", "").strip()

        if not token:
            return Response(
                {"error": "Current access token is required to authorize token rotation."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        with transaction.atomic():
            app = (
                AdmissionApplication.objects.select_for_update()
                .filter(application_number=application_number)
                .first()
            )

            is_valid = False
            if app and app.access_token_hash:
                provided_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
                if secrets.compare_digest(app.access_token_hash, provided_hash):
                    if not (app.access_token_expires_at and timezone.now() > app.access_token_expires_at):
                        is_valid = True
            else:
                hashlib.sha256(token.encode("utf-8")).hexdigest()

            if not is_valid:
                return Response(
                    {"error": "Application not found or access credentials invalid."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            new_raw_token = rotate_application_access_token(
                app, reason="Rotated via public self-service admissions portal."
            )

            resp = Response(
                {
                    "success": True,
                    "application_number": app.application_number,
                    "access_token": new_raw_token,
                    "access_token_expires_at": app.access_token_expires_at.isoformat(),
                    "message": "Access token has been rotated successfully. Your previous token is now invalid.",
                },
                status=status.HTTP_200_OK,
            )
            resp["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            return resp


class AdmissionApplicationTokenRotateView(APIView):
    """
    Staff-authorized token rotation endpoint.
    Used when a parent reports a lost or compromised capability token.
    """
    permission_classes = [IsAuthenticated, HasPermission("review_admission_applications")]

    def post(self, request, pk):
        app = get_object_or_404(AdmissionApplication, pk=pk)
        reason = request.data.get("reason", "Rotated by admissions staff.")
        new_token = rotate_application_access_token(app, user=request.user, reason=reason)

        return Response(
            {
                "success": True,
                "application_number": app.application_number,
                "access_token": new_token,
                "access_token_expires_at": app.access_token_expires_at.isoformat(),
                "message": f"Access token for application {app.application_number} was rotated successfully.",
            },
            status=status.HTTP_200_OK,
        )


class AdmissionApplicationTokenRevokeView(APIView):
    """
    Staff-authorized token revocation endpoint.
    Immediately closes public self-service access for this application.
    """
    permission_classes = [IsAuthenticated, HasPermission("review_admission_applications")]

    def post(self, request, pk):
        app = get_object_or_404(AdmissionApplication, pk=pk)
        reason = request.data.get("reason", "Revoked by admissions staff.")
        revoke_application_access_token(app, user=request.user, reason=reason)

        return Response(
            {
                "success": True,
                "application_number": app.application_number,
                "message": f"Access token for application {app.application_number} has been revoked.",
            },
            status=status.HTTP_200_OK,
        )


class PublicAdmissionDocumentDownloadView(APIView):
    """
    Applicant self-service download endpoint for admission documents.
    Requires matching secret capability token for authorization.
    Uniform 404 response eliminates document and application enumeration attacks.
    Enforces fail-closed quarantine: only clean documents can be downloaded.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_admissions_status"

    def get(self, request, application_number, document_id):
        if connection.schema_name == get_public_schema_name():
            return Response(
                {"error": "Public admissions are only available on individual school domains."},
                status=status.HTTP_404_NOT_FOUND,
            )

        token = request.headers.get("X-Application-Token", "").strip()
        if not token:
            token = request.query_params.get("token", "").strip()

        if not token:
            return Response(
                {"error": "Access token is required. Please provide it via X-Application-Token header."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        app = AdmissionApplication.objects.filter(application_number=application_number).first()
        document = (
            AdmissionDocument.objects.filter(id=document_id, application__application_number=application_number)
            .select_related("application")
            .first()
        )

        is_valid = False
        if app and document and app.access_token_hash:
            provided_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if secrets.compare_digest(app.access_token_hash, provided_hash):
                if not (app.access_token_expires_at and timezone.now() > app.access_token_expires_at):
                    is_valid = True
        else:
            hashlib.sha256(token.encode("utf-8") if token else b"").hexdigest()

        if not is_valid or not document:
            resp = Response(
                {"error": "Application or document not found or access credentials invalid."},
                status=status.HTTP_404_NOT_FOUND,
            )
            resp["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            return resp

        # Fail-closed quarantine check
        if document.scan_status != "clean":
            return Response(
                {
                    "error": (
                        f"Document download blocked: file is quarantined with scan status '{document.get_scan_status_display()}'. "
                        "Access is prohibited until malware inspection passes cleanly."
                    )
                },
                status=status.HTTP_423_LOCKED,
            )

        if not document.file:
            raise Http404("Document file not found.")

        filename = os.path.basename(document.file.name)
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

        use_x_accel = getattr(settings, "USE_X_ACCEL_REDIRECT", False)
        if use_x_accel:
            x_accel_prefix = getattr(settings, "X_ACCEL_PREFIX", "/protected_media/").rstrip("/") + "/"
            rel_name = posixpath.normpath(str(document.file.name)).lstrip("/")
            if ".." in rel_name.split("/") or rel_name.startswith("/"):
                raise Http404("Invalid file path.")

            internal_path = f"{x_accel_prefix}{rel_name}"
            response = HttpResponse(content_type=content_type)
            response["X-Accel-Redirect"] = internal_path
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response["Content-Security-Policy"] = "default-src 'none'; sandbox"
            return response

        try:
            file_handle = document.file.open("rb")
        except (FileNotFoundError, OSError):
            raise Http404("File not found on storage.")

        response = FileResponse(file_handle, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response



