import re

from django.db import connection
from django.db.models.deletion import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from core.dates import school_today
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from . import services
from .models import Driver, Route, RouteStop, StudentTransport, TransportBill, Vehicle
from .serializers import (
    AssignInputSerializer,
    BillRunSerializer,
    DriverSerializer,
    EndInputSerializer,
    RouteSerializer,
    RouteStopSerializer,
    StudentTransportSerializer,
    TransportBillSerializer,
    VehicleSerializer,
)

VIEW = "view_transport"
MANAGE = "manage_transport"
ASSIGN = "assign_transport"
BILL = "bill_transport"

STUDENT_SEARCH = ["student__enrollment_id", "student__profile__first_name", "student__profile__last_name"]


class TransportBaseViewSet(viewsets.GenericViewSet):
    """Nothing here is available without a transport permission; a school's data never shows in another
    school (each school has its own schema)."""

    pagination_class = StandardResultsPagination
    READ_ACTIONS = ("list", "retrieve")
    WRITE_PERMISSION = MANAGE

    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)

    def get_permissions(self):
        permission = VIEW if self.action in self.READ_ACTIONS else self.WRITE_PERMISSION
        return [IsAuthenticated(), HasPermission(permission)]


class CrudViewSet(TransportBaseViewSet, viewsets.ModelViewSet):
    """Create/update/delete with an audit entry; a record already in use is refused with 409."""

    audit_name = ""
    in_use_message = "This record is in use and cannot be deleted."

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, action=f"{self.audit_name}_created", model_name=type(obj).__name__, object_id=obj.pk)

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, action=f"{self.audit_name}_updated", model_name=type(obj).__name__, object_id=obj.pk)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        model_name, pk = type(obj).__name__, obj.pk
        try:
            obj.delete()
        except ProtectedError:
            return Response({"error": self.in_use_message}, status=status.HTTP_409_CONFLICT)
        log_action(request, action=f"{self.audit_name}_deleted", model_name=model_name, object_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleViewSet(CrudViewSet):
    serializer_class = VehicleSerializer
    queryset = Vehicle.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["registration_number", "name", "make_model"]
    audit_name = "vehicle"
    in_use_message = "This vehicle is used by a route and cannot be deleted. Switch it off instead."


class DriverViewSet(CrudViewSet):
    serializer_class = DriverSerializer
    queryset = Driver.objects.select_related("staff__profile")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active", "role"]
    search_fields = ["full_name", "phone", "license_number"]
    audit_name = "driver"
    in_use_message = "This person is on a route and cannot be deleted. Switch them off instead."


class RouteViewSet(CrudViewSet):
    serializer_class = RouteSerializer
    queryset = Route.objects.select_related("vehicle", "driver", "helper")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active", "vehicle"]
    search_fields = ["name"]
    audit_name = "route"
    in_use_message = "This route has students or bills and cannot be deleted. Switch it off instead."
    READ_ACTIONS = ("list", "retrieve", "students")

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        """Everyone currently seated on this route, in stop order."""
        route = self.get_object()
        seats = (
            StudentTransport.objects.filter(route=route, end_date__isnull=True)
            .select_related("student__profile", "route", "stop")
            .order_by("stop__sequence", "student__profile__first_name")
        )
        return Response(StudentTransportSerializer(seats, many=True).data)


class RouteStopViewSet(CrudViewSet):
    serializer_class = RouteStopSerializer
    queryset = RouteStop.objects.select_related("route")
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["route"]
    audit_name = "route_stop"
    in_use_message = "Students have used this stop and it cannot be deleted. Set its fee to 0 or move the students."
    pagination_class = None


class StudentTransportViewSet(TransportBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Seats. Create one (or move a student) with POST; end one with POST ``{id}/end/``. Never edited or deleted."""

    serializer_class = StudentTransportSerializer
    WRITE_PERMISSION = ASSIGN
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["student", "stop", "route", "mode"]
    search_fields = STUDENT_SEARCH

    def get_queryset(self):
        queryset = StudentTransport.objects.select_related("student__profile", "route", "stop")
        params = self.request.query_params
        if params.get("open") in ("true", "false"):
            queryset = queryset.filter(end_date__isnull=params["open"] == "true")
        return queryset

    def create(self, request):
        serializer = AssignInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        seat = services.assign_student(user_id=request.user.id, **serializer.validated_data)
        log_action(
            request, action="transport_seat_assigned", model_name="StudentTransport", object_id=seat.pk,
            changes={"student": str(seat.student_id), "route": str(seat.route_id),
                     "stop": str(seat.stop_id) if seat.stop_id else None, "mode": seat.mode,
                     "start_date": seat.start_date.isoformat()},
        )
        seat = self.get_queryset().get(pk=seat.pk)
        return Response(StudentTransportSerializer(seat).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        seat = self.get_object()
        serializer = EndInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        end_date = serializer.validated_data.get("end_date") or school_today()
        seat = services.end_assignment(assignment=seat, end_date=end_date)
        log_action(
            request, action="transport_seat_ended", model_name="StudentTransport", object_id=seat.pk,
            changes={"end_date": end_date.isoformat()},
        )
        return Response(StudentTransportSerializer(self.get_queryset().get(pk=seat.pk)).data)


class TransportBillViewSet(TransportBaseViewSet, mixins.ListModelMixin):
    """Bills made by the monthly run. ``POST run/`` bills a month; filter the list with ``?month=YYYY-MM``."""

    serializer_class = TransportBillSerializer
    WRITE_PERMISSION = BILL
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["student"]
    search_fields = STUDENT_SEARCH

    def get_queryset(self):
        queryset = TransportBill.objects.select_related("student__profile", "route", "stop")
        month = self.request.query_params.get("month")
        if month:
            match = re.fullmatch(r"(\d{4})-(\d{2})", month)
            if not match:
                raise ValidationError({"month": "Use the form YYYY-MM, like 2026-10."})
            first, _ = services.month_bounds(int(match.group(1)), int(match.group(2)))
            queryset = queryset.filter(month=first)
        return queryset

    @action(detail=False, methods=["post"])
    def run(self, request):
        serializer = BillRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        year, month = serializer.validated_data["month"]
        summary = services.bill_month(
            year=year, month=month, due_date=serializer.validated_data.get("due_date"), user_id=request.user.id
        )
        log_action(request, action="transport_billed", model_name="TransportBill", object_id=None, changes=summary)
        return Response(summary)


class ExpiringDocumentsView(APIView):
    """Insurance, fitness and licence dates that have passed or are coming up (``?days=30``)."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission(VIEW)]

    def get(self, request):
        if connection.schema_name == "public":
            raise NotFound()
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            raise ValidationError({"days": "Enter a whole number of days."})
        if not 0 <= days <= 365:
            raise ValidationError({"days": "Choose from 0 to 365 days."})
        return Response(services.expiring_documents(days=days))
