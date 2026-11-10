import logging
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from core.query_params import date_param, model_param
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import HasAnyPermission
from parent_portal.services import get_child_for_parent, get_linked_children, get_parent_for_user
from profiles.models import Profile
from roles.permissions import HasPermission
from staff.models import StaffMember

from .models import PTMSession, PTMSlot
from .serializers import (
    PTMSessionSerializer,
    PTMSlotBookingRequestSerializer,
    PTMSlotFeedbackRequestSerializer,
    PTMSlotSerializer,
)
from .services import (
    block_slot,
    book_slot,
    cancel_booking,
    generate_slots_for_session,
    record_slot_feedback,
    unblock_slot,
)

logger = logging.getLogger(__name__)


def get_staff_for_user(user):
    """Resolve StaffMember for the authenticated user, or None."""
    if not user or not user.is_authenticated:
        return None
    profile = Profile.objects.filter(user_id=user.id).first()
    return getattr(profile, "staff_record", None) if profile else None


def _is_ptm_admin(request, view):
    """Whether this user may manage every teacher's slots. Django's own has_perm knows nothing about this
    project's roles, so ask the same checker that guards the endpoints."""
    return HasPermission("manage_ptm")().has_permission(request, view)


class PTMSessionViewSet(viewsets.ModelViewSet):
    """
    CRUD for Parent-Teacher Meeting Sessions.
    """

    queryset = (
        PTMSession.objects.all()
        .select_related("level", "section", "academic_year")
        .prefetch_related("teachers__profile")
    )
    serializer_class = PTMSessionSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "roster"]:
            return [IsAuthenticated(), HasPermission("view_ptm")]
        return [IsAuthenticated(), HasPermission("manage_ptm")]

    def get_queryset(self):
        qs = super().get_queryset()
        academic_year = self.request.query_params.get("academic_year")
        level = self.request.query_params.get("level")
        status_filter = self.request.query_params.get("status")
        meeting_date = self.request.query_params.get("meeting_date")

        if academic_year:
            qs = qs.filter(academic_year_id=model_param(self.request, "academic_year", qs.model, "academic_year"))
        if level:
            qs = qs.filter(level_id=model_param(self.request, "level", qs.model, "level"))
        if status_filter:
            qs = qs.filter(status=status_filter)
        if meeting_date:
            qs = qs.filter(meeting_date=date_param(self.request, "meeting_date"))

        return qs

    @action(detail=True, methods=["post"])
    def generate_slots(self, request, pk=None):
        """Manually trigger slot generation for all assigned teachers."""
        session = self.get_object()
        try:
            count = generate_slots_for_session(session)
            return Response(
                {
                    "message": f"Successfully generated {count} slots for session.",
                    "slots_created": count,
                    "total_slots": session.slots.count(),
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """Publish session and auto-generate slots if not already generated."""
        session = self.get_object()
        if session.slots.count() == 0:
            generate_slots_for_session(session)
        session.status = PTMSession.Status.PUBLISHED
        session.save()
        return Response(
            {"message": "Session published successfully.", "status": session.status},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def cancel_session(self, request, pk=None):
        """Cancel the entire session."""
        session = self.get_object()
        session.status = PTMSession.Status.CANCELLED
        session.save()
        return Response(
            {"message": "Session cancelled.", "status": session.status},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def roster(self, request, pk=None):
        """Comprehensive roster of all slots, bookings, and attendance."""
        session = self.get_object()
        slots = (
            session.slots.all()
            .select_related(
                "teacher__profile",
                "student__profile",
                "booked_by_parent__profile",
            )
            .order_by("start_time", "teacher__profile__first_name")
        )
        serializer = PTMSlotSerializer(slots, many=True)
        return Response(
            {
                "session": PTMSessionSerializer(session).data,
                "slots": serializer.data,
            }
        )


class PTMSlotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Slot management, blocking/unblocking, and post-meeting notes.
    """

    queryset = (
        PTMSlot.objects.all()
        .select_related(
            "session",
            "teacher__profile",
            "student__profile",
            "booked_by_parent__profile",
        )
    )
    serializer_class = PTMSlotSerializer

    def get_permissions(self):
        # Slots carry other families' bookings and the teacher's private notes, so a login alone is not enough.
        if self.action in ["block", "unblock", "feedback"]:
            return [IsAuthenticated(), HasAnyPermission("manage_ptm", "record_ptm_feedback")]
        return [IsAuthenticated(), HasPermission("view_ptm")]

    def get_queryset(self):
        qs = super().get_queryset()
        session_id = self.request.query_params.get("session_id")
        teacher_id = self.request.query_params.get("teacher_id")
        slot_status = self.request.query_params.get("status")

        if session_id:
            qs = qs.filter(session_id=model_param(self.request, "session_id", qs.model, "session"))
        if teacher_id:
            qs = qs.filter(teacher_id=model_param(self.request, "teacher_id", qs.model, "teacher"))
        if slot_status:
            qs = qs.filter(status=slot_status)

        return qs

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        """Teacher blocks an available slot."""
        slot = self.get_object()
        staff_member = get_staff_for_user(request.user)
        is_admin = _is_ptm_admin(request, self)
        try:
            updated = block_slot(slot.id, teacher_member=staff_member, is_admin=is_admin)
            return Response(PTMSlotSerializer(updated).data)
        except (ValidationError, PermissionDenied) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        """Teacher unblocks a slot."""
        slot = self.get_object()
        staff_member = get_staff_for_user(request.user)
        is_admin = _is_ptm_admin(request, self)
        try:
            updated = unblock_slot(slot.id, teacher_member=staff_member, is_admin=is_admin)
            return Response(PTMSlotSerializer(updated).data)
        except (ValidationError, PermissionDenied) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def feedback(self, request, pk=None):
        """Teacher records discussion feedback, attendance, and action items."""
        slot = self.get_object()
        serializer = PTMSlotFeedbackRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        staff_member = get_staff_for_user(request.user)
        is_admin = _is_ptm_admin(request, self)

        try:
            updated = record_slot_feedback(
                slot_id=slot.id,
                teacher_member=staff_member,
                feedback=serializer.validated_data.get("feedback", ""),
                attended=serializer.validated_data.get("attended", True),
                is_admin=is_admin,
            )
            return Response(PTMSlotSerializer(updated).data)
        except (ValidationError, PermissionDenied) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TeacherScheduleView(APIView):
    """
    Returns upcoming meeting roster for the authenticated teacher.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        staff_member = get_staff_for_user(request.user)
        if not staff_member:
            return Response(
                {"error": "Only staff/instructors can access teacher schedule."},
                status=status.HTTP_403_FORBIDDEN,
            )

        slots = (
            PTMSlot.objects.filter(teacher=staff_member)
            .select_related(
                "session",
                "student__profile",
                "booked_by_parent__profile",
            )
            .order_by("-session__meeting_date", "start_time")
        )

        serializer = PTMSlotSerializer(slots, many=True)
        return Response(
            {
                "teacher": {
                    "id": str(staff_member.id),
                    "full_name": f"{staff_member.profile.first_name} {staff_member.profile.last_name}",
                    "designation": staff_member.designation,
                },
                "slots": serializer.data,
            }
        )


# =============================================================================
# Parent Portal PTM Views
# =============================================================================

class ParentPTMSessionsView(APIView):
    """
    Returns published PTM sessions applicable to the caller's linked children.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_child_ptm")]

    def get(self, request):
        parent = get_parent_for_user(request.user)
        if not parent:
            return Response(
                {"error": "Parent portal access is not available for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        linked = get_linked_children(parent)
        student_level_ids = set()
        for rel in linked:
            enrollments = getattr(rel.student, "current_enrollment_list", None) or []
            if enrollments and enrollments[0].level_id:
                student_level_ids.add(enrollments[0].level_id)

        # Include school-wide sessions (level is NULL) and sessions matching children's grades
        qs = (
            PTMSession.objects.filter(status=PTMSession.Status.PUBLISHED)
            .filter(Q(level__isnull=True) | Q(level_id__in=student_level_ids))
            .select_related("level", "section", "academic_year")
            .prefetch_related("teachers__profile")
            .order_by("meeting_date", "start_time")
        )

        return Response(PTMSessionSerializer(qs, many=True).data)


class ParentAvailableSlotsView(APIView):
    """
    Returns available and booked slots for a given session and child,
    allowing the parent to select a teacher and convenient time slot.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_child_ptm")]

    def get(self, request):
        parent = get_parent_for_user(request.user)
        if not parent:
            return Response(
                {"error": "Parent portal access is not available for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        session_id = request.query_params.get("session_id")
        student_id = request.query_params.get("student_id")

        if not session_id or not student_id:
            return Response(
                {"error": "Both session_id and student_id query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student = get_child_for_parent(parent, student_id)
        if not student:
            return Response(
                {"error": "You do not have access to this child."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            session = PTMSession.objects.get(
                id=model_param(request, "session_id", PTMSession), status=PTMSession.Status.PUBLISHED
            )
        except PTMSession.DoesNotExist:
            return Response(
                {"error": "PTM session not found or not published."},
                status=status.HTTP_404_NOT_FOUND,
            )

        slots = (
            session.slots.all()
            .select_related("teacher__profile", "student__profile")
            .order_by("start_time", "teacher__profile__first_name")
        )

        slots_data = []
        for slot in slots:
            is_mine = slot.student_id == student.id
            slots_data.append(
                {
                    "id": str(slot.id),
                    "start_time": slot.start_time.strftime("%H:%M"),
                    "end_time": slot.end_time.strftime("%H:%M"),
                    "status": slot.status,
                    "is_booked_for_this_child": is_mine,
                    "teacher": {
                        "id": str(slot.teacher.id),
                        "full_name": f"{slot.teacher.profile.first_name} {slot.teacher.profile.last_name}",
                        "designation": slot.teacher.designation,
                        "department": slot.teacher.department,
                    },
                    "parent_notes": slot.parent_notes if is_mine else "",
                }
            )

        return Response(
            {
                "session": PTMSessionSerializer(session).data,
                "child": {
                    "id": str(student.id),
                    "full_name": f"{student.profile.first_name} {student.profile.last_name}",
                    "enrollment_id": student.enrollment_id,
                },
                "slots": slots_data,
            }
        )


class ParentBookSlotView(APIView):
    """
    Endpoint for a parent to book an available PTM slot for their child.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_child_ptm")]

    def post(self, request):
        parent = get_parent_for_user(request.user)
        if not parent:
            return Response(
                {"error": "Parent portal access is not available for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PTMSlotBookingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student_id = serializer.validated_data["student_id"]
        slot_id = serializer.validated_data["slot_id"]
        notes = serializer.validated_data.get("notes", "")

        student = get_child_for_parent(parent, student_id)
        if not student:
            return Response(
                {"error": "You do not have access to this child."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            slot = book_slot(
                slot_id=slot_id,
                student=student,
                parent=parent,
                notes=notes,
            )
            return Response(
                {
                    "message": "Slot booked successfully.",
                    "slot": PTMSlotSerializer(slot).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ParentCancelBookingView(APIView):
    """
    Endpoint for a parent to cancel their child's PTM slot booking.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_child_ptm")]

    def post(self, request):
        parent = get_parent_for_user(request.user)
        if not parent:
            return Response(
                {"error": "Parent portal access is not available for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        slot_id = request.data.get("slot_id")
        if not slot_id:
            return Response(
                {"error": "slot_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            slot = cancel_booking(slot_id=slot_id, parent=parent, is_admin=False)
            return Response(
                {"message": "Booking cancelled successfully.", "slot_id": str(slot.id)},
                status=status.HTTP_200_OK,
            )
        except (ValidationError, PermissionDenied) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ParentMyBookingsView(APIView):
    """
    List all active and past PTM bookings for this parent's linked children.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_child_ptm")]

    def get(self, request):
        parent = get_parent_for_user(request.user)
        if not parent:
            return Response(
                {"error": "Parent portal access is not available for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        slots = (
            PTMSlot.objects.filter(booked_by_parent=parent)
            .select_related(
                "session",
                "teacher__profile",
                "student__profile",
            )
            .order_by("-session__meeting_date", "start_time")
        )

        return Response(PTMSlotSerializer(slots, many=True).data)
