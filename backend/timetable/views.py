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

from .models import Period, Room, TimetableEntry, TimetableSubstitution
from .serializers import (
    PeriodSerializer,
    RoomSerializer,
    TimetableEntryCreateUpdateSerializer,
    TimetableEntrySerializer,
    TimetableSubstitutionSerializer,
)
from .services import (
    get_instructor_for_user,
    get_staff_member_for_user,
    get_student_for_user,
    is_owner,
    user_can_access_instructor_timetable,
    user_can_access_section,
)


class PeriodViewSet(viewsets.ModelViewSet):
    queryset = Period.objects.all()
    serializer_class = PeriodSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["academic_year", "is_break"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            perm = HasPermission("view_timetable")
        else:
            perm = HasPermission("manage_periods")
        return [IsAuthenticated(), perm]


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            perm = HasPermission("view_timetable")
        else:
            perm = HasPermission("manage_rooms")
        return [IsAuthenticated(), perm]


class TimetableEntryViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["academic_year", "section", "day_of_week"]
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            perm = HasPermission("view_timetable")
        else:
            perm = HasPermission("manage_timetable")
        return [IsAuthenticated(), perm]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TimetableEntryCreateUpdateSerializer
        return TimetableEntrySerializer

    def get_queryset(self):
        qs = TimetableEntry.objects.select_related(
            "section", "subject", "period", "room", "instructor__staff_member__profile"
        )

        if is_owner(self.request) or get_instructor_for_user(self.request.user) is None:
            # Owner, or a non-instructor staff/other role - tenant-wide,
            # consistent with attendance.services.user_can_access_section.
            return qs

        instructor = get_instructor_for_user(self.request.user)
        from academics.models import SubjectAssignment

        allowed_section_ids = SubjectAssignment.objects.filter(instructor=instructor).values_list(
            "section_id", flat=True
        )
        return qs.filter(section_id__in=allowed_section_ids)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        section = serializer.validated_data["section"]
        if not user_can_access_section(request, section.id):
            return Response(
                {"error": "You are not assigned to this section."}, status=status.HTTP_403_FORBIDDEN
            )

        entry = serializer.save()
        log_action(
            request,
            action="timetable_entry_created",
            model_name="TimetableEntry",
            object_id=entry.id,
            changes={
                "section": str(entry.section_id),
                "subject": str(entry.subject_id),
                "day_of_week": entry.day_of_week,
                "period": str(entry.period_id),
                "instructor": str(entry.instructor_id) if entry.instructor_id else None,
            },
        )
        return Response(TimetableEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        if not user_can_access_section(request, instance.section_id):
            return Response(
                {"error": "You are not assigned to this section."}, status=status.HTTP_403_FORBIDDEN
            )

        before = {
            "section": str(instance.section_id),
            "subject": str(instance.subject_id),
            "instructor": str(instance.instructor_id) if instance.instructor_id else None,
            "room": str(instance.room_id) if instance.room_id else None,
        }

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()

        log_action(
            request,
            action="timetable_entry_updated",
            model_name="TimetableEntry",
            object_id=entry.id,
            changes={
                "before": before,
                "after": {
                    "section": str(entry.section_id),
                    "subject": str(entry.subject_id),
                    "instructor": str(entry.instructor_id) if entry.instructor_id else None,
                    "room": str(entry.room_id) if entry.room_id else None,
                },
            },
        )
        return Response(TimetableEntrySerializer(entry).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if not user_can_access_section(request, instance.section_id):
            return Response(
                {"error": "You are not assigned to this section."}, status=status.HTTP_403_FORBIDDEN
            )

        entry_id, section_id = instance.id, instance.section_id
        instance.delete()

        log_action(
            request,
            action="timetable_entry_deleted",
            model_name="TimetableEntry",
            object_id=entry_id,
            changes={"section": str(section_id)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, HasPermission("manage_substitutions")])
    def substitute(self, request, pk=None):
        entry = get_object_or_404(TimetableEntry, pk=pk)

        if not user_can_access_section(request, entry.section_id):
            return Response(
                {"error": "You are not assigned to this section."}, status=status.HTTP_403_FORBIDDEN
            )

        data = dict(request.data)
        data["timetable_entry"] = entry.id
        serializer = TimetableSubstitutionSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        staff_member = get_staff_member_for_user(request.user)
        substitution = serializer.save(created_by=staff_member)

        log_action(
            request,
            action="timetable_substitution_created",
            model_name="TimetableSubstitution",
            object_id=substitution.id,
            changes={
                "timetable_entry": str(entry.id),
                "date": str(substitution.date),
                "substitute_instructor": str(substitution.substitute_instructor_id)
                if substitution.substitute_instructor_id
                else None,
            },
        )
        return Response(TimetableSubstitutionSerializer(substitution).data, status=status.HTTP_201_CREATED)


class TimetableSubstitutionViewSet(viewsets.ModelViewSet):
    queryset = TimetableSubstitution.objects.select_related("timetable_entry", "substitute_instructor")
    serializer_class = TimetableSubstitutionSerializer
    http_method_names = ["get", "post", "delete"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            perm = HasPermission("view_timetable")
        else:
            perm = HasPermission("manage_substitutions")
        return [IsAuthenticated(), perm]

    def perform_create(self, serializer):
        staff_member = get_staff_member_for_user(self.request.user)
        substitution = serializer.save(created_by=staff_member)
        log_action(
            self.request,
            action="timetable_substitution_created",
            model_name="TimetableSubstitution",
            object_id=substitution.id,
            changes={"timetable_entry": str(substitution.timetable_entry_id), "date": str(substitution.date)},
        )

    def perform_destroy(self, instance):
        sub_id, entry_id, date = instance.id, instance.timetable_entry_id, instance.date
        instance.delete()
        log_action(
            self.request,
            action="timetable_substitution_deleted",
            model_name="TimetableSubstitution",
            object_id=sub_id,
            changes={"timetable_entry": str(entry_id), "date": str(date)},
        )


class SectionTimetableView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_timetable")]

    def get(self, request, section_id):
        if not user_can_access_section(request, section_id):
            return Response(
                {"error": "You are not assigned to this section."}, status=status.HTTP_403_FORBIDDEN
            )

        academic_year = request.query_params.get("academic_year")
        qs = TimetableEntry.objects.filter(section_id=section_id).select_related(
            "subject", "period", "room", "instructor__staff_member__profile"
        )
        if academic_year:
            qs = qs.filter(academic_year=academic_year)

        return Response(TimetableEntrySerializer(qs, many=True).data)


class InstructorTimetableView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, instructor_id):
        if not HasPermission("view_timetable").has_permission(request, None):
            return Response(
                {"error": "You do not have permission to view timetables."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not user_can_access_instructor_timetable(request, instructor_id):
            return Response(
                {"error": "You are not authorized to view this instructor's timetable."},
                status=status.HTTP_403_FORBIDDEN,
            )

        academic_year = request.query_params.get("academic_year")
        qs = TimetableEntry.objects.filter(instructor_id=instructor_id).select_related(
            "section", "subject", "period", "room"
        )
        if academic_year:
            qs = qs.filter(academic_year=academic_year)

        return Response(TimetableEntrySerializer(qs, many=True).data)


class MyTimetableView(APIView):
    """
    Convenience endpoint: resolves the caller's own section (student) or
    own instructor record and returns their weekly timetable, so the
    frontend's "My Schedule" page doesn't need to already know an ID.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        academic_year = request.query_params.get("academic_year")

        student = get_student_for_user(request.user)
        if student is not None:
            current = student.enrollments.filter(is_current=True).first()
            if not current or not current.section_id:
                return Response({"role": "student", "results": []})
            qs = TimetableEntry.objects.filter(section_id=current.section_id).select_related(
                "subject", "period", "room", "instructor__staff_member__profile"
            )
            if academic_year:
                qs = qs.filter(academic_year=academic_year)
            return Response({"role": "student", "section": str(current.section_id), "results": TimetableEntrySerializer(qs, many=True).data})

        instructor = get_instructor_for_user(request.user)
        if instructor is not None:
            qs = TimetableEntry.objects.filter(instructor=instructor).select_related(
                "section", "subject", "period", "room"
            )
            if academic_year:
                qs = qs.filter(academic_year=academic_year)
            return Response({"role": "instructor", "results": TimetableEntrySerializer(qs, many=True).data})

        return Response({"role": None, "results": []})
