"""Asset lifecycle rules. Every status/location/holder change goes through here, in one transaction
that locks the asset row first, so two people cannot (for example) assign the same projector at once.

    available --assign--> assigned --return--> available
    available/assigned --send to repair--> in_repair --complete--> available
    available/assigned --mark lost--> lost --found--> available
    available/lost --dispose--> disposed (final)
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from staff.models import StaffMember

from .models import Asset, AssetAssignment, AssetEvent, MaintenanceRecord, StockLocation

Status = Asset.Status
Kind = AssetEvent.Kind


def _locked(asset):
    return Asset.objects.select_for_update().get(pk=asset.pk)


def _require(asset, allowed, action):
    if asset.status not in allowed:
        raise serializers.ValidationError(
            {"status": f"A {asset.get_status_display().lower()} asset cannot be {action}."}
        )


def _need_reason(reason, field="reason"):
    reason = (reason or "").strip()
    if not reason:
        raise serializers.ValidationError({field: "A reason is required."})
    return reason[:255]


def _check_location(location):
    if location is not None and not location.is_active:
        raise serializers.ValidationError({"location": "This location is inactive."})


def _event(asset, kind, from_status, note="", user_id=None):
    return AssetEvent.objects.create(
        asset=asset, kind=kind, from_status=from_status, to_status=asset.status, note=(note or "")[:255], user_id=user_id
    )


def _open_assignment(asset):
    return AssetAssignment.objects.select_for_update().filter(asset=asset, returned_at__isnull=True).first()


def _close_assignment(asset, user_id, condition=""):
    assignment = _open_assignment(asset)
    if assignment is not None:
        assignment.returned_at = timezone.now()
        assignment.returned_by_user_id = user_id
        assignment.return_condition = condition
        assignment.save(update_fields=["returned_at", "returned_by_user_id", "return_condition"])
    return assignment


def register(*, user_id=None, **fields):
    """Create an asset and record its registration."""
    _check_location(fields.get("location"))
    with transaction.atomic():
        asset = Asset.objects.create(**fields)
        _event(asset, Kind.REGISTERED, "", user_id=user_id)
    return asset


def assign(asset, *, user_id=None, staff=None, location=None, note=""):
    """Give an available asset to a staff member and/or a place (or just a note, e.g. a class)."""
    note = (note or "").strip()[:255]
    if staff is None and location is None and not note:
        raise serializers.ValidationError({"staff": "Say who or where the asset is assigned to."})
    with transaction.atomic():
        asset = _locked(asset)
        _require(asset, {Status.AVAILABLE}, "assigned")
        if staff is not None and not StaffMember.objects.filter(pk=staff.pk, is_active=True).exists():
            raise serializers.ValidationError({"staff": "This staff member is not active."})
        _check_location(location)
        AssetAssignment.objects.create(asset=asset, staff=staff, location=location, note=note, assigned_by_user_id=user_id)
        asset.status = Status.ASSIGNED
        if location is not None:
            asset.location = location
        asset.save(update_fields=["status", "location", "updated_at"])
        _event(asset, Kind.ASSIGNED, Status.AVAILABLE, note, user_id)
    return asset


def return_asset(asset, *, user_id=None, location=None, condition=None, note=""):
    """Take an assigned asset back, optionally recording where it is now and its condition."""
    with transaction.atomic():
        asset = _locked(asset)
        _require(asset, {Status.ASSIGNED}, "returned")
        _check_location(location)
        _close_assignment(asset, user_id, condition or "")
        asset.status = Status.AVAILABLE
        update = ["status", "updated_at"]
        if location is not None:
            asset.location = location
            update.append("location")
        if condition:
            asset.condition = condition
            update.append("condition")
        asset.save(update_fields=update)
        _event(asset, Kind.RETURNED, Status.ASSIGNED, note, user_id)
    return asset


def move(asset, *, location, user_id=None, note=""):
    """Change where an available asset is kept."""
    if location is None:
        raise serializers.ValidationError({"location": "Choose a location."})
    with transaction.atomic():
        asset = _locked(asset)
        _require(asset, {Status.AVAILABLE}, "moved")
        _check_location(location)
        if asset.location_id == location.pk:
            raise serializers.ValidationError({"location": "The asset is already there."})
        asset.location = location
        asset.save(update_fields=["location", "updated_at"])
        _event(asset, Kind.MOVED, Status.AVAILABLE, note or f"Moved to {location.name}", user_id)
    return asset


def send_to_repair(asset, *, reason, user_id=None):
    reason = _need_reason(reason)
    with transaction.atomic():
        asset = _locked(asset)
        _require(asset, {Status.AVAILABLE, Status.ASSIGNED}, "sent to repair")
        from_status = asset.status
        _close_assignment(asset, user_id)
        MaintenanceRecord.objects.create(asset=asset, reason=reason, opened_by_user_id=user_id)
        asset.status = Status.IN_REPAIR
        asset.save(update_fields=["status", "updated_at"])
        _event(asset, Kind.SENT_TO_REPAIR, from_status, reason, user_id)
    return asset


def complete_repair(asset, *, user_id=None, cost=None, notes="", condition=None):
    if cost is not None and cost < 0:
        raise serializers.ValidationError({"cost": "The cost cannot be negative."})
    with transaction.atomic():
        asset = _locked(asset)
        _require(asset, {Status.IN_REPAIR}, "marked repaired")
        record = MaintenanceRecord.objects.select_for_update().filter(asset=asset, closed_at__isnull=True).first()
        if record is not None:
            record.closed_at = timezone.now()
            record.closed_by_user_id = user_id
            record.cost = Decimal(cost) if cost is not None else None
            record.notes = (notes or "")[:255]
            record.save(update_fields=["closed_at", "closed_by_user_id", "cost", "notes"])
        asset.status = Status.AVAILABLE
        update = ["status", "updated_at"]
        if condition:
            asset.condition = condition
            update.append("condition")
        asset.save(update_fields=update)
        _event(asset, Kind.REPAIRED, Status.IN_REPAIR, notes, user_id)
    return asset


def mark_lost(asset, *, reason, user_id=None):
    reason = _need_reason(reason)
    with transaction.atomic():
        asset = _locked(asset)
        _require(asset, {Status.AVAILABLE, Status.ASSIGNED}, "marked lost")
        from_status = asset.status
        _close_assignment(asset, user_id)
        asset.status = Status.LOST
        asset.save(update_fields=["status", "updated_at"])
        _event(asset, Kind.LOST, from_status, reason, user_id)
    return asset


def mark_found(asset, *, location=None, user_id=None, note=""):
    with transaction.atomic():
        asset = _locked(asset)
        _require(asset, {Status.LOST}, "marked found")
        _check_location(location)
        asset.status = Status.AVAILABLE
        update = ["status", "updated_at"]
        if location is not None:
            asset.location = location
            update.append("location")
        asset.save(update_fields=update)
        _event(asset, Kind.FOUND, Status.LOST, note, user_id)
    return asset


def dispose(asset, *, reason, user_id=None):
    """Retire an asset for good (sold, scrapped, donated). It stays in the register."""
    reason = _need_reason(reason)
    with transaction.atomic():
        asset = _locked(asset)
        _require(asset, {Status.AVAILABLE, Status.LOST}, "disposed of")
        from_status = asset.status
        asset.status = Status.DISPOSED
        asset.disposed_at = timezone.now()
        asset.disposal_reason = reason
        asset.save(update_fields=["status", "disposed_at", "disposal_reason", "updated_at"])
        _event(asset, Kind.DISPOSED, from_status, reason, user_id)
    return asset
