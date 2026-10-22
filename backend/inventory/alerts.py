"""Low-stock alerts.

One alert per dip: when an item's total stock (all locations) falls to or below its reorder level the
people who manage stock are told once; the item is marked (``low_stock_notified_at``) and is not
announced again until stock has been back above the reorder level. Off unless the school turned on
``low_stock_alerts_enabled`` in its alert settings.

The check runs inside the transaction of the stock movement that caused it, with the item row locked,
so concurrent movements cannot both announce the same dip. A failure here never blocks the stock
movement: it is logged, rolled back on its own savepoint, and tried again by the next movement.
"""
import logging
from decimal import Decimal

from django.apps import apps
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from notifications.models import NotificationSettings
from notifications.services import notify, queue_email

from .models import Item

logger = logging.getLogger(__name__)

# Roles that get the alert: the owner, and anyone whose role can restock or manage items.
ALERT_PERMISSIONS = ("receive_stock", "manage_inventory_items")


def alert_recipients():
    """Active users of this school who manage stock: ``[(user_id, email_or_None), ...]``."""
    from roles.models import UserRole

    user_ids = set(
        UserRole.objects.filter(
            Q(role__slug="owner") | Q(role__permissions__codename__in=ALERT_PERMISSIONS)
        ).values_list("user_id", flat=True)
    )
    if not user_ids:
        return []
    User = apps.get_model("accounts", "User")
    users = User.objects.filter(id__in=user_ids, is_active=True).order_by("username")
    return [(user.id, user.email or None) for user in users]


def _is_low(item, on_hand):
    return bool(item.is_active and item.reorder_level > 0 and on_hand <= item.reorder_level)


def _announce(item, on_hand):
    recipients = alert_recipients()
    title = f"Low stock: {item.name}"[:200]
    body = (
        f"{item.name} ({item.sku}): {on_hand:.3f} {item.unit} left in total. "
        f"The reorder level is {item.reorder_level:.3f}."
    )[:500]
    for user_id, email in recipients:
        notify(recipient_user_id=user_id, title=title, body=body, category="inventory")
        if email:
            queue_email(to_email=email, subject=title[:255], body=body)
    return len(recipients)


def check_low_stock(item_id):
    """Announce or reset the low-stock state of one item. Returns ``"announced"``, ``"reset"`` or None."""
    if not NotificationSettings.load().low_stock_alerts_enabled:
        return None
    try:
        with transaction.atomic():
            item = Item.objects.select_for_update().get(pk=item_id)
            on_hand = item.levels.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
            if _is_low(item, on_hand):
                if item.low_stock_notified_at is not None:
                    return None
                _announce(item, on_hand)
                Item.objects.filter(pk=item.pk).update(low_stock_notified_at=timezone.now())
                return "announced"
            if item.low_stock_notified_at is not None:
                Item.objects.filter(pk=item.pk).update(low_stock_notified_at=None)
                return "reset"
    except Exception:
        logger.exception("Could not check the low-stock alert for item %s.", item_id)
    return None
