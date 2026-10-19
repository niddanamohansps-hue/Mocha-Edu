from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection
from django.db.models import Q
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.audit import log_action
from core.pagination import StandardResultsPagination
from profiles.models import InstitutionProfile
from roles.permissions import HasPermission

from . import idcards, pdf, services
from .models import Certificate, CertificateSettings
from .serializers import (
    CancelSerializer,
    CertificateBasicSerializer,
    CertificateListSerializer,
    CertificateSerializer,
    CertificateSettingsSerializer,
    IssueSerializer,
    ReissueSerializer,
)

# type -> permission required to issue/reissue it
ISSUE_PERMISSION = {
    Certificate.Type.TRANSFER: "approve_certificates",
    Certificate.Type.EXPERIENCE: "approve_certificates",
    Certificate.Type.BONAFIDE: "issue_certificates",
    Certificate.Type.CHARACTER: "issue_certificates",
}


def _to_drf(exc):
    if isinstance(exc, DjangoValidationError):
        return serializers.ValidationError({"non_field_errors": exc.messages})
    return exc


def _require_permission(request, view, codename, message):
    if not HasPermission(codename).has_permission(request, view):
        raise PermissionDenied(message)


def _tenant_only():
    if connection.schema_name == "public":
        raise NotFound()


def _pdf_assets():
    institution = InstitutionProfile.objects.first()
    settings_row = CertificateSettings.objects.first()
    return {
        "institution_logo": pdf.load_image(institution.logo) if institution else None,
        "signature": pdf.load_image(settings_row.signature) if settings_row else None,
        "signatory_name": settings_row.signatory_name if settings_row else "",
        "signatory_title": settings_row.signatory_title if settings_row else "",
    }


def _pdf_response(content, filename):
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class CertificateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = CertificateSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["certificate_type", "status"]
    ordering_fields = ["issued_at", "certificate_number", "issue_date"]
    ordering = ["-issued_at", "-id"]

    def get_queryset(self):
        _tenant_only()
        queryset = Certificate.objects.select_related("student", "staff_member", "supersedes", "superseded_by")
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(certificate_number__icontains=search) | Q(snapshot__holder_name__icontains=search)
            )
        return queryset

    SENSITIVE_PERMISSIONS = ("issue_certificates", "approve_certificates", "cancel_certificates")

    def get_serializer_class(self):
        """Backend-enforced field exposure: list rows are minimal; a single
        certificate shows internal notes and internal ids only to people who
        issue, approve or cancel certificates, not to read-only viewers."""
        if self.action == "list":
            return CertificateListSerializer
        if self.action == "retrieve":
            if any(HasPermission(code).has_permission(self.request, self) for code in self.SENSITIVE_PERMISSIONS):
                return CertificateSerializer
            return CertificateBasicSerializer
        return CertificateSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]  # per-type permission is checked in create()
        if self.action in ("cancel", "reissue"):
            return [IsAuthenticated(), HasPermission("cancel_certificates")]
        return [IsAuthenticated(), HasPermission("view_certificates")]

    def _subject(self, certificate_type, validated):
        if certificate_type in Certificate.STUDENT_TYPES:
            from students.models import Student

            subject = Student.objects.select_related("profile").filter(pk=validated.get("student_id")).first()
            if subject is None:
                raise serializers.ValidationError({"student_id": "Student not found."})
        else:
            from staff.models import StaffMember

            subject = StaffMember.objects.select_related("profile").filter(pk=validated.get("staff_id")).first()
            if subject is None:
                raise serializers.ValidationError({"staff_id": "Staff member not found."})
        return subject

    def create(self, request):
        _tenant_only()
        payload = IssueSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        certificate_type = data["certificate_type"]
        permission = ISSUE_PERMISSION[certificate_type]
        _require_permission(request, self, permission, "You do not have permission to issue this certificate type.")
        subject = self._subject(certificate_type, data)
        try:
            cert = services.issue_certificate(
                certificate_type=certificate_type,
                subject=subject,
                data=data,
                issued_by_user_id=request.user.id,
                approved_by_user_id=request.user.id if permission == "approve_certificates" else None,
            )
        except DjangoValidationError as exc:
            raise _to_drf(exc)
        log_action(
            request, action="certificate_issued", model_name="Certificate", object_id=cert.id,
            changes={
                "number": cert.certificate_number, "type": cert.certificate_type,
                "integrity_key": services.seal_key_id(cert),
                "end_date_source": cert.snapshot.get("end_date_source"),
            },
        )
        return Response(CertificateSerializer(cert).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="pdf")
    def download_pdf(self, request, pk=None):
        cert = self.get_object()
        verify_url = idcards.frontend_url(request, f"/verify/certificate/{cert.verification_id}")
        content = pdf.render_certificate_pdf(cert, verify_url, **_pdf_assets())
        log_action(request, action="certificate_downloaded", model_name="Certificate", object_id=cert.id)
        return _pdf_response(content, f"{cert.certificate_number}.pdf")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        cert = self.get_object()
        payload = CancelSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            cert = services.cancel_certificate(
                certificate_id=cert.id, user_id=request.user.id, reason=payload.validated_data["reason"]
            )
        except DjangoValidationError as exc:
            raise _to_drf(exc)
        log_action(
            request, action="certificate_cancelled", model_name="Certificate", object_id=cert.id,
            changes={"number": cert.certificate_number, "reason": cert.cancellation_reason},
        )
        return Response(CertificateSerializer(self.get_queryset().get(pk=cert.pk)).data)

    @action(detail=True, methods=["post"])
    def reissue(self, request, pk=None):
        cert = self.get_object()
        permission = ISSUE_PERMISSION[cert.certificate_type]
        _require_permission(request, self, permission, "You do not have permission to reissue this certificate type.")
        payload = ReissueSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        reason = data.pop("reason")
        if data.get("new_reason"):
            data["reason"] = data["new_reason"]
        data.pop("new_reason", None)
        try:
            old, new = services.reissue_certificate(
                certificate_id=cert.id,
                user_id=request.user.id,
                approved_by_user_id=request.user.id if permission == "approve_certificates" else None,
                reason=reason,
                data=data,
            )
        except DjangoValidationError as exc:
            raise _to_drf(exc)
        log_action(
            request, action="certificate_reissued", model_name="Certificate", object_id=new.id,
            changes={"old": old.certificate_number, "new": new.certificate_number, "reason": reason},
        )
        return Response(CertificateSerializer(self.get_queryset().get(pk=new.pk)).data, status=status.HTTP_201_CREATED)


class CertificateSettingsView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), HasPermission("view_certificates")]
        return [IsAuthenticated(), HasPermission("manage_certificate_settings")]

    def get(self, request):
        _tenant_only()
        return Response(CertificateSettingsSerializer(CertificateSettings.load()).data)

    def patch(self, request):
        _tenant_only()
        row = CertificateSettings.load()
        serializer = CertificateSettingsSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        signature = request.data.get("signature") if hasattr(request.data, "get") else None
        if signature and hasattr(signature, "content_type") and not signature.content_type.startswith("image/"):
            raise serializers.ValidationError({"signature": "Upload an image file."})
        serializer.save()
        log_action(
            request, action="certificate_settings_updated", model_name="CertificateSettings", object_id=row.id,
            changes={"fields": sorted(k for k in request.data.keys() if k != "signature"), "signature_changed": bool(signature)},
        )
        return Response(CertificateSettingsSerializer(row).data)


class _IdCardBase(APIView):
    permission_classes = [IsAuthenticated, HasPermission("generate_id_cards")]
    kind = None

    def _record(self, record_id):
        _tenant_only()
        if self.kind == idcards.KIND_STUDENT:
            from students.models import Student

            record = Student.objects.select_related("profile").filter(pk=record_id).first()
        else:
            from staff.models import StaffMember

            record = StaffMember.objects.select_related("profile").filter(pk=record_id).first()
        if record is None:
            raise NotFound()
        return record

    def _card(self, record):
        try:
            if self.kind == idcards.KIND_STUDENT:
                return idcards.build_student_card(record)
            return idcards.build_staff_card(record)
        except DjangoValidationError as exc:
            raise _to_drf(exc)

    def _verify_url(self, request, record):
        return idcards.frontend_url(request, f"/verify/id/{idcards.card_token(self.kind, record)}")


class IdCardDataView(_IdCardBase):
    """JSON for the on-screen print view."""

    def get(self, request, record_id):
        record = self._record(record_id)
        card = self._card(record)
        verify_url = self._verify_url(request, record)
        institution = InstitutionProfile.objects.first()
        log_action(request, action="id_card_generated", model_name=card["kind_label"], object_id=record.pk)
        return Response(
            {
                **card,
                "details": [{"label": k, "value": v} for k, v in card["details"] if v],
                "photo": idcards.photo_data_uri(record.profile),
                "logo": idcards.field_data_uri(institution.logo) if institution else None,
                "qr_svg": pdf.qr_svg_data_uri(verify_url),
            }
        )


class IdCardPdfView(_IdCardBase):
    def get(self, request, record_id):
        record = self._record(record_id)
        card = self._card(record)
        try:
            idcards.ensure_printable(card)
        except DjangoValidationError as exc:
            raise _to_drf(exc)
        institution = InstitutionProfile.objects.first()
        content = pdf.render_id_card_pdf(
            card,
            self._verify_url(request, record),
            institution_logo=pdf.load_image(institution.logo) if institution else None,
            photo=pdf.load_image(record.profile.profile_image),
        )
        log_action(request, action="id_card_downloaded", model_name=card["kind_label"], object_id=record.pk)
        return _pdf_response(content, f"id-card-{card['id_number']}.pdf")


class IdCardRotateView(_IdCardBase):
    """POST: revoke the card's QR token and issue a new one (lost or reprinted
    card). The old printed code stops verifying immediately."""

    def post(self, request, record_id):
        record = self._record(record_id)
        self._card(record)  # same eligibility as generating a card
        token, revoked_id = idcards.rotate_card_token(self.kind, record)
        log_action(
            request, action="id_card_token_rotated", model_name=self.kind.capitalize(), object_id=record.pk,
            changes={"revoked_token_row": str(revoked_id) if revoked_id else None, "token_suffix": token[-4:]},
        )
        return Response({"rotated": True, "verification_url": self._verify_url(request, record)})


class StudentIdCardRotate(IdCardRotateView):
    kind = idcards.KIND_STUDENT


class StaffIdCardRotate(IdCardRotateView):
    kind = idcards.KIND_STAFF


class StudentIdCardData(IdCardDataView):
    kind = idcards.KIND_STUDENT


class StaffIdCardData(IdCardDataView):
    kind = idcards.KIND_STAFF


class StudentIdCardPdf(IdCardPdfView):
    kind = idcards.KIND_STUDENT


class StaffIdCardPdf(IdCardPdfView):
    kind = idcards.KIND_STAFF


class _PublicBase(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_certificate_verify"


class PublicCertificateVerifyView(_PublicBase):
    def get(self, request, verification_id):
        _tenant_only()
        cert = Certificate.objects.select_related("superseded_by").filter(verification_id=verification_id).first()
        if cert is None:
            raise NotFound()
        response = Response(services.public_verification(cert))
        response["Cache-Control"] = "no-store"
        return response


class PublicIdCardVerifyView(_PublicBase):
    def get(self, request, token):
        _tenant_only()
        response = Response(idcards.public_card_verification(token))
        response["Cache-Control"] = "no-store"
        return response
