from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Sum
from rest_framework import serializers

from staff.models import StaffMember

from .models import (
    Asset,
    AssetAssignment,
    AssetCategory,
    AssetEvent,
    Item,
    ItemCategory,
    MaintenanceRecord,
    Purchase,
    PurchaseLine,
    StockLevel,
    StockLocation,
    StockMovement,
    Supplier,
)

QUANTITY_INPUT = {"max_digits": 12, "decimal_places": 3, "min_value": Decimal("0.001")}


class ItemCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCategory
        fields = ("id", "name", "description", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class StockLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockLocation
        fields = ("id", "name", "description", "room", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    on_hand = serializers.SerializerMethodField()
    low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            "id", "sku", "name", "category", "category_name", "unit", "description", "reorder_level",
            "is_active", "on_hand", "low_stock", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    @staticmethod
    def _on_hand(item):
        """The list queryset annotates ``on_hand``; after a create/update the item is not annotated, so
        it is read from the levels instead of being reported as zero."""
        value = getattr(item, "on_hand", None)
        if value is None:
            value = item.levels.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        return value

    def get_on_hand(self, item):
        return f"{self._on_hand(item):.3f}"

    def get_low_stock(self, item):
        return bool(item.is_active and item.reorder_level > 0 and self._on_hand(item) <= item.reorder_level)


class StockLevelSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = StockLevel
        fields = ("id", "item", "item_name", "item_sku", "unit", "location", "location_name", "quantity", "updated_at")
        read_only_fields = fields


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    reversed = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = (
            "id", "item", "item_name", "location", "location_name", "kind", "quantity_delta", "balance_after",
            "unit_cost", "reason", "reference", "issued_to_staff", "issued_to_note", "transfer_group",
            "reverses", "reversed", "recorded_by_user_id", "created_at",
        )
        read_only_fields = fields

    def get_reversed(self, movement):
        return hasattr(movement, "reversal")


class _MovementInput(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())
    location = serializers.PrimaryKeyRelatedField(queryset=StockLocation.objects.all())
    quantity = serializers.DecimalField(**QUANTITY_INPUT)
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class ReceiveSerializer(_MovementInput):
    unit_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True, default=None
    )
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class IssueSerializer(_MovementInput):
    issued_to_staff = serializers.PrimaryKeyRelatedField(
        queryset=StaffMember.objects.all(), required=False, allow_null=True, default=None
    )
    issued_to_note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ReturnSerializer(_MovementInput):
    issued_to_staff = serializers.PrimaryKeyRelatedField(
        queryset=StaffMember.objects.all(), required=False, allow_null=True, default=None
    )
    issued_to_note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class AdjustSerializer(_MovementInput):
    direction = serializers.ChoiceField(choices=("in", "out"))
    reason = serializers.CharField(max_length=255)


class WriteOffSerializer(_MovementInput):
    reason = serializers.CharField(max_length=255)


class TransferSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())
    from_location = serializers.PrimaryKeyRelatedField(queryset=StockLocation.objects.all())
    to_location = serializers.PrimaryKeyRelatedField(queryset=StockLocation.objects.all())
    quantity = serializers.DecimalField(**QUANTITY_INPUT)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class ReverseSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ("id", "name", "contact_name", "phone", "email", "address", "notes", "is_active",
                  "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class PurchaseLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseLine
        fields = ("id", "item", "item_name", "item_sku", "quantity", "unit_cost", "line_total", "movement")
        read_only_fields = fields

    def get_line_total(self, line):
        return f"{(line.quantity * line.unit_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}"


class PurchaseSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    lines = PurchaseLineSerializer(many=True, read_only=True)

    class Meta:
        model = Purchase
        fields = ("id", "supplier", "supplier_name", "location", "location_name", "reference", "purchase_date",
                  "notes", "status", "total_cost", "cancelled_at", "cancellation_reason", "lines",
                  "created_by_user_id", "created_at")
        read_only_fields = fields


class PurchaseLineInputSerializer(serializers.Serializer):
    item = serializers.PrimaryKeyRelatedField(queryset=Item.objects.all())
    quantity = serializers.DecimalField(**QUANTITY_INPUT)
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))


class PurchaseCreateSerializer(serializers.Serializer):
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    location = serializers.PrimaryKeyRelatedField(queryset=StockLocation.objects.all())
    purchase_date = serializers.DateField()
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    lines = PurchaseLineInputSerializer(many=True, allow_empty=False, max_length=200)


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ("id", "name", "description", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class AssetAssignmentSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    location_name = serializers.CharField(source="location.name", read_only=True, default=None)

    class Meta:
        model = AssetAssignment
        fields = ("id", "staff", "staff_name", "location", "location_name", "note", "assigned_at",
                  "assigned_by_user_id", "returned_at", "returned_by_user_id", "return_condition")
        read_only_fields = fields

    def get_staff_name(self, assignment):
        if assignment.staff_id is None:
            return None
        profile = assignment.staff.profile
        return f"{profile.first_name} {profile.last_name}".strip()


class AssetSerializer(serializers.ModelSerializer):
    """Descriptive fields are editable; status, location and holder change only through the actions."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)
    location_name = serializers.CharField(source="location.name", read_only=True, default=None)
    current_assignment = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = (
            "id", "tag", "name", "category", "category_name", "serial_number", "description", "supplier",
            "supplier_name", "purchase_date", "purchase_cost", "condition", "status", "location", "location_name",
            "current_assignment", "disposed_at", "disposal_reason", "created_at", "updated_at",
        )
        read_only_fields = ("id", "status", "location", "disposed_at", "disposal_reason", "created_at", "updated_at")

    def get_current_assignment(self, asset):
        rows = getattr(asset, "open_assignments", None)
        if rows is None:
            rows = list(asset.assignments.filter(returned_at__isnull=True))
        return AssetAssignmentSerializer(rows[0]).data if rows else None

    def validate_purchase_cost(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("The cost cannot be negative.")
        return value

    def validate(self, attrs):
        if self.instance is not None and "tag" in attrs and attrs["tag"] != self.instance.tag:
            raise serializers.ValidationError({"tag": "An asset tag cannot be changed."})
        return attrs


class AssetCreateSerializer(AssetSerializer):
    """Registration may also place the asset in a location."""

    class Meta(AssetSerializer.Meta):
        read_only_fields = ("id", "status", "disposed_at", "disposal_reason", "created_at", "updated_at")


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceRecord
        fields = ("id", "reason", "opened_at", "opened_by_user_id", "closed_at", "closed_by_user_id", "cost", "notes")
        read_only_fields = fields


class AssetEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetEvent
        fields = ("id", "kind", "from_status", "to_status", "note", "user_id", "created_at")
        read_only_fields = fields


class _OptionalLocation(serializers.Serializer):
    location = serializers.PrimaryKeyRelatedField(
        queryset=StockLocation.objects.all(), required=False, allow_null=True, default=None
    )
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class AssetAssignInputSerializer(_OptionalLocation):
    staff = serializers.PrimaryKeyRelatedField(
        queryset=StaffMember.objects.all(), required=False, allow_null=True, default=None
    )


class AssetReturnInputSerializer(_OptionalLocation):
    condition = serializers.ChoiceField(choices=Asset.Condition.choices, required=False, default=None)


class AssetFoundInputSerializer(_OptionalLocation):
    pass


class AssetMoveInputSerializer(serializers.Serializer):
    location = serializers.PrimaryKeyRelatedField(queryset=StockLocation.objects.all())
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class AssetReasonInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class AssetRepairCompleteInputSerializer(serializers.Serializer):
    cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True, default=None
    )
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    condition = serializers.ChoiceField(choices=Asset.Condition.choices, required=False, default=None)
