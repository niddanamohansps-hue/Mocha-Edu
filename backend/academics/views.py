import django_filters
from django_filters import rest_framework as drf_filters
from django.db import IntegrityError, transaction
from django.db.models import Q, ProtectedError
from django.utils import timezone
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from core.audit import log_action
from core.pagination import StandardResultsPagination
from .models import AcademicYear, CalendarEvent, Program, AcademicLevel, Section, Subject, SubjectAssignment
from .serializers import (
    AcademicYearSerializer,
    CalendarEventSerializer,
    ProgramSerializer,
    AcademicLevelSerializer,
    SectionSerializer,
    SubjectSerializer,
    SubjectAssignmentSerializer,
)
from roles.permissions import HasPermission


PROTECTED_DELETE_MESSAGE = (
    "This record is still referenced by other records (for example students, fees, or announcements) "
    "and cannot be deleted."
)


class ProtectedDeleteMixin:
    """Returns 400 instead of an unhandled 500 when on_delete=PROTECT blocks a delete."""

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({"non_field_errors": [PROTECTED_DELETE_MESSAGE]}, status=status.HTTP_400_BAD_REQUEST)


class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all().prefetch_related("levels__sections")
    serializer_class = ProgramSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_program")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("add_program")]
        if self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("change_program")]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), HasPermission("delete_program")]
        return [permissions.IsAuthenticated(), HasPermission("view_program")]


class AcademicLevelViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = AcademicLevel.objects.all().select_related("program")
    serializer_class = AcademicLevelSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_academic_level")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("add_academic_level")]
        if self.action in ["update", "partial_update"]:
            return [
                permissions.IsAuthenticated(),
                HasPermission("change_academic_level"),
            ]
        if self.action == "destroy":
            return [
                permissions.IsAuthenticated(),
                HasPermission("delete_academic_level"),
            ]
        return [permissions.IsAuthenticated(), HasPermission("view_academic_level")]


class SectionViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Section.objects.all().select_related("level__program")
    serializer_class = SectionSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_section")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("add_section")]
        if self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("change_section")]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), HasPermission("delete_section")]
        return [permissions.IsAuthenticated(), HasPermission("view_section")]


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all().select_related("level")
    serializer_class = SubjectSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_subject")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("add_subject")]
        if self.action in ["update", "partial_update"]:
            return [permissions.IsAuthenticated(), HasPermission("change_subject")]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), HasPermission("delete_subject")]
        return [permissions.IsAuthenticated(), HasPermission("view_subject")]


class SubjectAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectAssignmentSerializer

    def get_queryset(self):
        queryset = SubjectAssignment.objects.all().select_related(
            "section__level__program", "subject__level", "instructor__staff_member__profile"
        )

        instructor_id = self.request.query_params.get("instructor", None)
        section_id = self.request.query_params.get("section", None)

        if instructor_id:
            # Check if it's an Instructor ID or Staff ID.
            # Note: The model has FK to Instructor.
            queryset = queryset.filter(instructor__id=instructor_id)

        if section_id:
            queryset = queryset.filter(section__id=section_id)

        return queryset

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [
                permissions.IsAuthenticated(),
                HasPermission("view_subject_assignment"),
            ]
        if self.action == "create":
            return [
                permissions.IsAuthenticated(),
                HasPermission("add_subject_assignment"),
            ]
        if self.action in ["update", "partial_update"]:
            return [
                permissions.IsAuthenticated(),
                HasPermission("change_subject_assignment"),
            ]
        if self.action == "destroy":
            return [
                permissions.IsAuthenticated(),
                HasPermission("delete_subject_assignment"),
            ]
        return [permissions.IsAuthenticated(), HasPermission("view_subject_assignment")]


class AcademicYearViewSet(viewsets.ModelViewSet):
    """
    Tenant-scoped academic years. Tenant isolation is provided by the schema
    itself (the queryset only sees this school's table). Access reuses the
    academic-structure permission family rather than introducing a new codename.
    """

    serializer_class = AcademicYearSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        queryset = AcademicYear.objects.all()
        is_current = self.request.query_params.get("is_current")
        if is_current is not None:
            queryset = queryset.filter(is_current=is_current.lower() in ("true", "1", "yes"))
        return queryset

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated(), HasPermission("view_academic_level")]
        if self.action == "create":
            return [permissions.IsAuthenticated(), HasPermission("add_academic_level")]
        if self.action in ["update", "partial_update", "set_current"]:
            return [permissions.IsAuthenticated(), HasPermission("change_academic_level")]
        return [permissions.IsAuthenticated(), HasPermission("delete_academic_level")]

    def perform_create(self, serializer):
        year = serializer.save()
        log_action(
            self.request,
            action="academic_year_created",
            model_name="AcademicYear",
            object_id=year.id,
            changes={"name": year.name, "start_date": str(year.start_date), "end_date": str(year.end_date)},
        )

    def perform_update(self, serializer):
        year = serializer.save()
        log_action(
            self.request,
            action="academic_year_updated",
            model_name="AcademicYear",
            object_id=year.id,
            changes={"name": year.name, "start_date": str(year.start_date), "end_date": str(year.end_date)},
        )

    def destroy(self, request, *args, **kwargs):
        year = self.get_object()
        if year.is_current:
            return Response(
                {"non_field_errors": ["The current academic year cannot be deleted. Set another year as current first."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        year_id, name = year.id, year.name
        year.delete()
        log_action(
            request,
            action="academic_year_deleted",
            model_name="AcademicYear",
            object_id=year_id,
            changes={"name": name},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="set-current")
    def set_current(self, request, pk=None):
        """
        Atomically makes this year the single current year for the tenant.
        The partial unique index on is_current is the final invariant: if a
        concurrent request wins the race, IntegrityError is mapped to a 409.
        """
        target = self.get_object()
        if target.is_current:
            return Response(AcademicYearSerializer(target).data)

        try:
            with transaction.atomic():
                AcademicYear.objects.select_for_update().filter(is_current=True).exclude(pk=target.pk).update(
                    is_current=False, updated_at=timezone.now()
                )
                AcademicYear.objects.filter(pk=target.pk).update(is_current=True, updated_at=timezone.now())
        except IntegrityError:
            return Response(
                {"non_field_errors": ["Another academic year was set as current at the same time. Please retry."]},
                status=status.HTTP_409_CONFLICT,
            )

        target.refresh_from_db()
        log_action(
            request,
            action="academic_year_set_current",
            model_name="AcademicYear",
            object_id=target.id,
            changes={"name": target.name},
        )
        return Response(AcademicYearSerializer(target).data)


class CalendarEventFilter(drf_filters.FilterSet):
    date = django_filters.DateFilter(method="filter_date")
    start_date = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")
    date_from = django_filters.DateFilter(field_name="end_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")
    is_holiday = django_filters.BooleanFilter(field_name="is_holiday")
    event_type = django_filters.CharFilter(field_name="event_type", lookup_expr="iexact")
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    academic_year = django_filters.UUIDFilter(field_name="academic_year_id")
    month = django_filters.NumberFilter(method="filter_month")
    year = django_filters.NumberFilter(method="filter_year")

    class Meta:
        model = CalendarEvent
        fields = [
            "date",
            "start_date",
            "end_date",
            "date_from",
            "date_to",
            "is_holiday",
            "event_type",
            "status",
            "academic_year",
        ]

    def filter_date(self, queryset, name, value):
        return queryset.filter(start_date__lte=value, end_date__gte=value)

    def filter_month(self, queryset, name, value):
        return queryset.filter(Q(start_date__month=value) | Q(end_date__month=value))

    def filter_year(self, queryset, name, value):
        return queryset.filter(Q(start_date__year=value) | Q(end_date__year=value))

    @property
    def qs(self):
        parent_qs = super().qs
        if hasattr(self, "form") and self.form.is_valid():
            start_date = self.form.cleaned_data.get("start_date")
            end_date = self.form.cleaned_data.get("end_date")
            if start_date and end_date and start_date > end_date:
                raise DRFValidationError({"start_date": ["start_date cannot be after end_date."]})
            date_from = self.form.cleaned_data.get("date_from")
            date_to = self.form.cleaned_data.get("date_to")
            if date_from and date_to and date_from > date_to:
                raise DRFValidationError({"date_from": ["date_from cannot be after date_to."]})
        return parent_qs


class CalendarEventViewSet(viewsets.ModelViewSet):
    queryset = CalendarEvent.objects.all().select_related("academic_year")
    serializer_class = CalendarEventSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [drf_filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CalendarEventFilter
    search_fields = ["title", "description", "location"]
    ordering_fields = ["start_date", "end_date", "title", "created_at"]
    ordering = ["start_date", "start_time", "title", "id"]

    def get_permissions(self):
        if self.action in ["list", "retrieve", "upcoming", "holidays"]:
            return [permissions.IsAuthenticated(), HasPermission("view_calendar_events")]
        return [permissions.IsAuthenticated(), HasPermission("manage_calendar_events")]

    def get_queryset(self):
        user = self.request.user
        queryset = CalendarEvent.objects.all().select_related("academic_year")

        if not user.is_authenticated:
            return queryset.none()

        from roles.models import UserRole
        user_roles = list(UserRole.objects.filter(user=user).select_related("role"))
        has_manage = any(
            ur.role.slug == "owner" or ur.role.permissions.filter(codename="manage_calendar_events").exists()
            for ur in user_roles
        )

        if not has_manage:
            # Non-managers only see published events
            queryset = queryset.filter(status="PUBLISHED")
            is_student_or_parent = any(ur.role.slug in ("student", "parent") for ur in user_roles)
            if is_student_or_parent:
                queryset = queryset.filter(audience__in=["ALL", "STUDENTS"])
            else:
                is_staff_or_instructor = any(ur.role.slug in ("staff", "instructor") for ur in user_roles)
                if is_staff_or_instructor:
                    queryset = queryset.filter(audience__in=["ALL", "STAFF"])

        # Also support X-Academic-Year header if supplied
        academic_year_header = self.request.headers.get("X-Academic-Year")
        if academic_year_header:
            queryset = queryset.filter(academic_year_id=academic_year_header)

        return queryset.order_by("start_date", "start_time", "title", "id")

    def perform_create(self, serializer):
        event = serializer.save(
            created_by_id=self.request.user.id if self.request.user.is_authenticated else None,
            created_by_username=self.request.user.username if self.request.user.is_authenticated else None,
        )
        log_action(
            self.request,
            action="calendar_event_created",
            model_name="CalendarEvent",
            object_id=event.id,
            changes={
                "title": event.title,
                "event_type": event.event_type,
                "start_date": str(event.start_date),
                "end_date": str(event.end_date),
                "status": event.status,
            },
        )

    def perform_update(self, serializer):
        event = serializer.save()
        log_action(
            self.request,
            action="calendar_event_updated",
            model_name="CalendarEvent",
            object_id=event.id,
            changes={
                "title": event.title,
                "event_type": event.event_type,
                "start_date": str(event.start_date),
                "end_date": str(event.end_date),
                "status": event.status,
            },
        )

    def perform_destroy(self, instance):
        event_id, title = instance.id, instance.title
        instance.delete()
        log_action(
            self.request,
            action="calendar_event_deleted",
            model_name="CalendarEvent",
            object_id=event_id,
            changes={"title": title},
        )

    @action(detail=False, methods=["get"], url_path="upcoming")
    def upcoming(self, request):
        today = timezone.now().date()
        limit = int(request.query_params.get("limit", 10))
        qs = self.get_queryset().filter(end_date__gte=today)[:limit]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="holidays")
    def holidays(self, request):
        qs = self.filter_queryset(self.get_queryset().filter(is_holiday=True))
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        event = self.get_object()
        event.status = "PUBLISHED"
        event.save(update_fields=["status", "updated_at"])
        log_action(
            request,
            action="calendar_event_published",
            model_name="CalendarEvent",
            object_id=event.id,
            changes={"status": "PUBLISHED"},
        )
        return Response(self.get_serializer(event).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        event = self.get_object()
        event.status = "CANCELLED"
        event.save(update_fields=["status", "updated_at"])
        log_action(
            request,
            action="calendar_event_cancelled",
            model_name="CalendarEvent",
            object_id=event.id,
            changes={"status": "CANCELLED"},
        )
        return Response(self.get_serializer(event).data)

