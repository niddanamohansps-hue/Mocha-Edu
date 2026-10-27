from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from .models import ExamResult, ExamSchedule, Examination, ExamType, GradeBoundary
from .serializers import (
    ExamMarkBulkSerializer,
    ExamResultSerializer,
    ExamScheduleCreateUpdateSerializer,
    ExamScheduleSerializer,
    ExaminationSerializer,
    ExamTypeSerializer,
    GradeBoundarySerializer,
)
from .services import (
    get_instructor_for_user,
    get_staff_member_for_user,
    get_student_for_user,
    is_owner,
    publish_examination,
    user_can_access_schedule,
    user_can_access_student_result,
)


class ExamTypeViewSet(viewsets.ModelViewSet):
    queryset = ExamType.objects.all()
    serializer_class = ExamTypeSerializer

    def get_permissions(self):
        perm = HasPermission("view_examinations" if self.action in ("list", "retrieve") else "manage_examinations")
        return [IsAuthenticated(), perm]


class ExaminationViewSet(viewsets.ModelViewSet):
    queryset = Examination.objects.select_related("exam_type")
    serializer_class = ExaminationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["academic_year", "exam_type", "is_published"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            perm = HasPermission("view_examinations")
        elif self.action == "publish":
            perm = HasPermission("publish_results")
        elif self.action == "request_publication":
            perm = HasPermission("manage_examinations")
        else:
            perm = HasPermission("manage_examinations")
        return [IsAuthenticated(), perm]

    def perform_create(self, serializer):
        examination = serializer.save()
        log_action(
            self.request, action="examination_created", model_name="Examination", object_id=examination.id,
            changes={"name": examination.name, "academic_year": examination.academic_year},
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.is_published:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"non_field_errors": ["A published examination cannot be edited."]})
        examination = serializer.save()
        log_action(
            self.request, action="examination_updated", model_name="Examination", object_id=examination.id,
            changes={"name": examination.name},
        )

    def perform_destroy(self, instance):
        if instance.is_published:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"non_field_errors": ["A published examination cannot be deleted."]})
        exam_id, name = instance.id, instance.name
        instance.delete()
        log_action(self.request, action="examination_deleted", model_name="Examination", object_id=exam_id, changes={"name": name})

    @action(detail=True, methods=["post"], url_path="request-publication")
    def request_publication(self, request, pk=None):
        """Ask for the results to be published. With two-person publishing on, someone else then publishes."""
        from django.utils import timezone

        examination = self.get_object()
        if examination.is_published:
            return Response({"error": "This examination is already published."}, status=status.HTTP_400_BAD_REQUEST)
        examination.publication_requested_by_user_id = request.user.id
        examination.publication_requested_at = timezone.now()
        examination.save(update_fields=["publication_requested_by_user_id", "publication_requested_at", "updated_at"])
        log_action(request, action="results_publication_requested", model_name="Examination", object_id=examination.id)
        _tell_publishers(examination, exclude=request.user.id)
        return Response(ExaminationSerializer(examination).data)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        examination = self.get_object()
        from .models import ExaminationSettings

        if ExaminationSettings.load().require_separate_publisher:
            requester = examination.publication_requested_by_user_id
            if requester is None:
                return Response({"error": "Ask for publication first; a different person then publishes the results."},
                                status=status.HTTP_400_BAD_REQUEST)
            if requester == request.user.id:
                return Response({"error": "You asked for these results to be published, so someone else must publish them."},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            publish_examination(examination)
        except Exception as exc:
            from rest_framework.exceptions import ValidationError

            if isinstance(exc, ValidationError):
                raise
            raise ValidationError({"non_field_errors": [str(exc)]})

        Examination.objects.filter(pk=examination.pk).update(published_by_user_id=request.user.id)
        examination.refresh_from_db()
        log_action(
            request, action="results_published", model_name="Examination", object_id=examination.id,
            changes={"name": examination.name, "result_count": ExamResult.objects.filter(examination=examination).count()},
        )
        return Response(ExaminationSerializer(examination).data)


def _marks_blocked(request, schedule):
    """Marks of a published examination change only through a recheck or grace marks; a locked schedule only by
    someone with manage_marks."""
    if schedule.examination.is_published:
        return Response({"error": "Results of this examination are published. Change a mark through a recheck or grace marks."},
                        status=status.HTTP_423_LOCKED)
    if schedule.is_locked and not HasPermission("manage_marks").has_permission(request, None):
        return Response({"error": "This exam schedule is locked."}, status=status.HTTP_423_LOCKED)
    return None


def _user_names(user_ids):
    """{user id: display name} from the tenant's profiles; blank for anyone without a profile."""
    from profiles.models import Profile

    ids = {i for i in user_ids if i}
    return {
        str(p.user_id): f"{p.first_name} {p.last_name}".strip()
        for p in Profile.objects.filter(user_id__in=ids)
    }


def _tell_publishers(examination, exclude=None):
    """In-app notice to everyone who may publish results (except the requester), after the request commits."""
    from django.db import transaction
    from django.db.models import Q

    from roles.models import UserRole

    ids = set(UserRole.objects.filter(Q(role__slug="owner") | Q(role__permissions__codename="publish_results"))
              .values_list("user_id", flat=True)) - {exclude}
    if not ids:
        return

    def send():
        from notifications.services import notify_many

        try:
            notify_many(recipient_user_ids=list(ids), title=f"Results ready to publish: {examination.name}",
                        body="Marks are in and publication has been requested.", category="examinations",
                        link="/dashboard/examinations")
        except Exception:  # pragma: no cover - best effort
            pass

    transaction.on_commit(send)


class ExaminationSettingsView(APIView):
    """GET/PATCH /api/examinations/settings/ - the school's examination rules."""

    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        perm = HasPermission("view_examinations" if self.request.method in ("GET", "HEAD", "OPTIONS") else "manage_examinations")
        return [IsAuthenticated(), perm]

    def get(self, request):
        from .models import ExaminationSettings

        row = ExaminationSettings.load()
        return Response({"require_separate_publisher": row.require_separate_publisher, "is_default": row._state.adding})

    def patch(self, request):
        from rest_framework.exceptions import ValidationError

        from .models import ExaminationSettings

        value = request.data.get("require_separate_publisher")
        if set(request.data) != {"require_separate_publisher"} or not isinstance(value, bool):
            raise ValidationError({"require_separate_publisher": "Send true or false."})
        row, _ = ExaminationSettings.objects.get_or_create(singleton=True)
        previous = row.require_separate_publisher
        row.require_separate_publisher, row.updated_by_user_id = value, request.user.id
        row.save()
        log_action(request, action="examination_settings_changed", model_name="ExaminationSettings", object_id=row.id,
                   changes={"require_separate_publisher": [previous, value]})
        return Response({"require_separate_publisher": row.require_separate_publisher, "is_default": False})


class ExamScheduleViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["examination", "section", "subject", "academic_year"]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        # A custom get_permissions() override shadows @action's own
        # permission_classes kwarg entirely (DRF only auto-applies it when
        # the viewset relies on the default get_permissions()), so every
        # action - including the two custom ones below - must be handled
        # explicitly here rather than assumed to come from the decorator.
        if self.action in ("list", "retrieve"):
            perm = HasPermission("view_examinations")
        elif self.action in ("marks", "marks_import"):
            perm = HasPermission("enter_marks")
        elif self.action == "history":
            perm = HasPermission("view_examinations")
        elif self.action == "lock":
            perm = HasPermission("manage_marks")
        else:
            perm = HasPermission("manage_examinations")
        return [IsAuthenticated(), perm]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ExamScheduleCreateUpdateSerializer
        return ExamScheduleSerializer

    def get_queryset(self):
        qs = ExamSchedule.objects.select_related("examination", "subject", "section", "room", "period")

        if is_owner(self.request) or get_instructor_for_user(self.request.user) is None:
            return qs

        instructor = get_instructor_for_user(self.request.user)
        from academics.models import SubjectAssignment

        assignments = SubjectAssignment.objects.filter(instructor=instructor).values_list(
            "section_id", "subject_id"
        )
        pairs = set(assignments)
        if not pairs:
            return qs.none()
        # Exact (section, subject) pairs: teaching Maths in A and Science in B must not show Science in A.
        from django.db.models import Q

        match = Q()
        for section_id, subject_id in pairs:
            match |= Q(section_id=section_id, subject_id=subject_id)
        return qs.filter(match)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        section = serializer.validated_data["section"]
        subject = serializer.validated_data["subject"]
        instructor = get_instructor_for_user(request.user)
        if instructor is not None and not is_owner(request):
            from academics.models import SubjectAssignment

            if not SubjectAssignment.objects.filter(section=section, subject=subject, instructor=instructor).exists():
                return Response(
                    {"error": "You are not assigned to teach this subject for this section."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        schedule = serializer.save()
        log_action(
            request, action="exam_schedule_created", model_name="ExamSchedule", object_id=schedule.id,
            changes={"examination": str(schedule.examination_id), "section": str(schedule.section_id), "subject": str(schedule.subject_id)},
        )
        return Response(ExamScheduleSerializer(schedule).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        if not user_can_access_schedule(request, instance):
            return Response({"error": "You are not authorized to modify this schedule."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instructor = get_instructor_for_user(request.user)
        if instructor is not None and not is_owner(request):
            from academics.models import SubjectAssignment

            section = serializer.validated_data.get("section", instance.section)
            subject = serializer.validated_data.get("subject", instance.subject)
            if not SubjectAssignment.objects.filter(section=section, subject=subject, instructor=instructor).exists():
                return Response(
                    {"error": "You are not assigned to teach this subject for this section."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        schedule = serializer.save()
        log_action(
            request, action="exam_schedule_updated", model_name="ExamSchedule", object_id=schedule.id,
            changes={"examination": str(schedule.examination_id)},
        )
        return Response(ExamScheduleSerializer(schedule).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not user_can_access_schedule(request, instance):
            return Response({"error": "You are not authorized to modify this schedule."}, status=status.HTTP_403_FORBIDDEN)
        if instance.examination.is_published:
            return Response(
                {"error": "Cannot delete a schedule for a published examination."}, status=status.HTTP_400_BAD_REQUEST
            )

        schedule_id, examination_id = instance.id, instance.examination_id
        instance.delete()
        log_action(
            request, action="exam_schedule_deleted", model_name="ExamSchedule", object_id=schedule_id,
            changes={"examination": str(examination_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"])
    def marks(self, request, pk=None):
        schedule = get_object_or_404(ExamSchedule.objects.select_related("examination"), pk=pk)

        if not user_can_access_schedule(request, schedule):
            return Response({"error": "You are not authorized to enter marks for this schedule."}, status=status.HTTP_403_FORBIDDEN)

        if request.method == "GET":
            from .models import ExamMark
            from .serializers import ExamMarkSerializer

            rows = ExamMark.objects.filter(exam_schedule=schedule).select_related("student__profile")
            return Response({
                "is_published": schedule.examination.is_published,
                "marks": ExamMarkSerializer(rows, many=True).data,
            })

        blocked = _marks_blocked(request, schedule)
        if blocked:
            return blocked

        serializer = ExamMarkBulkSerializer(data=request.data, exam_schedule=schedule)
        serializer.is_valid(raise_exception=True)

        entered_by = get_staff_member_for_user(request.user)
        summary = serializer.save(entered_by=entered_by, user_id=request.user.id, require_reason=schedule.is_locked)

        log_action(
            request, action="marks_submitted", model_name="ExamSchedule", object_id=schedule.id,
            changes={
                "examination": str(schedule.examination_id), "schedule": str(schedule.id),
                "total_records": summary["total"], "absent": summary["absent"],
                "created": summary["created"], "updated": summary["updated"],
            },
        )
        return Response(ExamScheduleSerializer(schedule).data)

    @action(detail=True, methods=["post"], url_path="marks-import")
    def marks_import(self, request, pk=None):
        """Marks from a CSV file (enrollment_id, marks, optional attendance and remarks). With dry_run=true it only
        checks the file and returns a preview; otherwise it saves all rows, or none if any row is wrong."""
        from .marks import parse_marks_csv, record_marks
        from .models import ExamMarkChange

        schedule = get_object_or_404(ExamSchedule.objects.select_related("examination"), pk=pk)
        if not user_can_access_schedule(request, schedule):
            return Response({"error": "You are not authorized to enter marks for this schedule."}, status=status.HTTP_403_FORBIDDEN)
        blocked = _marks_blocked(request, schedule)
        if blocked:
            return blocked
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"error": "Choose a CSV file."}, status=status.HTTP_400_BAD_REQUEST)
        records, rows, errors = parse_marks_csv(schedule, upload)
        if errors:
            return Response({"errors": errors, "rows": rows}, status=status.HTTP_400_BAD_REQUEST)
        dry_run = str(request.data.get("dry_run", "")).lower() in ("1", "true", "yes")
        if dry_run:
            return Response({"dry_run": True, "rows": rows, "total": len(rows)})
        summary = record_marks(
            schedule, records, entered_by=get_staff_member_for_user(request.user), user_id=request.user.id,
            kind=ExamMarkChange.Kind.IMPORT, reason=str(request.data.get("reason", ""))[:500],
            require_reason=schedule.is_locked,
        )
        log_action(
            request, action="marks_imported", model_name="ExamSchedule", object_id=schedule.id,
            changes={"examination": str(schedule.examination_id), **summary},
        )
        return Response({"dry_run": False, **summary})

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Every entry and change of this schedule's marks, newest first."""
        from .models import ExamMarkChange
        from .serializers import ExamMarkChangeSerializer

        schedule = get_object_or_404(ExamSchedule, pk=pk)
        if not user_can_access_schedule(request, schedule):
            return Response({"error": "You are not authorized to see this schedule's marks."}, status=status.HTTP_403_FORBIDDEN)
        changes = list(
            ExamMarkChange.objects.filter(mark__exam_schedule=schedule).select_related("mark__student__profile")[:500]
        )
        return Response(ExamMarkChangeSerializer(changes, many=True, context={"names": _user_names(c.changed_by_user_id for c in changes)}).data)

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        schedule = self.get_object()
        if not user_can_access_schedule(request, schedule):
            return Response({"error": "You are not authorized to lock this schedule."}, status=status.HTTP_403_FORBIDDEN)
        from django.utils import timezone

        lock_value = request.data.get("is_locked", True)
        schedule.is_locked = bool(lock_value)
        schedule.locked_at = timezone.now() if schedule.is_locked else None
        schedule.save(update_fields=["is_locked", "locked_at", "updated_at"])

        log_action(
            request, action="marks_locked" if schedule.is_locked else "marks_unlocked",
            model_name="ExamSchedule", object_id=schedule.id, changes={"examination": str(schedule.examination_id)},
        )
        return Response(ExamScheduleSerializer(schedule).data)


class GradeBoundaryViewSet(viewsets.ModelViewSet):
    queryset = GradeBoundary.objects.all()
    serializer_class = GradeBoundarySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["academic_year"]

    def get_permissions(self):
        perm = HasPermission("view_examinations" if self.action in ("list", "retrieve") else "manage_grading")
        return [IsAuthenticated(), perm]

    def perform_create(self, serializer):
        boundary = serializer.save()
        log_action(
            self.request, action="grading_config_changed", model_name="GradeBoundary", object_id=boundary.id,
            changes={"grade_label": boundary.grade_label, "range": [str(boundary.min_percentage), str(boundary.max_percentage)]},
        )

    def perform_update(self, serializer):
        boundary = serializer.save()
        log_action(
            self.request, action="grading_config_changed", model_name="GradeBoundary", object_id=boundary.id,
            changes={"grade_label": boundary.grade_label, "range": [str(boundary.min_percentage), str(boundary.max_percentage)]},
        )

    def perform_destroy(self, instance):
        boundary_id, label = instance.id, instance.grade_label
        instance.delete()
        log_action(
            self.request, action="grading_config_changed", model_name="GradeBoundary", object_id=boundary_id,
            changes={"deleted": label},
        )


class StudentResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from students.models import Student

        student = get_object_or_404(Student.objects.select_related("profile"), id=student_id)

        own_student = get_student_for_user(request.user)
        if own_student is None or own_student.id != student.id:
            if not HasPermission("view_results").has_permission(request, None):
                return Response({"error": "You do not have permission to view results."}, status=status.HTTP_403_FORBIDDEN)
            if not user_can_access_student_result(request, student):
                return Response({"error": "You are not authorized to view this student's results."}, status=status.HTTP_403_FORBIDDEN)

        results = ExamResult.objects.filter(student=student).select_related("examination")
        academic_year = request.query_params.get("academic_year")
        if academic_year:
            results = results.filter(academic_year=academic_year)

        return Response(ExamResultSerializer(results, many=True).data)


class StudentReportCardView(APIView):
    """
    Renders every published ExamResult for the student within one academic year,
    along with school branding, attendance summary, GPA, promotion status and remarks.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from students.models import Student
        from .services import build_student_report_card, user_can_access_student_report

        student = get_object_or_404(Student.objects.select_related("profile"), id=student_id)

        if not user_can_access_student_report(request, student):
            return Response(
                {"error": "You are not authorized to view this student's results."},
                status=status.HTTP_403_FORBIDDEN,
            )

        academic_year = request.query_params.get("academic_year")
        report_card = build_student_report_card(student, academic_year=academic_year)
        return Response(report_card)


class StudentTranscriptView(APIView):
    """
    Renders multi-year academic transcript for the student across all eligible
    academic years in chronological order.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from students.models import Student
        from .services import build_student_transcript, user_can_access_student_report

        student = get_object_or_404(Student.objects.select_related("profile"), id=student_id)

        if not user_can_access_student_report(request, student):
            return Response(
                {"error": "You are not authorized to view this student's transcript."},
                status=status.HTTP_403_FORBIDDEN,
            )

        transcript_data = build_student_transcript(student)
        return Response(transcript_data)



class BelowPassingReportView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_exam_reports")]

    def get(self, request):
        examination_id = request.query_params.get("examination")
        if not examination_id:
            return Response({"error": "examination query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        examination = get_object_or_404(Examination, id=examination_id)
        results = ExamResult.objects.filter(examination=examination, is_pass=False).select_related(
            "student__profile"
        )

        return Response(
            {
                "examination": str(examination.id),
                "students": [
                    {
                        "student": str(r.student_id),
                        "full_name": f"{r.student.profile.first_name} {r.student.profile.last_name}",
                        "enrollment_id": r.student.enrollment_id,
                        "percentage": float(r.percentage),
                    }
                    for r in results
                ],
            }
        )


class ExamMarkGraceView(APIView):
    """POST /api/examinations/marks/<id>/grace/ {grace_marks, reason} - sets grace marks on one mark."""

    permission_classes = [IsAuthenticated, HasPermission("manage_marks")]

    def post(self, request, mark_id):
        from decimal import Decimal, InvalidOperation

        from .marks import apply_grace
        from .models import ExamMark
        from .serializers import ExamMarkSerializer

        mark = get_object_or_404(ExamMark.objects.select_related("exam_schedule"), pk=mark_id)
        if not user_can_access_schedule(request, mark.exam_schedule):
            return Response({"error": "You are not authorized to change this mark."}, status=status.HTTP_403_FORBIDDEN)
        try:
            grace = Decimal(str(request.data.get("grace_marks", ""))).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return Response({"grace_marks": ["Enter grace marks as a number."]}, status=status.HTTP_400_BAD_REQUEST)
        before = mark.grace_marks
        mark = apply_grace(mark, grace, request.data.get("reason", ""), request.user.id)
        log_action(
            request, action="grace_marks_set", model_name="ExamMark", object_id=mark.id,
            changes={"from": str(before), "to": str(mark.grace_marks)},
        )
        return Response(ExamMarkSerializer(mark).data)


class RecheckViewSet(viewsets.GenericViewSet):
    """Recheck requests. A student asks about their own mark; staff with view_results or manage_marks ask for any
    mark they can see. Only manage_marks decides. Lists show everything to manage_marks, and otherwise only the
    requests the person made."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        from .models import RecheckRequest

        qs = RecheckRequest.objects.select_related(
            "mark__student__profile", "mark__exam_schedule__subject", "mark__exam_schedule__examination"
        )
        if not HasPermission("manage_marks").has_permission(self.request, None):
            qs = qs.filter(requested_by_user_id=self.request.user.id)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def list(self, request):
        from .serializers import RecheckRequestSerializer

        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(RecheckRequestSerializer(page, many=True).data)

    def create(self, request):
        from .marks import request_recheck
        from .models import ExamMark
        from .serializers import RecheckRequestSerializer

        own = get_student_for_user(request.user)
        marks = ExamMark.objects.select_related("student", "exam_schedule")
        try:
            if request.data.get("mark"):
                mark = marks.get(pk=request.data["mark"])
            else:
                # From a result page: examination + subject, and the student (staff) or oneself (a student).
                mark = marks.get(
                    exam_schedule__examination_id=request.data.get("examination"),
                    exam_schedule__subject_id=request.data.get("subject"),
                    student_id=own.id if own is not None else request.data.get("student"),
                )
        except (ExamMark.DoesNotExist, ExamMark.MultipleObjectsReturned, ValueError, DjangoValidationError):
            return Response({"error": "That mark was not found."}, status=status.HTTP_404_NOT_FOUND)
        if own is not None:
            if own.id != mark.student_id:
                return Response({"error": "You can ask for a recheck of your own marks only."}, status=status.HTTP_403_FORBIDDEN)
        elif not (HasPermission("view_results").has_permission(request, None) or HasPermission("manage_marks").has_permission(request, None)):
            return Response({"error": "You do not have permission to ask for a recheck."}, status=status.HTTP_403_FORBIDDEN)
        elif not user_can_access_student_result(request, mark.student):
            return Response({"error": "You are not authorized to see this student's marks."}, status=status.HTTP_403_FORBIDDEN)
        recheck = request_recheck(mark, request.data.get("reason", ""), request.user.id)
        log_action(request, action="recheck_requested", model_name="RecheckRequest", object_id=recheck.id,
                   changes={"mark": str(mark.id)})
        _tell_markers(recheck)
        return Response(RecheckRequestSerializer(recheck).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        from decimal import Decimal, InvalidOperation

        from .marks import decide_recheck
        from .models import RecheckRequest
        from .serializers import RecheckRequestSerializer

        if not HasPermission("manage_marks").has_permission(request, None):
            return Response({"error": "You do not have permission to decide rechecks."}, status=status.HTTP_403_FORBIDDEN)
        recheck = get_object_or_404(RecheckRequest.objects.select_related("mark__exam_schedule"), pk=pk)
        if not user_can_access_schedule(request, recheck.mark.exam_schedule):
            return Response({"error": "You are not authorized to change this mark."}, status=status.HTTP_403_FORBIDDEN)
        decision = request.data.get("decision")
        if decision not in ("accept", "reject"):
            return Response({"decision": ["Choose accept or reject."]}, status=status.HTTP_400_BAD_REQUEST)
        revised = request.data.get("revised_marks")
        if decision == "accept" and revised not in (None, ""):
            try:
                revised = Decimal(str(revised)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                return Response({"revised_marks": ["Enter the marks as a number."]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            revised = None
        recheck = decide_recheck(recheck, accept=decision == "accept", revised_marks=revised,
                                 comment=request.data.get("decision_comment", ""), user_id=request.user.id)
        log_action(request, action=f"recheck_{recheck.status}", model_name="RecheckRequest", object_id=recheck.id,
                   changes={"original": str(recheck.original_marks), "revised": str(recheck.revised_marks)})
        _tell_requester(recheck)
        return Response(RecheckRequestSerializer(RecheckRequest.objects.get(pk=recheck.pk)).data)


def _notify_after_commit(user_ids, title, body, link):
    from django.db import transaction

    ids = [i for i in set(user_ids) if i]
    if not ids:
        return

    def send():
        from notifications.services import notify_many

        try:
            notify_many(recipient_user_ids=ids, title=title[:200], body=body[:500], category="examinations", link=link)
        except Exception:  # pragma: no cover - best effort
            pass

    transaction.on_commit(send)


def _tell_markers(recheck):
    from django.db.models import Q

    from roles.models import UserRole

    ids = set(UserRole.objects.filter(Q(role__slug="owner") | Q(role__permissions__codename="manage_marks"))
              .values_list("user_id", flat=True)) - {recheck.requested_by_user_id}
    schedule = recheck.mark.exam_schedule
    _notify_after_commit(ids, f"Recheck asked: {schedule.subject.name}",
                         f"{recheck.mark.student.enrollment_id}: {recheck.reason}", "/dashboard/examinations/rechecks")


def _tell_requester(recheck):
    word = "accepted" if recheck.status == "accepted" else "rejected"
    _notify_after_commit([recheck.requested_by_user_id], f"Your recheck was {word}",
                         recheck.decision_comment or f"Marks: {recheck.revised_marks}", "/dashboard/examinations/rechecks")
