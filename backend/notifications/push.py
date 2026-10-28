"""
Free phone / browser push notifications (Web Push with VAPID keys; no paid service).

Every in-app notification (notify / notify_many) is also pushed to the recipient's subscribed devices,
after the transaction commits and through the Celery worker, so a slow push service never slows a request.
Nothing is pushed when the VAPID keys are not configured. A device the push service reports as gone
(404 / 410) is forgotten; others are retried by the push service itself.

Settings (in .env): WEBPUSH_VAPID_PUBLIC_KEY, WEBPUSH_VAPID_PRIVATE_KEY, WEBPUSH_CONTACT (mailto: address).
Generate a key pair once with:  python manage.py generate_vapid_keys
"""
import json
import logging

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_TITLE, MAX_BODY = 120, 240


def enabled():
    return bool(getattr(settings, "WEBPUSH_VAPID_PUBLIC_KEY", "") and getattr(settings, "WEBPUSH_VAPID_PRIVATE_KEY", ""))


def queue_push(notifications):
    """Called by notify / notify_many: pushes these notifications once the transaction commits."""
    if not enabled() or not notifications:
        return
    ids = [str(n.id) for n in notifications]
    schema = connection.schema_name

    def send_later():
        from .tasks import send_push_notifications

        try:
            send_push_notifications.delay(schema, ids)
        except Exception:  # noqa: BLE001 - a missing broker must not break the action that notified
            logger.warning("Push notifications could not be queued.", exc_info=True)

    transaction.on_commit(send_later)


def send(notification_ids):
    """Sends the given notifications (current schema) to their recipients' devices. Returns pushes delivered."""
    from pywebpush import WebPushException, webpush

    from .models import Notification, PushSubscription

    notes = list(Notification.objects.filter(id__in=notification_ids))
    subs = {}
    for sub in PushSubscription.objects.filter(user_id__in={n.recipient_user_id for n in notes}):
        subs.setdefault(sub.user_id, []).append(sub)
    delivered = 0
    for note in notes:
        payload = json.dumps({
            "title": note.title[:MAX_TITLE], "body": (note.body or "")[:MAX_BODY],
            "link": note.link or "/dashboard", "tag": note.category or "edusekai",
        })
        for sub in subs.get(note.recipient_user_id, []):
            try:
                webpush(
                    subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=payload,
                    vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": getattr(settings, "WEBPUSH_CONTACT", "mailto:support@example.com")},
                    ttl=24 * 3600,
                    timeout=10,
                )
            except WebPushException as exc:
                code = getattr(getattr(exc, "response", None), "status_code", None)
                if code in (404, 410):
                    sub.delete()  # the browser unsubscribed or the app was removed
                else:
                    PushSubscription.objects.filter(pk=sub.pk).update(failures=sub.failures + 1)
                    logger.warning("Push to a device failed (%s).", code)
                continue
            except Exception:  # noqa: BLE001 - network trouble with one device must not stop the others
                logger.warning("Push to a device failed.", exc_info=True)
                continue
            PushSubscription.objects.filter(pk=sub.pk).update(last_success_at=timezone.now(), failures=0)
            delivered += 1
    return delivered
