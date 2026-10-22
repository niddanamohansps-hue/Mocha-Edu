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
