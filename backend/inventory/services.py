"""Stock rules. Every change of stock goes through here, inside one transaction:

    lock the (item, location) level row -> check the rule -> update the level -> write the movement

so two simultaneous issues of the last unit cannot both succeed, a balance can never go negative
(the database constraints are the backstop), and the level always equals the sum of its movements.
"""
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from . import alerts
from .models import Item, Purchase, PurchaseLine, StockLevel, StockLocation, StockMovement

Kind = StockMovement.Kind

# Kinds that add stock / remove stock. A reversal takes the opposite sign of what it reverses.
INCREASING = {Kind.RECEIVE, Kind.RETURN, Kind.ADJUST_IN, Kind.TRANSFER_IN}
DECREASING = {Kind.ISSUE, Kind.ADJUST_OUT, Kind.WRITE_OFF, Kind.TRANSFER_OUT}
REASON_REQUIRED = {Kind.ADJUST_IN, Kind.ADJUST_OUT, Kind.WRITE_OFF, Kind.REVERSAL}
NOT_REVERSIBLE = {Kind.TRANSFER_IN, Kind.TRANSFER_OUT, Kind.REVERSAL}


def _check_usable(item, location):
    if not item.is_active:
        raise serializers.ValidationError({"item": "This item is inactive."})
    if not location.is_active:
        raise serializers.ValidationError({"location": "This location is inactive."})


def _locked_level(item, location):
    """The level row for (item, location), locked for the rest of the transaction; created at zero
    when the item has never been in that location."""
    level = StockLevel.objects.select_for_update().filter(item=item, location=location).first()
    if level is not None:
        return level
    try:
        with transaction.atomic():
            StockLevel.objects.create(item=item, location=location, quantity=Decimal("0"))
    except IntegrityError:
        pass  # a concurrent request created it first
    return StockLevel.objects.select_for_update().get(item=item, location=location)


def _apply(*, item, location, kind, delta, user_id, unit_cost=None, reason="", reference="",
           issued_to_staff=None, issued_to_note="", transfer_group=None, reverses=None):
    """One locked, all-or-nothing change of stock. Returns the movement."""
    if delta == 0:
        raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})
    reason = (reason or "").strip()
    if kind in REASON_REQUIRED and not reason:
        raise serializers.ValidationError({"reason": "A reason is required."})
    with transaction.atomic():
        _check_usable(item, location)
        level = _locked_level(item, location)
        new_balance = level.quantity + delta
        if new_balance < 0:
            raise serializers.ValidationError(
                {"quantity": f"Not enough stock: {level.quantity} {item.unit} on hand, {-delta} requested."}
            )
        level.quantity = new_balance
        level.save(update_fields=["quantity", "updated_at"])
        movement = StockMovement.objects.create(
            item=item, location=location, kind=kind, quantity_delta=delta, balance_after=new_balance,
            unit_cost=unit_cost, reason=reason, reference=reference or "", issued_to_staff=issued_to_staff,
            issued_to_note=issued_to_note or "", transfer_group=transfer_group, reverses=reverses,
            recorded_by_user_id=user_id,
        )
        # A transfer moves stock between locations without changing the item's total.
        if transfer_group is None:
            alerts.check_low_stock(item.pk)
        return movement


def record(*, item, location, kind, quantity, user_id=None, unit_cost=None, reason="", reference="",
           issued_to_staff=None, issued_to_note=""):
    """Record one ordinary movement. ``quantity`` is always positive; the kind decides the sign."""
    if kind not in INCREASING | DECREASING or kind in (Kind.TRANSFER_IN, Kind.TRANSFER_OUT):
        raise ValueError(f"Use the dedicated function for {kind!r}.")
    if quantity is None or quantity <= 0:
        raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})
    if unit_cost is not None and kind != Kind.RECEIVE:
        raise serializers.ValidationError({"unit_cost": "A unit cost is only recorded when receiving stock."})
    if kind == Kind.ISSUE and issued_to_staff is None and not (issued_to_note or "").strip():
        raise serializers.ValidationError(
            {"issued_to_note": "Say who the stock was issued to (a staff member or a note)."}
        )
    delta = quantity if kind in INCREASING else -quantity
    return _apply(
        item=item, location=location, kind=kind, delta=delta, user_id=user_id, unit_cost=unit_cost,
        reason=reason, reference=reference, issued_to_staff=issued_to_staff, issued_to_note=issued_to_note,
    )


def transfer(*, item, from_location, to_location, quantity, user_id=None, reason="", reference=""):
    """Move stock between two locations: two linked movements in one transaction."""
    if from_location.pk == to_location.pk:
        raise serializers.ValidationError({"to_location": "Choose a different location."})
    if quantity is None or quantity <= 0:
        raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})
    group = uuid.uuid4()
    with transaction.atomic():
        # Lock in a stable order so two opposite transfers cannot deadlock.
        for location in sorted((from_location, to_location), key=lambda loc: str(loc.pk)):
            _check_usable(item, location)
            _locked_level(item, location)
        out = _apply(item=item, location=from_location, kind=Kind.TRANSFER_OUT, delta=-quantity,
                     user_id=user_id, reason=reason, reference=reference, transfer_group=group)
        into = _apply(item=item, location=to_location, kind=Kind.TRANSFER_IN, delta=quantity,
                      user_id=user_id, reason=reason, reference=reference, transfer_group=group)
    return out, into


def reverse(movement, *, reason, user_id=None, _from_purchase=False):
    """Undo a movement with an opposite one. A movement is reversed at most once; a transfer leg or
    a reversal cannot be reversed (make the opposite transfer instead)."""
    with transaction.atomic():
        original = StockMovement.objects.select_for_update().select_related("item", "location").get(pk=movement.pk)
        if original.kind in NOT_REVERSIBLE:
            raise serializers.ValidationError({"movement": "This kind of movement cannot be reversed."})
        if not _from_purchase and PurchaseLine.objects.filter(movement=original).exists():
            raise serializers.ValidationError({"movement": "This stock came in with a purchase; cancel the purchase instead."})
        if StockMovement.objects.filter(reverses=original).exists():
            raise serializers.ValidationError({"movement": "This movement has already been reversed."})
        return _apply(
            item=original.item, location=original.location, kind=Kind.REVERSAL, delta=-original.quantity_delta,
            user_id=user_id, reason=reason, reference=original.reference, reverses=original,
        )


# --- Purchases ----------------------------------------------------------------------------------

MAX_PURCHASE_LINES = 200
MONEY_LIMIT = Decimal("1000000000000")  # keeps a purchase total inside Purchase.total_cost (14 digits)


def receive_purchase(*, supplier, location, lines, purchase_date, reference="", notes="", user_id=None):
    """Record a purchase and receive its stock in one transaction.

    ``lines`` is a list of ``{"item", "quantity", "unit_cost"}``. Each line becomes one RECEIVE
    movement carrying its unit cost; an item may appear once. Either everything is received or
    nothing is.
    """
    if not supplier.is_active:
        raise serializers.ValidationError({"supplier": "This supplier is inactive."})
    if not lines:
        raise serializers.ValidationError({"lines": "Add at least one item."})
    if len(lines) > MAX_PURCHASE_LINES:
        raise serializers.ValidationError({"lines": f"At most {MAX_PURCHASE_LINES} items per purchase."})
    item_ids = [line["item"].pk for line in lines]
    if len(set(item_ids)) != len(item_ids):
        raise serializers.ValidationError({"lines": "Each item can appear only once in a purchase."})
    total = Decimal("0")
    for line in lines:
        if line["quantity"] <= 0 or line["unit_cost"] < 0:
            raise serializers.ValidationError({"lines": "Quantities must be positive and costs cannot be negative."})
        total += (line["quantity"] * line["unit_cost"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if total >= MONEY_LIMIT:
        raise serializers.ValidationError({"lines": "The purchase total is too large."})

    with transaction.atomic():
        purchase = Purchase.objects.create(
            supplier=supplier, location=location, reference=reference or "", purchase_date=purchase_date,
            notes=notes or "", total_cost=total, created_by_user_id=user_id,
        )
        movement_reference = (reference or f"PUR-{str(purchase.pk)[:8]}")[:100]
        # A stable order, so two purchases of the same items at the same time cannot deadlock.
        for line in sorted(lines, key=lambda entry: str(entry["item"].pk)):
            movement = record(
                item=line["item"], location=location, kind=Kind.RECEIVE, quantity=line["quantity"],
                user_id=user_id, unit_cost=line["unit_cost"], reference=movement_reference,
                reason=f"Purchase from {supplier.name}"[:255],
            )
            PurchaseLine.objects.create(
                purchase=purchase, item=line["item"], quantity=line["quantity"], unit_cost=line["unit_cost"],
                movement=movement,
            )
    return purchase


def cancel_purchase(purchase, *, reason, user_id=None):
    """Cancel a received purchase by reversing every one of its movements. If any of that stock has
    since been used the whole cancellation is refused and nothing changes."""
    reason = (reason or "").strip()
    if not reason:
        raise serializers.ValidationError({"reason": "A reason is required."})
    with transaction.atomic():
        locked = Purchase.objects.select_for_update().get(pk=purchase.pk)
        if locked.status != Purchase.Status.RECEIVED:
            raise serializers.ValidationError({"purchase": "This purchase is already cancelled."})
        lines = list(locked.lines.select_related("movement").order_by("item_id"))
        for line in lines:
            reverse(line.movement, reason=f"Purchase cancelled: {reason}"[:255], user_id=user_id, _from_purchase=True)
        locked.status = Purchase.Status.CANCELLED
        locked.cancelled_at = timezone.now()
        locked.cancellation_reason = reason[:255]
        locked.save(update_fields=["status", "cancelled_at", "cancellation_reason"])
    return locked
