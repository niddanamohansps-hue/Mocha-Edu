from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import HasAnyPermission
from roles.permissions import HasPermission
from staff.models import StaffMember

from . import allocation
from .models import Examination, ExamInvigilation, ExamSitting


def _bool(value, default):
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes", "on")


def _int(value, default):
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        raise ValidationError("A number was expected.")


def _fail(exc):
    return ValidationError(str(exc))


class ExamSittingViewSet(viewsets.ViewSet):
    """Rooms and invigilators per sitting. Reading needs view_examinations; changing needs manage_exam_allocation."""

    def get_permissions(self):
        write = self.action in ("sync", "allocate_rooms", "allocate_invigilators", "move_seat")
        return [IsAuthenticated(), HasPermission("manage_exam_allocation" if write else "view_examinations")]

    def _sitting(self, pk):
        return get_object_or_404(ExamSitting.objects.select_related("examination"), pk=pk)

    def list(self, request):
        examination = get_object_or_404(Examination, pk=request.query_params.get("examination"))
        return Response([allocation.sitting_summary(s) for s in ExamSitting.objects.filter(examination=examination)])

    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request):
        examination = get_object_or_404(Examination, pk=request.data.get("examination"))
        return Response([allocation.sitting_summary(s) for s in allocation.sync_sittings(examination)])

    def retrieve(self, request, pk=None):
        return Response(allocation.build_sitting_plan(self._sitting(pk)))

    @action(detail=True, methods=["post"], url_path="allocate-rooms")
    def allocate_rooms(self, request, pk=None):
        sitting = self._sitting(pk)
        try:
            result = allocation.allocate_rooms(
                sitting,
                mix=_bool(request.data.get("mix"), True),
                room_ids=request.data.get("rooms") or None,
                request=request,
            )
        except allocation.AllocationError as exc:
            raise _fail(exc)
        return Response({**result, "plan": allocation.build_sitting_plan(sitting)})

    @action(detail=True, methods=["post"], url_path="move-seat")
    def move_seat(self, request, pk=None):
        sitting = self._sitting(pk)
        try:
            allocation.move_seat(
                sitting, request.data.get("student"), request.data.get("room"), _int(request.data.get("seat"), 0), request
            )
        except allocation.AllocationError as exc:
            raise _fail(exc)
        return Response(allocation.build_sitting_plan(sitting))

    @action(detail=True, methods=["post"], url_path="allocate-invigilators")
    def allocate_invigilators(self, request, pk=None):
        sitting = self._sitting(pk)
        try:
            staff_ids = allocation.allocate_invigilators(
                sitting,
                per_room=_int(request.data.get("per_room"), 2),
                avoid_own_class=_bool(request.data.get("avoid_own_class"), True),
                staff_ids=request.data.get("staff") or None,
                include_non_teaching=_bool(request.data.get("include_non_teaching"), False),
                request=request,
            )
        except allocation.AllocationError as exc:
            raise _fail(exc)
        if _bool(request.data.get("notify"), True):
            allocation.notify_invigilators(sitting, staff_ids)
        return Response(allocation.build_sitting_plan(sitting))


class ExamInvigilationViewSet(viewsets.ViewSet):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_exam_allocation")]

    @action(detail=True, methods=["post"], url_path="replace")
    def replace(self, request, pk=None):
        duty = get_object_or_404(ExamInvigilation.objects.select_related("sitting__examination"), pk=pk)
        staff = get_object_or_404(StaffMember.objects.select_related("profile"), pk=request.data.get("staff"))
        try:
            allocation.replace_invigilator(duty, staff, request)
        except allocation.AllocationError as exc:
            raise _fail(exc)
        if _bool(request.data.get("notify"), True):
            allocation.notify_invigilators(duty.sitting, [staff.id])
        return Response(allocation.build_sitting_plan(duty.sitting))


class DutyRosterView(APIView):
    """Every invigilation duty of an examination, for printing the roster."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_examinations")]

    def get(self, request):
        examination = get_object_or_404(Examination, pk=request.query_params.get("examination"))
        return Response(allocation.duty_rows(ExamInvigilation.objects.filter(sitting__examination=examination)))


class MyDutiesView(APIView):
    """The logged-in staff member's own invigilation duties. No extra permission: it only shows their own."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        staff = StaffMember.objects.filter(profile__user_id=request.user.id).first()
        if staff is None:
            return Response([])
        return Response(allocation.duty_rows(ExamInvigilation.objects.filter(staff=staff)))


class AdmitCardsView(APIView):
    """Admit cards for one section of an examination: each student's papers with room and seat."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_examinations")]

    def get(self, request):
        from academics.models import Section

        examination = get_object_or_404(Examination, pk=request.query_params.get("examination"))
        section = get_object_or_404(Section.objects.select_related("level"), pk=request.query_params.get("section"))
        return Response(allocation.build_admit_cards(examination, section))


class MarksProgressView(APIView):
    """How far marks entry has got for an examination, paper by paper."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_examinations")]

    def get(self, request):
        from .progress import schedule_progress

        examination = get_object_or_404(Examination, pk=request.query_params.get("examination"))
        return Response(schedule_progress(examination))


class RankListView(APIView):
    """A merit list for one section, or for a whole class, from the published results."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_results")]

    def get(self, request):
        from academics.models import AcademicLevel, Section

        from .ranking import rank_list

        examination = get_object_or_404(Examination, pk=request.query_params.get("examination"))
        section = (
            get_object_or_404(Section.objects.select_related("level"), pk=request.query_params["section"])
            if request.query_params.get("section") else None
        )
        level = get_object_or_404(AcademicLevel, pk=request.query_params["level"]) if request.query_params.get("level") else None
        try:
            return Response(
                rank_list(
                    examination, section=section, level=level,
                    include_failed=_bool(request.query_params.get("include_failed"), False),
                    top=_int(request.query_params.get("top"), 3),
                )
            )
        except allocation.AllocationError as exc:
            raise _fail(exc)


class MyExamsView(APIView):
    """The logged-in student's announced examinations. Only their own, so no permission beyond being a student here."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .self_service import visible_examinations
        from .services import get_student_for_user

        student = get_student_for_user(request.user)
        return Response(visible_examinations(student) if student else [])


class MyAdmitCardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .self_service import admit_card_for
        from .services import get_student_for_user

        student = get_student_for_user(request.user)
        if student is None:
            raise Http404()
        examination = get_object_or_404(Examination, pk=request.query_params.get("examination"))
        data = admit_card_for(examination, student)
        if data is None:
            raise Http404()  # not announced yet, or no papers: the same answer, so nothing is revealed
        return Response(data)


def _scope(request):
    """The section or class level a request asks about (exactly one is expected by the callers)."""
    from academics.models import AcademicLevel, Section

    params = request.query_params
    section = get_object_or_404(Section.objects.select_related("level"), pk=params["section"]) if params.get("section") else None
    level = get_object_or_404(AcademicLevel, pk=params["level"]) if params.get("level") else None
    return section, level


class _ReportView(APIView):
    """Examination reports for staff with view_exam_reports."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_exam_reports")]

    def _run(self, request, build):
        try:
            return Response(build())
        except allocation.AllocationError as exc:
            raise _fail(exc)


class AnalyticsView(_ReportView):
    def get(self, request):
        from .analytics import exam_analytics

        examination = get_object_or_404(Examination, pk=request.query_params.get("examination"))
        section, level = _scope(request)
        return self._run(request, lambda: exam_analytics(examination, section=section, level=level))


class AnalyticsCompareView(_ReportView):
    def get(self, request):
        from .analytics import compare_examinations

        examination = get_object_or_404(Examination, pk=request.query_params.get("examination"))
        other = get_object_or_404(Examination, pk=request.query_params.get("other"))
        section, level = _scope(request)
        return self._run(request, lambda: compare_examinations(examination, other, section=section, level=level))


class WeakStudentsView(_ReportView):
    def get(self, request):
        from .analytics import weak_students

        examination = get_object_or_404(Examination, pk=request.query_params.get("examination"))
        section, level = _scope(request)
        margin = _int(request.query_params.get("margin"), 5)
        return self._run(request, lambda: weak_students(examination, section=section, level=level, margin=margin))


class _ModerationView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("moderate_exam_marks")]

    def _schedule(self, schedule_id):
        from .models import ExamSchedule

        return get_object_or_404(ExamSchedule.objects.select_related("examination", "subject", "section__level"), pk=schedule_id)

    @staticmethod
    def _options(data):
        return {"method": data.get("method"), "value": data.get("value"), "step": data.get("step", "1"), "below": data.get("below")}


class ModerationPreviewView(_ModerationView):
    """What a moderation would do to this paper's marks. Changes nothing."""

    def post(self, request, schedule_id):
        from .moderation import ModerationError, preview_moderation

        try:
            return Response(preview_moderation(self._schedule(schedule_id), **self._options(request.data)))
        except ModerationError as exc:
            raise _fail(exc)


class ModerationApplyView(_ModerationView):
    """Apply a moderation. Needs a reason; the preview's count guards against marks moving in between."""

    def post(self, request, schedule_id):
        from .moderation import ModerationError, apply_moderation

        data = request.data
        try:
            result = apply_moderation(
                self._schedule(schedule_id), reason=data.get("reason"), user_id=request.user.id, request=request,
                expected_changed=data.get("expected_changed"), **self._options(data),
            )
        except ModerationError as exc:
            raise _fail(exc)
        return Response(result)


class MalpracticeViewSet(viewsets.ViewSet):
    """Malpractice cases. Reporters see and add to the cases they reported; deciders see all and decide."""

    def get_permissions(self):
        if self.action == "decide":
            return [IsAuthenticated(), HasPermission("decide_exam_malpractice")]
        return [IsAuthenticated(), HasAnyPermission("report_exam_malpractice", "decide_exam_malpractice")]

    def _is_decider(self, request):
        return HasPermission("decide_exam_malpractice")().has_permission(request, self)

    def _queryset(self, request):
        from .models import MalpracticeCase

        qs = MalpracticeCase.objects.select_related(
            "examination", "schedule__subject", "schedule__section__level", "student__profile"
        )
        return qs if self._is_decider(request) else qs.filter(reported_by_user_id=request.user.id)

    def list(self, request):
        from .malpractice import case_data

        qs = self._queryset(request)
        for key in ("examination", "status"):
            if request.query_params.get(key):
                qs = qs.filter(**{key: request.query_params[key]})
        return Response([case_data(c) for c in qs])

    def retrieve(self, request, pk=None):
        from .malpractice import case_data

        return Response(case_data(get_object_or_404(self._queryset(request), pk=pk)))

    def create(self, request):
        from students.models import Student

        from .malpractice import MalpracticeError, case_data, report_case
        from .models import ExamSchedule

        data = request.data
        schedule = get_object_or_404(ExamSchedule.objects.select_related("examination", "subject", "section__level"), pk=data.get("schedule"))
        student = get_object_or_404(Student.objects.select_related("profile"), pk=data.get("student"))
        try:
            case = report_case(
                schedule, student, description=data.get("description"), evidence_notes=data.get("evidence_notes", ""),
                user=request.user, request=request,
            )
        except MalpracticeError as exc:
            raise _fail(exc)
        return Response(case_data(self._queryset(request).get(pk=case.pk)), status=201)

    def partial_update(self, request, pk=None):
        from .malpractice import MalpracticeError, case_data, update_case

        case = get_object_or_404(self._queryset(request), pk=pk)
        try:
            update_case(
                case, description=request.data.get("description"), evidence_notes=request.data.get("evidence_notes"),
                user=request.user, is_decider=self._is_decider(request), request=request,
            )
        except MalpracticeError as exc:
            raise _fail(exc)
        return Response(case_data(self._queryset(request).get(pk=case.pk)))

    @action(detail=True, methods=["post"], url_path="decide")
    def decide(self, request, pk=None):
        from .malpractice import MalpracticeError, case_data, decide_case

        case = get_object_or_404(self._queryset(request), pk=pk)
        try:
            decide_case(case, decision=request.data.get("decision"), notes=request.data.get("notes"), user=request.user, request=request)
        except MalpracticeError as exc:
            raise _fail(exc)
        return Response(case_data(self._queryset(request).get(pk=case.pk)))
