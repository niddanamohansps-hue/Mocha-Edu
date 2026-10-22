import uuid
from datetime import date

from django.db import connection
from django.db.models import OuterRef, Subquery
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import IsTenantMember
from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission
from staff.models import StaffMember

from . import services
from .models import PayrollSettings, SalaryComponent, StaffSalary, StaffSalaryComponent
from .serializers import (
    AssignComponentSerializer,
    EndComponentSerializer,
    PayrollSettingsSerializer,
    SalaryComponentSerializer,
    SetSalarySerializer,
    StaffSalaryComponentSerializer,
    StaffSalarySerializer,
    structure_to_dict,
)

READ = "view_payroll"
WRITE = "manage_salary_structures"


class PayrollBaseViewSet(viewsets.GenericViewSet):
    """Salary data is sensitive: nothing here is available without a payroll permission, and a school's
    data is never visible in another school (each school has its own schema)."""

    pagination_class = StandardResultsPagination
    READ_ACTIONS = ("list", "retrieve")

    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)

    def get_permissions(self):
        permission = READ if self.action in self.READ_ACTIONS else WRITE
        return [IsAuthenticated(), HasPermission(permission)]


class SalaryComponentViewSet(PayrollBaseViewSet, viewsets.ModelViewSet):
    serializer_class = SalaryComponentSerializer
    queryset = SalaryComponent.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["kind", "is_active"]
    search_fields = ["name", "code"]

    def perform_create(self, serializer):
        component = serializer.save()
        log_action(self.request, action="salary_component_created", model_name="SalaryComponent", object_id=component.pk)

    def perform_update(self, serializer):
        component = serializer.save()
        log_action(self.request, action="salary_component_updated", model_name="SalaryComponent", object_id=component.pk)

    def destroy(self, request, *args, **kwargs):
        component = self.get_object()
        try:
            component.delete()
        except ProtectedError:
            return Response(
                {"error": "This component has been given to staff and cannot be deleted. Deactivate it instead."},
                status=status.HTTP_409_CONFLICT,
            )
        log_action(request, action="salary_component_deleted", model_name="SalaryComponent", object_id=kwargs.get("pk"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffSalaryViewSet(PayrollBaseViewSet, mixins.ListModelMixin):
    """``list`` shows each staff member's salary in force today; ``history`` shows all of one person's.
    Salaries are set (a new row) with POST and never edited or deleted."""

    serializer_class = StaffSalarySerializer
    filter_backends = [SearchFilter]
    search_fields = ["staff__employee_id", "staff__profile__first_name", "staff__profile__last_name"]
    READ_ACTIONS = ("list", "history", "structure")

    def get_queryset(self):
        today = timezone.localdate()
        latest = (
            StaffSalary.objects.filter(staff=OuterRef("staff"), effective_from__lte=today)
            .order_by("-effective_from").values("pk")[:1]
        )
        return (
            StaffSalary.objects.filter(pk=Subquery(latest))
            .select_related("staff__profile")
            .order_by("staff__profile__first_name", "staff__employee_id")
        )

    def create(self, request):
        serializer = SetSalarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        salary = services.set_salary(user_id=request.user.id, **serializer.validated_data)
        log_action(
            request, action="salary_set", model_name="StaffSalary", object_id=salary.pk,
            changes={"staff": str(salary.staff_id), "basic_amount": str(salary.basic_amount),
                     "effective_from": salary.effective_from.isoformat()},
        )
        return Response(StaffSalarySerializer(salary).data, status=status.HTTP_201_CREATED)

    def _staff(self, request):
        raw = request.query_params.get("staff")
        if not raw:
            raise ValidationError({"staff": ["This query parameter is required."]})
        try:
            staff_id = uuid.UUID(str(raw))
        except ValueError:
            raise ValidationError({"staff": ["Not a valid staff id."]})
        staff = StaffMember.objects.select_related("profile").filter(pk=staff_id).first()
        if staff is None:
            raise NotFound("No such staff member.")
        return staff

    @action(detail=False, methods=["get"])
    def history(self, request):
        staff = self._staff(request)
        rows = StaffSalary.objects.filter(staff=staff).select_related("staff__profile")
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(StaffSalarySerializer(page, many=True).data)

    @action(detail=False, methods=["get"])
    def structure(self, request):
        """What the staff member is paid for a full month on ``date`` (default today): the lines and totals."""
        staff = self._staff(request)
        raw_date = request.query_params.get("date")
        try:
            on_date = timezone.localdate() if not raw_date else date.fromisoformat(raw_date)
        except ValueError:
            raise ValidationError({"date": ["Use the format YYYY-MM-DD."]})
        result = services.compute_structure(staff, on_date)
        if result is None:
            raise NotFound("No salary is set for this staff member on that date.")
        return Response(structure_to_dict(result))


class StaffSalaryComponentViewSet(PayrollBaseViewSet, mixins.ListModelMixin):
    serializer_class = StaffSalaryComponentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["staff", "component"]

    def get_queryset(self):
        queryset = StaffSalaryComponent.objects.select_related("component", "staff")
        if self.request.query_params.get("open", "").lower() in ("1", "true", "yes"):
            queryset = queryset.filter(effective_to__isnull=True)
        return queryset

    def get_permissions(self):
        if self.action in ("create", "end"):
            return [IsAuthenticated(), HasPermission(WRITE)]
        return super().get_permissions()

    def create(self, request):
        serializer = AssignComponentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = services.assign_component(user_id=request.user.id, **serializer.validated_data)
        log_action(
            request, action="salary_component_assigned", model_name="StaffSalaryComponent", object_id=assignment.pk,
            changes={"staff": str(assignment.staff_id), "component": str(assignment.component_id)},
        )
        return Response(StaffSalaryComponentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        serializer = EndComponentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = services.end_component(self.get_object(), effective_to=serializer.validated_data["effective_to"],
                                            user_id=request.user.id)
        log_action(request, action="salary_component_ended", model_name="StaffSalaryComponent", object_id=assignment.pk)
        return Response(StaffSalaryComponentSerializer(assignment).data)


class PayrollSettingsView(APIView):
    """GET/PATCH /api/payroll/settings/. GET never writes (no row yet returns the defaults)."""

    http_method_names = ["get", "patch", "head", "options"]

    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)

    def get_permissions(self):
        permission = WRITE if self.request.method == "PATCH" else READ
        return [IsAuthenticated(), IsTenantMember(), HasPermission(permission)]

    def get(self, request):
        return Response(PayrollSettingsSerializer(PayrollSettings.load()).data)

    def patch(self, request):
        serializer = PayrollSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance, previous = PayrollSettings.update_singleton(user_id=request.user.id, **serializer.validated_data)
        log_action(request, action="payroll_settings_changed", model_name="PayrollSettings", object_id=instance.id,
                   changes={"old": previous, "new": instance.editable_values()})
        return Response(PayrollSettingsSerializer(instance).data)
