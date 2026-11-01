from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
