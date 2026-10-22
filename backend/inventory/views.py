from decimal import Decimal

from django.db import connection
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from . import services
from .models import Item, ItemCategory, StockLevel, StockLocation, StockMovement
from .serializers import (
    AdjustSerializer,
    IssueSerializer,
    ItemCategorySerializer,
    ItemSerializer,
    ReceiveSerializer,
    ReturnSerializer,
    ReverseSerializer,
    StockLevelSerializer,
    StockLocationSerializer,
    StockMovementSerializer,
    TransferSerializer,
    WriteOffSerializer,
)

Kind = StockMovement.Kind


class InventoryBaseViewSet(viewsets.GenericViewSet):
    pagination_class = StandardResultsPagination
    read_permission = "view_inventory"
    write_permission = "manage_inventory_items"

    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), HasPermission(self.read_permission)]
        return [IsAuthenticated(), HasPermission(self.write_permission)]


class ConfigViewSet(InventoryBaseViewSet, viewsets.ModelViewSet):
    """Create/read/update/delete for the small configuration tables (categories, locations)."""

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {"error": "This record is in use and cannot be deleted. Deactivate it instead where possible."},
                status=status.HTTP_409_CONFLICT,
            )
        log_action(request, action="inventory_deleted", model_name=type(instance).__name__, object_id=kwargs.get("pk"))
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        instance = serializer.save()
        log_action(self.request, action="inventory_created", model_name=type(instance).__name__, object_id=instance.pk)

    def perform_update(self, serializer):
        instance = serializer.save()
        log_action(self.request, action="inventory_updated", model_name=type(instance).__name__, object_id=instance.pk)


class ItemCategoryViewSet(ConfigViewSet):
    serializer_class = ItemCategorySerializer
    queryset = ItemCategory.objects.all()
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]


class StockLocationViewSet(ConfigViewSet):
    serializer_class = StockLocationSerializer
    queryset = StockLocation.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class ItemViewSet(ConfigViewSet):
    """Items are never deleted (they keep history): switch ``is_active`` off instead."""

    serializer_class = ItemSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["category", "is_active"]
    search_fields = ["name", "sku"]
    ordering_fields = ["name", "sku", "created_at"]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Item.objects.select_related("category").annotate(
            on_hand=Coalesce(
                Sum("levels__quantity"), Value(Decimal("0")),
                output_field=DecimalField(max_digits=14, decimal_places=3),
            )
        )
        if self.request.query_params.get("low_stock", "").lower() in ("1", "true", "yes"):
            queryset = queryset.filter(is_active=True, reorder_level__gt=0, on_hand__lte=F("reorder_level"))
        return queryset.order_by("name", "sku")


class StockLevelViewSet(InventoryBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = StockLevelSerializer
    queryset = StockLevel.objects.select_related("item", "location")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["item", "location"]
    search_fields = ["item__name", "item__sku"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("hide_empty", "").lower() in ("1", "true", "yes"):
            queryset = queryset.filter(~Q(quantity=0))
        return queryset


class StockMovementViewSet(InventoryBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Read the ledger; every change is a POST to one of the actions below."""

    serializer_class = StockMovementSerializer
    queryset = StockMovement.objects.select_related("item", "location", "reversal")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["item", "location", "kind", "transfer_group"]
    search_fields = ["item__name", "item__sku", "reference", "reason"]
    ordering_fields = ["created_at"]

    PERMISSIONS = {
        "receive": "receive_stock",
        "issue": "issue_stock",
        "return_stock": "issue_stock",
        "transfer": "issue_stock",
        "adjust": "adjust_stock",
        "write_off": "adjust_stock",
        "reverse": "adjust_stock",
    }

    def get_permissions(self):
        if self.action in self.PERMISSIONS:
            return [IsAuthenticated(), HasPermission(self.PERMISSIONS[self.action])]
        return super().get_permissions()

    def _respond(self, request, movements, action_name):
        movements = movements if isinstance(movements, (list, tuple)) else [movements]
        for movement in movements:
            log_action(
                request, action=action_name, model_name="StockMovement", object_id=movement.pk,
                changes={"item": str(movement.item_id), "location": str(movement.location_id),
                         "delta": str(movement.quantity_delta), "balance_after": str(movement.balance_after)},
            )
        data = StockMovementSerializer(movements, many=True).data
        return Response(data if len(data) > 1 else data[0], status=status.HTTP_201_CREATED)

    def _record(self, request, serializer_class, kind, action_name):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        movement = services.record(kind=kind, user_id=request.user.id, **serializer.validated_data)
        return self._respond(request, movement, action_name)

    @action(detail=False, methods=["post"])
    def receive(self, request):
        return self._record(request, ReceiveSerializer, Kind.RECEIVE, "stock_received")

    @action(detail=False, methods=["post"])
    def issue(self, request):
        return self._record(request, IssueSerializer, Kind.ISSUE, "stock_issued")

    @action(detail=False, methods=["post"], url_path="return")
    def return_stock(self, request):
        return self._record(request, ReturnSerializer, Kind.RETURN, "stock_returned")

    @action(detail=False, methods=["post"], url_path="write-off")
    def write_off(self, request):
        return self._record(request, WriteOffSerializer, Kind.WRITE_OFF, "stock_written_off")

    @action(detail=False, methods=["post"])
    def adjust(self, request):
        serializer = AdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        kind = Kind.ADJUST_IN if data.pop("direction") == "in" else Kind.ADJUST_OUT
        movement = services.record(kind=kind, user_id=request.user.id, **data)
        return self._respond(request, movement, "stock_adjusted")

    @action(detail=False, methods=["post"])
    def transfer(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        out, into = services.transfer(user_id=request.user.id, **serializer.validated_data)
        return self._respond(request, [out, into], "stock_transferred")

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        serializer = ReverseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        movement = services.reverse(self.get_object(), reason=serializer.validated_data["reason"], user_id=request.user.id)
        return self._respond(request, movement, "stock_movement_reversed")
