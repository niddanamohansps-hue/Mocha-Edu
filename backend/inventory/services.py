"""Stock rules. Every change of stock goes through here, inside one transaction:

    lock the (item, location) level row -> check the rule -> update the level -> write the movement

so two simultaneous issues of the last unit cannot both succeed, a balance can never go negative
(the database constraints are the backstop), and the level always equals the sum of its movements.
"""
import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Item, StockLevel, StockLocation, StockMovement

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
        return StockMovement.objects.create(
            item=item, location=location, kind=kind, quantity_delta=delta, balance_after=new_balance,
            unit_cost=unit_cost, reason=reason, reference=reference or "", issued_to_staff=issued_to_staff,
            issued_to_note=issued_to_note or "", transfer_group=transfer_group, reverses=reverses,
            recorded_by_user_id=user_id,
        )


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


def reverse(movement, *, reason, user_id=None):
    """Undo a movement with an opposite one. A movement is reversed at most once; a transfer leg or
    a reversal cannot be reversed (make the opposite transfer instead)."""
    with transaction.atomic():
        original = StockMovement.objects.select_for_update().select_related("item", "location").get(pk=movement.pk)
        if original.kind in NOT_REVERSIBLE:
            raise serializers.ValidationError({"movement": "This kind of movement cannot be reversed."})
        if StockMovement.objects.filter(reverses=original).exists():
            raise serializers.ValidationError({"movement": "This movement has already been reversed."})
        return _apply(
            item=original.item, location=original.location, kind=Kind.REVERSAL, delta=-original.quantity_delta,
            user_id=user_id, reason=reason, reference=original.reference, reverses=original,
        )
