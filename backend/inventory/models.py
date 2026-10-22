import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

QUANTITY = {"max_digits": 12, "decimal_places": 3}


class ItemCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "item categories"

    def __str__(self):
        return self.name


class StockLocation(models.Model):
    """A store, cupboard or room where stock is kept. ``room`` optionally ties it to a timetable room."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    room = models.ForeignKey("timetable.Room", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Item(models.Model):
    """A consumable that is counted in stock (chalk, paper, lab chemicals, ...). Never deleted once it
    has history: it is deactivated instead."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(ItemCategory, on_delete=models.PROTECT, related_name="items")
    unit = models.CharField(max_length=20, help_text="Unit of measure, e.g. pcs, box, kg, litre")
    description = models.TextField(blank=True)
    # 0 means "no reorder level": the item is never reported as low.
    reorder_level = models.DecimalField(default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))], **QUANTITY)
    is_active = models.BooleanField(default=True)
    # Set when a low-stock alert was sent for the current dip below the reorder level; cleared when
    # stock is back above it, so one dip produces one alert (see inventory.alerts).
    low_stock_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "sku"]
        constraints = [
            models.CheckConstraint(condition=Q(reorder_level__gte=0), name="inventory_item_reorder_nonneg"),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"


class StockLevel(models.Model):
    """On-hand quantity of one item in one location.

    This row is only ever changed by ``inventory.services`` in the same transaction that writes the
    matching ``StockMovement``, so it always equals the sum of that item+location's movements (a test
    proves it). It exists so the database itself can refuse a negative balance and so concurrent
    issues can queue on a row lock.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="levels")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="levels")
    quantity = models.DecimalField(default=Decimal("0"), **QUANTITY)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["item__name", "location__name"]
        constraints = [
            models.UniqueConstraint(fields=["item", "location"], name="inventory_stocklevel_unique"),
            models.CheckConstraint(condition=Q(quantity__gte=0), name="inventory_stocklevel_nonneg"),
        ]

    def __str__(self):
        return f"{self.item_id} @ {self.location_id}: {self.quantity}"


class StockMovement(models.Model):
    """One immutable change of stock. Mistakes are undone by a reversal movement, never by editing."""

    class Kind(models.TextChoices):
        RECEIVE = "receive", "Received"
        ISSUE = "issue", "Issued"
        RETURN = "return", "Returned"
        ADJUST_IN = "adjust_in", "Adjusted up"
        ADJUST_OUT = "adjust_out", "Adjusted down"
        WRITE_OFF = "write_off", "Written off"
        TRANSFER_OUT = "transfer_out", "Transferred out"
        TRANSFER_IN = "transfer_in", "Transferred in"
        REVERSAL = "reversal", "Reversal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="movements")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    quantity_delta = models.DecimalField(**QUANTITY)  # signed
    balance_after = models.DecimalField(**QUANTITY)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    issued_to_staff = models.ForeignKey(
        "staff.StaffMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    issued_to_note = models.CharField(max_length=255, blank=True)
    transfer_group = models.UUIDField(null=True, blank=True, db_index=True)
    reverses = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal"
    )
    # Soft link to accounts.User (public schema), same convention as notifications.
    recorded_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["item", "-created_at"], name="inventory_move_item_idx"),
            models.Index(fields=["location", "-created_at"], name="inventory_move_location_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=~Q(quantity_delta=0), name="inventory_move_delta_nonzero"),
            models.CheckConstraint(condition=Q(balance_after__gte=0), name="inventory_move_balance_nonneg"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("A stock movement is immutable; reverse it with a new movement instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("A stock movement can never be deleted; reverse it with a new movement instead.")

    def __str__(self):
        return f"{self.kind} {self.quantity_delta} of {self.item_id} @ {self.location_id}"


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    contact_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Purchase(models.Model):
    """Stock bought from a supplier and received into one location. Creating it receives the stock
    (one RECEIVE movement per line, carrying the unit cost); cancelling it reverses those movements,
    and is refused if any of the stock has since been used."""

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="purchases")
    reference = models.CharField(max_length=100, blank=True, help_text="Supplier invoice or order number")
    purchase_date = models.DateField()
    notes = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchase_date", "-created_at", "-id"]
        indexes = [models.Index(fields=["supplier", "-purchase_date"], name="inventory_purch_supplier_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(total_cost__gte=0), name="inventory_purchase_total_nonneg"),
        ]

    def __str__(self):
        return f"{self.reference or self.id} ({self.status})"


class PurchaseLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="purchase_lines")
    quantity = models.DecimalField(**QUANTITY)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    movement = models.OneToOneField(StockMovement, on_delete=models.PROTECT, related_name="purchase_line")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["purchase", "item"], name="inventory_purchaseline_unique_item"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="inventory_purchaseline_qty_positive"),
            models.CheckConstraint(condition=Q(unit_cost__gte=0), name="inventory_purchaseline_cost_nonneg"),
        ]

    def __str__(self):
        return f"{self.item_id} x {self.quantity} @ {self.unit_cost}"


class AssetCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "asset categories"

    def __str__(self):
        return self.name


class Asset(models.Model):
    """A durable item that is tracked one by one (desk, computer, projector, lab equipment).

    ``status``, ``location`` and the holder are changed only by ``inventory.asset_services`` (each
    change under a row lock, with an immutable ``AssetEvent``); the descriptive fields are edited
    normally. An asset is never deleted: a disposed asset stays in the register.
    """

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ASSIGNED = "assigned", "Assigned"
        IN_REPAIR = "in_repair", "In repair"
        LOST = "lost", "Lost"
        DISPOSED = "disposed", "Disposed"

    class Condition(models.TextChoices):
        NEW = "new", "New"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        POOR = "poor", "Poor"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tag = models.CharField(max_length=50, unique=True, help_text="The school's asset tag number")
    name = models.CharField(max_length=200)
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name="assets")
    serial_number = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="assets")
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.GOOD)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    location = models.ForeignKey(StockLocation, null=True, blank=True, on_delete=models.PROTECT, related_name="assets")
    disposed_at = models.DateTimeField(null=True, blank=True)
    disposal_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tag"]
        indexes = [models.Index(fields=["status"], name="inventory_asset_status_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(purchase_cost__isnull=True) | Q(purchase_cost__gte=0), name="inventory_asset_cost_nonneg"
            ),
            models.CheckConstraint(
                condition=~Q(status="disposed") | Q(disposed_at__isnull=False), name="inventory_asset_disposed_dated"
            ),
        ]

    def __str__(self):
        return f"{self.tag} - {self.name}"


class AssetAssignment(models.Model):
    """Who (or where) an asset was given to, and when it came back. An asset has at most one open
    assignment at a time (a partial unique index)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="assignments")
    staff = models.ForeignKey("staff.StaffMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    location = models.ForeignKey(StockLocation, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    note = models.CharField(max_length=255, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by_user_id = models.UUIDField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    returned_by_user_id = models.UUIDField(null=True, blank=True)
    return_condition = models.CharField(max_length=10, choices=Asset.Condition.choices, blank=True)

    class Meta:
        ordering = ["-assigned_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset"], condition=Q(returned_at__isnull=True), name="inventory_assign_one_open"
            ),
            models.CheckConstraint(
                condition=Q(staff__isnull=False) | Q(location__isnull=False) | ~Q(note=""),
                name="inventory_assign_has_holder",
            ),
        ]


class MaintenanceRecord(models.Model):
    """One repair or service. An asset has at most one open record at a time."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="maintenance")
    reason = models.CharField(max_length=255)
    opened_at = models.DateTimeField(auto_now_add=True)
    opened_by_user_id = models.UUIDField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_user_id = models.UUIDField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-opened_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset"], condition=Q(closed_at__isnull=True), name="inventory_maint_one_open"
            ),
            models.CheckConstraint(
                condition=Q(cost__isnull=True) | Q(cost__gte=0), name="inventory_maint_cost_nonneg"
            ),
        ]


class AssetEvent(models.Model):
    """Immutable history of an asset: every registration and status/location change."""

    class Kind(models.TextChoices):
        REGISTERED = "registered", "Registered"
        ASSIGNED = "assigned", "Assigned"
        RETURNED = "returned", "Returned"
        MOVED = "moved", "Moved"
        SENT_TO_REPAIR = "sent_to_repair", "Sent to repair"
        REPAIRED = "repaired", "Repair completed"
        LOST = "lost", "Marked lost"
        FOUND = "found", "Found"
        DISPOSED = "disposed", "Disposed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    note = models.CharField(max_length=255, blank=True)
    user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["asset", "-created_at"], name="inventory_assetev_asset_idx")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("An asset event is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("An asset event can never be deleted.")

