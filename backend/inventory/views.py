from decimal import Decimal

from django.db import connection
from django.db.models import Count, DecimalField, F, Prefetch, Q, Sum, Value
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

from . import asset_services, services
from .models import (
    Asset,
    AssetAssignment,
    AssetCategory,
    Item,
    ItemCategory,
    Purchase,
    StockLevel,
    StockLocation,
    StockMovement,
    Supplier,
)
from .serializers import (
    AdjustSerializer,
    AssetAssignInputSerializer,
    AssetAssignmentSerializer,
    AssetCategorySerializer,
    AssetCreateSerializer,
    AssetEventSerializer,
    AssetFoundInputSerializer,
    AssetMoveInputSerializer,
    AssetReasonInputSerializer,
    AssetRepairCompleteInputSerializer,
    AssetReturnInputSerializer,
    AssetSerializer,
    MaintenanceRecordSerializer,
    IssueSerializer,
    ItemCategorySerializer,
    ItemSerializer,
    PurchaseCreateSerializer,
    PurchaseSerializer,
    ReceiveSerializer,
    ReturnSerializer,
    ReverseSerializer,
    StockLevelSerializer,
    StockLocationSerializer,
    StockMovementSerializer,
    SupplierSerializer,
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


class SupplierViewSet(ConfigViewSet):
    serializer_class = SupplierSerializer
    queryset = Supplier.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "contact_name", "phone", "email"]


class PurchaseViewSet(InventoryBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Purchases are created (which receives the stock) and cancelled, never edited."""

    serializer_class = PurchaseSerializer
    queryset = Purchase.objects.select_related("supplier", "location").prefetch_related("lines__item")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"supplier": ["exact"], "location": ["exact"], "status": ["exact"],
                        "purchase_date": ["gte", "lte"]}
    search_fields = ["reference", "supplier__name", "lines__item__name", "lines__item__sku"]
    ordering_fields = ["purchase_date", "created_at", "total_cost"]

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), HasPermission("receive_stock")]
        if self.action == "cancel":
            return [IsAuthenticated(), HasPermission("adjust_stock")]
        return super().get_permissions()

    def get_queryset(self):
        return super().get_queryset().distinct()

    def create(self, request):
        serializer = PurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = services.receive_purchase(user_id=request.user.id, **serializer.validated_data)
        log_action(
            request, action="purchase_received", model_name="Purchase", object_id=purchase.pk,
            changes={"supplier": str(purchase.supplier_id), "location": str(purchase.location_id),
                     "total_cost": str(purchase.total_cost), "lines": purchase.lines.count()},
        )
        return Response(PurchaseSerializer(self.get_queryset().get(pk=purchase.pk)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = ReverseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = services.cancel_purchase(self.get_object(), reason=serializer.validated_data["reason"],
                                            user_id=request.user.id)
        log_action(request, action="purchase_cancelled", model_name="Purchase", object_id=purchase.pk,
                   changes={"reason": purchase.cancellation_reason})
        return Response(PurchaseSerializer(self.get_queryset().get(pk=purchase.pk)).data)


class AssetCategoryViewSet(ConfigViewSet):
    serializer_class = AssetCategorySerializer
    queryset = AssetCategory.objects.all()
    read_permission = "view_assets"
    write_permission = "manage_assets"
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]


class AssetViewSet(InventoryBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                   mixins.CreateModelMixin, mixins.UpdateModelMixin):
    """The asset register. Assets are never deleted; status and holder change only through the actions."""

    read_permission = "view_assets"
    write_permission = "manage_assets"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["category", "status", "condition", "location", "supplier"]
    search_fields = ["tag", "name", "serial_number"]
    ordering_fields = ["tag", "name", "purchase_date", "created_at"]
    ACTION_PERMISSIONS = {"assign": "assign_assets", "return_asset": "assign_assets", "move": "assign_assets"}
    READ_ACTIONS = ("history", "assignments", "maintenance", "summary")

    def get_serializer_class(self):
        return AssetCreateSerializer if self.action == "create" else AssetSerializer

    def get_queryset(self):
        open_assignments = AssetAssignment.objects.filter(returned_at__isnull=True).select_related(
            "staff__profile", "location"
        )
        return (
            Asset.objects.select_related("category", "supplier", "location")
            .prefetch_related(Prefetch("assignments", queryset=open_assignments, to_attr="open_assignments"))
            .order_by("tag")
        )

    def get_permissions(self):
        if self.action in self.ACTION_PERMISSIONS:
            return [IsAuthenticated(), HasPermission(self.ACTION_PERMISSIONS[self.action])]
        if self.action in self.READ_ACTIONS:
            return [IsAuthenticated(), HasPermission(self.read_permission)]
        return super().get_permissions()

    def _fresh(self, asset):
        return AssetSerializer(self.get_queryset().get(pk=asset.pk)).data

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = asset_services.register(user_id=request.user.id, **serializer.validated_data)
        log_action(request, action="asset_registered", model_name="Asset", object_id=asset.pk, changes={"tag": asset.tag})
        return Response(self._fresh(asset), status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        asset = serializer.save()
        log_action(self.request, action="asset_updated", model_name="Asset", object_id=asset.pk)

    def _act(self, request, input_serializer, operation, action_name):
        serializer = input_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = operation(self.get_object(), user_id=request.user.id, **serializer.validated_data)
        log_action(request, action=action_name, model_name="Asset", object_id=asset.pk, changes={"status": asset.status})
        return Response(self._fresh(asset))

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        return self._act(request, AssetAssignInputSerializer, asset_services.assign, "asset_assigned")

    @action(detail=True, methods=["post"], url_path="return")
    def return_asset(self, request, pk=None):
        return self._act(request, AssetReturnInputSerializer, asset_services.return_asset, "asset_returned")

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        return self._act(request, AssetMoveInputSerializer, asset_services.move, "asset_moved")

    @action(detail=True, methods=["post"])
    def repair(self, request, pk=None):
        return self._act(request, AssetReasonInputSerializer, asset_services.send_to_repair, "asset_sent_to_repair")

    @action(detail=True, methods=["post"], url_path="complete-repair")
    def complete_repair(self, request, pk=None):
        return self._act(request, AssetRepairCompleteInputSerializer, asset_services.complete_repair, "asset_repaired")

    @action(detail=True, methods=["post"])
    def lost(self, request, pk=None):
        return self._act(request, AssetReasonInputSerializer, asset_services.mark_lost, "asset_marked_lost")

    @action(detail=True, methods=["post"])
    def found(self, request, pk=None):
        return self._act(request, AssetFoundInputSerializer, asset_services.mark_found, "asset_found")

    @action(detail=True, methods=["post"])
    def dispose(self, request, pk=None):
        return self._act(request, AssetReasonInputSerializer, asset_services.dispose, "asset_disposed")

    def _page(self, queryset, serializer_class):
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(serializer_class(page, many=True).data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        return self._page(self.get_object().events.all(), AssetEventSerializer)

    @action(detail=True, methods=["get"])
    def assignments(self, request, pk=None):
        queryset = self.get_object().assignments.select_related("staff__profile", "location")
        return self._page(queryset, AssetAssignmentSerializer)

    @action(detail=True, methods=["get"])
    def maintenance(self, request, pk=None):
        return self._page(self.get_object().maintenance.all(), MaintenanceRecordSerializer)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Counts by status and category, and the purchase cost of everything not disposed of."""
        assets = Asset.objects.all()
        in_service = assets.exclude(status=Asset.Status.DISPOSED)
        by_status = {row["status"]: row["n"] for row in assets.values("status").annotate(n=Count("id"))}
        by_category = in_service.values("category__name").annotate(n=Count("id")).order_by("category__name")
        cost = in_service.aggregate(total=Sum("purchase_cost"))["total"] or Decimal("0")
        return Response({
            "total": assets.count(),
            "by_status": {value: by_status.get(value, 0) for value in Asset.Status.values},
            "by_category": [{"category": row["category__name"], "count": row["n"]} for row in by_category],
            "purchase_cost_in_service": f"{cost:.2f}",
        })
