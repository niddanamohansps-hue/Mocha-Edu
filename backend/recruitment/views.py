import os

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django_tenants.utils import get_public_schema_name
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.audit import log_action
from roles.permissions import HasPermission

from .models import Applicant, Interview, JobOpening
from .serializers import (
    ApplicantEventSerializer,
    ApplicantSerializer,
    HireSerializer,
    InterviewCompleteSerializer,
    InterviewSerializer,
    JobOpeningSerializer,
    PublicApplySerializer,
    PublicOpeningSerializer,
    StageMoveSerializer,
)
from .services import (
    close_opening,
    hire_applicant,
    CANDIDATE_STATUS,
    decoy_credentials,
    find_applicant_by_credentials,
    is_accepting_applications,
    issue_access_token,
    move_stage,
    open_opening,
    record_event,
    send_application_confirmation,
)
from .captcha import verify_captcha


def _as_api_error(exc):
    """Business-rule failures from the services become 400 responses with the message intact."""
    detail = getattr(exc, "message_dict", None) or exc.messages
    return ValidationError(detail)


class _ReadOrManage:
    """list/retrieve need view_recruitment; anything that changes data needs manage_recruitment."""

    read_actions = ("list", "retrieve")

    def get_permissions(self):
        code = "view_recruitment" if self.action in self.read_actions else "manage_recruitment"
        return [IsAuthenticated(), HasPermission(code)]


class JobOpeningViewSet(_ReadOrManage, viewsets.ModelViewSet):
    serializer_class = JobOpeningSerializer

    def get_queryset(self):
        qs = JobOpening.objects.annotate(
            applicant_count=Count("applicants", distinct=True),
            hired_count=Count("applicants", filter=Q(applicants__stage=Applicant.Stage.HIRED), distinct=True),
        )
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("position_type"):
            qs = qs.filter(position_type=params["position_type"])
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by_id=self.request.user.id)

    def update(self, request, *args, **kwargs):
        if self.get_object().status == JobOpening.Status.CLOSED:
            raise ValidationError("A closed opening cannot be edited.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        opening = self.get_object()
        if opening.applicants.exists():
            raise ValidationError("An opening that has applicants cannot be deleted; close it instead.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        try:
            opening = open_opening(self.get_object(), request)
        except DjangoValidationError as exc:
            raise _as_api_error(exc)
        return Response(self.get_serializer(self.get_queryset().get(pk=opening.pk)).data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        opening = close_opening(self.get_object(), request)
        return Response(self.get_serializer(self.get_queryset().get(pk=opening.pk)).data)


class ApplicantViewSet(_ReadOrManage, viewsets.ModelViewSet):
    serializer_class = ApplicantSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "patch", "put", "head", "options"]
    read_actions = ("list", "retrieve", "resume", "history")

    def get_permissions(self):
        if self.action == "hire":
            # Hiring creates a staff record, so it needs the same right as onboarding staff directly.
            return [IsAuthenticated(), HasPermission("manage_recruitment"), HasPermission("add_staff")]
        return super().get_permissions()

    def get_queryset(self):
        qs = Applicant.objects.select_related("opening").prefetch_related("interviews")
        params = self.request.query_params
        if params.get("opening"):
            qs = qs.filter(opening_id=params["opening"])
        if params.get("stage"):
            qs = qs.filter(stage=params["stage"])
        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )
        return qs

    def perform_create(self, serializer):
        applicant = serializer.save(created_by_id=self.request.user.id)
        record_event(applicant, "", applicant.stage, self.request.user, "Application recorded")

    @action(detail=True, methods=["post"], url_path="move")
    def move(self, request, pk=None):
        data = StageMoveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            applicant = move_stage(
                self.get_object(),
                data.validated_data["stage"],
                request.user,
                note=data.validated_data.get("note", ""),
                rejection_reason=data.validated_data.get("rejection_reason", ""),
                request=request,
            )
        except DjangoValidationError as exc:
            raise _as_api_error(exc)
        return Response(self.get_serializer(applicant).data)

    @action(detail=True, methods=["post"], url_path="hire")
    def hire(self, request, pk=None):
        data = HireSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            applicant = hire_applicant(self.get_object(), request.user, dict(data.validated_data), request)
        except DjangoValidationError as exc:
            raise _as_api_error(exc)
        return Response(self.get_serializer(applicant).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        return Response(ApplicantEventSerializer(self.get_object().events.all(), many=True).data)

    @action(detail=True, methods=["get"], url_path="resume")
    def resume(self, request, pk=None):
        applicant = self.get_object()
        if not applicant.resume:
            raise Http404("This applicant has no resume.")
        log_action(request, "applicant_resume_viewed", "Applicant", str(applicant.id))
        filename = os.path.basename(applicant.resume.name)
        if getattr(settings, "USE_X_ACCEL_REDIRECT", False):
            response = HttpResponse()
            prefix = getattr(settings, "X_ACCEL_PREFIX", "/protected_media/").rstrip("/")
            response["X-Accel-Redirect"] = f"{prefix}/{applicant.resume.name}"
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response
        try:
            return FileResponse(applicant.resume.open("rb"), filename=filename)
        except OSError:
            raise Http404("The resume could not be read from storage.")


class InterviewViewSet(_ReadOrManage, viewsets.ModelViewSet):
    serializer_class = InterviewSerializer
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    def get_queryset(self):
        qs = Interview.objects.select_related("applicant", "interviewer__profile")
        params = self.request.query_params
        if params.get("applicant"):
            qs = qs.filter(applicant_id=params["applicant"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by_id=self.request.user.id)

    def update(self, request, *args, **kwargs):
        if self.get_object().status != Interview.Status.SCHEDULED:
            raise ValidationError("Only a scheduled interview can be changed.")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        interview = self.get_object()
        if interview.status != Interview.Status.SCHEDULED:
            raise ValidationError("Only a scheduled interview can be completed.")
        data = InterviewCompleteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        interview.status = Interview.Status.COMPLETED
        interview.score = data.validated_data["score"]
        interview.feedback = data.validated_data.get("feedback", "")
        interview.save(update_fields=["status", "score", "feedback", "updated_at"])
        return Response(self.get_serializer(interview).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        interview = self.get_object()
        if interview.status != Interview.Status.SCHEDULED:
            raise ValidationError("Only a scheduled interview can be cancelled.")
        interview.status = Interview.Status.CANCELLED
        interview.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(interview).data)


class RecruitmentSummaryView(APIView):
    """Counts for the recruitment landing page."""

    permission_classes = [IsAuthenticated, HasPermission("view_recruitment")]

    def get(self, request):
        stages = {s: 0 for s in Applicant.Stage.values}
        for row in Applicant.objects.values("stage").annotate(n=Count("id")):
            stages[row["stage"]] = row["n"]
        return Response(
            {
                "open_openings": JobOpening.objects.filter(status=JobOpening.Status.OPEN).count(),
                "applicants_by_stage": stages,
                "upcoming_interviews": Interview.objects.filter(status=Interview.Status.SCHEDULED).count(),
            }
        )


def _public_school_only():
    """The careers page belongs to one school, so it is not served on the platform's own (public) schema."""
    if connection.schema_name == get_public_schema_name():
        raise Http404("Careers are only available on individual school domains.")


class PublicOpeningsView(APIView):
    """The positions a school is currently hiring for. No login."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_careers_info"

    def get(self, request):
        _public_school_only()
        open_now = [o for o in JobOpening.objects.filter(status=JobOpening.Status.OPEN) if is_accepting_applications(o)]
        return Response(PublicOpeningSerializer(open_now, many=True).data)


class PublicApplyView(APIView):
    """A candidate applies to an open position. No login; throttled; lands in the Applied stage."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_careers_apply"
    parser_classes = [MultiPartParser, FormParser]

    MESSAGE = "Thank you. Your application has been received."

    def _reply(self, reference, token):
        response = Response(
            {"success": True, "message": self.MESSAGE, "reference": reference, "access_code": token},
            status=status.HTTP_201_CREATED,
        )
        response["Cache-Control"] = "no-store"
        return response

    def post(self, request):
        _public_school_only()
        if not verify_captcha(request.data.get("cf-turnstile-response"), request.META.get("REMOTE_ADDR")):
            raise ValidationError({"captcha": "Please complete the verification and try again."})
        # A hidden field real visitors never see. Bots that fill every field get a normal-looking reply and nothing is stored.
        if request.data.get("website"):
            return self._reply(*decoy_credentials())

        serializer = PublicApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        opening = data.pop("opening")

        # Someone who has already applied gets a reply of the same shape (with credentials that match nothing),
        # so the form cannot be used to find out who applied.
        if Applicant.objects.filter(opening=opening, email=data["email"]).exists():
            return self._reply(*decoy_credentials())

        applicant = Applicant.objects.create(opening=opening, source="Careers page", **data)
        record_event(applicant, "", Applicant.Stage.APPLIED, None, "Applied online")
        token = issue_access_token(applicant)
        scheme = "https" if request.is_secure() else "http"
        send_application_confirmation(
            applicant,
            token,
            f"{scheme}://{request.get_host()}/careers/status",
            getattr(request.tenant, "name", "The school") if hasattr(request, "tenant") else "The school",
        )
        return self._reply(applicant.reference, token)


class PublicStatusView(APIView):
    """A candidate checks where their application stands, using the reference and access code they were given."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_careers_status"

    def post(self, request):
        _public_school_only()
        applicant = find_applicant_by_credentials(request.data.get("reference"), request.data.get("access_code"))
        if applicant is None:
            raise Http404("No application matches those details.")
        upcoming = (
            applicant.interviews.filter(status=Interview.Status.SCHEDULED).order_by("scheduled_at").first()
            if applicant.stage == Applicant.Stage.INTERVIEW
            else None
        )
        response = Response(
            {
                "reference": applicant.reference,
                "position": applicant.opening.title,
                "applied_on": applicant.created_at.date().isoformat(),
                "status": CANDIDATE_STATUS[applicant.stage],
                "interview": (
                    {
                        "round": upcoming.round_name,
                        "scheduled_at": upcoming.scheduled_at.isoformat(),
                        "mode": upcoming.mode,
                        "location_or_url": upcoming.location_or_url,
                    }
                    if upcoming
                    else None
                ),
            }
        )
        response["Cache-Control"] = "no-store"
        return response
