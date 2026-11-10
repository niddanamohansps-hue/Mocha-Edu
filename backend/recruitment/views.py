import os

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
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
from core.query_params import model_param
from accounts.tenant_access import HasAnyPermission
from roles.permissions import HasPermission

from .models import Applicant, Interview, JobOpening
from .serializers import (
    ApplicantEventSerializer,
    ApplicantSerializer,
    HireSerializer,
    InterviewCompleteSerializer,
    InterviewSerializer,
    JobOpeningSerializer,
    OfferSerializer,
    PanelistFeedbackSerializer,
    PublicApplySerializer,
    PublicOpeningSerializer,
    StageMoveSerializer,
)
from .services import (
    close_opening,
    complete_interview,
    hire_applicant,
    CANDIDATE_STATUS,
    decoy_credentials,
    find_applicant_by_credentials,
    is_accepting_applications,
    issue_access_token,
    move_stage,
    offer_letter,
    save_offer,
    send_interview_invitation,
    send_offer,
    send_stage_update,
    notify_panelists,
    open_opening,
    record_event,
    send_application_confirmation,
    set_panel,
    staff_for_user,
    submit_panelist_feedback,
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


def _serve_resume(request, applicant):
    """The applicant's resume through a permission-checked response (never a /media/ URL)."""
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
    read_actions = ("list", "retrieve", "resume", "history", "letter")

    def get_permissions(self):
        if self.action == "hire":
            # Hiring creates a staff record, so it needs the same right as onboarding staff directly.
            return [IsAuthenticated(), HasPermission("manage_recruitment"), HasPermission("add_staff")]
        return super().get_permissions()

    def get_queryset(self):
        qs = Applicant.objects.select_related("opening").prefetch_related("interviews")
        params = self.request.query_params
        opening_id = model_param(self.request, "opening", qs.model, "opening")
        if opening_id is not None:
            qs = qs.filter(opening_id=opening_id)
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
        # An interview invitation carries the date, so moving to the interview stage is announced when the
        # interview is scheduled; every other stage tells the candidate now.
        if applicant.stage != Applicant.Stage.INTERVIEW:
            send_stage_update(applicant, applicant.stage)
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

    @action(detail=True, methods=["post"], url_path="offer")
    def offer(self, request, pk=None):
        data = OfferSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            with transaction.atomic():
                applicant = save_offer(
                    self.get_object(), designation=v.get("designation", ""), salary=v["salary"],
                    joining_date=v["joining_date"], valid_until=v.get("valid_until"), notes=v.get("notes", ""),
                    user=request.user, request=request,
                )
        except DjangoValidationError as exc:
            raise _as_api_error(exc)
        return Response(self.get_serializer(applicant).data)

    @action(detail=True, methods=["get"], url_path="letter")
    def letter(self, request, pk=None):
        try:
            return Response(offer_letter(self.get_object()))
        except DjangoValidationError as exc:
            raise _as_api_error(exc)

    @action(detail=True, methods=["post"], url_path="send-offer")
    def send_offer(self, request, pk=None):
        try:
            with transaction.atomic():
                applicant = send_offer(self.get_object(), request.user, request)
        except DjangoValidationError as exc:
            raise _as_api_error(exc)
        return Response(self.get_serializer(applicant).data)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        return Response(ApplicantEventSerializer(self.get_object().events.all(), many=True).data)

    @action(detail=True, methods=["get"], url_path="resume")
    def resume(self, request, pk=None):
        return _serve_resume(request, self.get_object())


class InterviewViewSet(viewsets.ModelViewSet):
    serializer_class = InterviewSerializer
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "resume"):
            # Panelists read their own interviews; get_queryset narrows them to those.
            return [IsAuthenticated(), HasAnyPermission("view_recruitment", "record_interview_feedback")]
        if self.action == "feedback":
            return [IsAuthenticated(), HasPermission("record_interview_feedback")]
        return [IsAuthenticated(), HasPermission("manage_recruitment")]

    def _is_hr(self):
        return HasPermission("view_recruitment")().has_permission(self.request, self)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        staff = staff_for_user(self.request.user)
        context["is_hr"] = self._is_hr()
        context["my_staff_id"] = staff.id if staff else None
        return context

    def get_queryset(self):
        qs = Interview.objects.select_related("applicant__opening", "interviewer__profile").prefetch_related(
            "panelists__staff__profile"
        )
        if not self._is_hr():
            staff = staff_for_user(self.request.user)
            qs = qs.filter(panelists__staff=staff) if staff else qs.none()
        params = self.request.query_params
        applicant_id = model_param(self.request, "applicant", qs.model, "applicant")
        if applicant_id is not None:
            qs = qs.filter(applicant_id=applicant_id)
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("mine") == "true":
            staff = staff_for_user(self.request.user)
            qs = qs.filter(panelists__staff=staff) if staff else qs.none()
        return qs.distinct()

    def _save_panel(self, serializer, instance):
        ids = serializer.validated_data.get("panelist_ids")
        if ids is None:
            return
        try:
            added = set_panel(instance, ids, self.request)
        except DjangoValidationError as exc:
            raise _as_api_error(exc)
        if added:
            notify_panelists(instance, added)

    def perform_create(self, serializer):
        with transaction.atomic():
            interview = serializer.save(created_by_id=self.request.user.id)
            self._save_panel(serializer, interview)
            send_interview_invitation(interview)

    def perform_update(self, serializer):
        with transaction.atomic():
            interview = serializer.save()
            self._save_panel(serializer, interview)

    def update(self, request, *args, **kwargs):
        if self.get_object().status != Interview.Status.SCHEDULED:
            raise ValidationError("Only a scheduled interview can be changed.")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="feedback")
    def feedback(self, request, pk=None):
        """A panelist records their own score and comment; the interview completes when the last one does."""
        data = PanelistFeedbackSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        staff = staff_for_user(request.user)
        if staff is None:
            raise ValidationError("Your login is not linked to a staff record.")
        try:
            interview = submit_panelist_feedback(
                self.get_object(), staff, data.validated_data["score"], data.validated_data.get("feedback", ""), request
            )
        except DjangoValidationError as exc:
            raise _as_api_error(exc)
        return Response(self.get_serializer(self.get_queryset().get(pk=interview.pk)).data)

    @action(detail=True, methods=["get"], url_path="resume")
    def resume(self, request, pk=None):
        return _serve_resume(request, self.get_object().applicant)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        interview = self.get_object()
        panel = interview.panelists.exists()
        score = feedback = None
        if not panel:
            data = InterviewCompleteSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            score, feedback = data.validated_data["score"], data.validated_data.get("feedback", "")
        try:
            interview = complete_interview(interview, score, feedback or "", request)
        except DjangoValidationError as exc:
            raise _as_api_error(exc)
        return Response(self.get_serializer(self.get_queryset().get(pk=interview.pk)).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        interview = self.get_object()
        if interview.status != Interview.Status.SCHEDULED:
            raise ValidationError("Only a scheduled interview can be cancelled.")
        interview.status = Interview.Status.CANCELLED
        interview.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(interview).data)


class PanelOptionsView(APIView):
    """Active staff HR can put on an interview panel."""

    permission_classes = [IsAuthenticated, HasPermission("manage_recruitment")]

    def get(self, request):
        from staff.models import StaffMember

        members = StaffMember.objects.filter(is_active=True).select_related("profile").order_by(
            "profile__first_name", "profile__last_name"
        )
        return Response(
            [
                {
                    "id": m.id,
                    "name": f"{m.profile.first_name} {m.profile.last_name}".strip(),
                    "designation": m.designation,
                }
                for m in members
            ]
        )


class PanelConflictsView(APIView):
    """Warnings for a proposed panel and time: who is on leave, on exam duty, teaching or already on another panel."""

    permission_classes = [IsAuthenticated, HasPermission("manage_recruitment")]

    def get(self, request):
        import uuid

        from django.utils.dateparse import parse_datetime

        raw = (request.query_params.get("at") or "").strip().replace(" ", "+")
        moment = parse_datetime(raw) if raw else None
        if moment is None:
            raise ValidationError({"at": ["Give the interview date and time."]})
        if moment.tzinfo is None:
            from core.dates import school_zone

            moment = moment.replace(tzinfo=school_zone())
        ids = [i for i in (request.query_params.get("staff") or "").split(",") if i]
        try:
            ids = [str(uuid.UUID(i)) for i in ids]
        except ValueError:
            raise ValidationError({"staff": ["Those are not valid staff ids."]})
        from .services import panel_conflicts

        return Response(panel_conflicts(ids, moment, exclude_interview=model_param(request, "interview", Interview)))


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
