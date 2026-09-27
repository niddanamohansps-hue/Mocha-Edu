"""
Notification creation - the ONLY intended way Notification rows come into
existence (the API never accepts a create/write body - see views.py).
Deliberately synchronous and dependency-free: no email, no SMS, no Celery,
no Redis, no external service. Ready for future modules to call, but
nothing in this milestone calls it yet (see the approved V1 decision - no
existing module is wired in).
"""

from .models import Notification


def notify(*, recipient_user_id, title, body="", category="", link=""):
    """Creates and returns a single Notification for one recipient."""
    if not recipient_user_id:
        raise ValueError("recipient_user_id is required.")
    if not title:
        raise ValueError("title is required.")

    return Notification.objects.create(
        recipient_user_id=recipient_user_id,
        title=title,
        body=body,
        category=category,
        link=link,
    )


def notify_many(*, recipient_user_ids, title, body="", category="", link=""):
    """
    Creates one Notification per recipient in a single bulk_create() -
    intentionally no restriction on duplicate recipients in the list (the
    caller's problem, not this function's - a recipient appearing twice
    just gets two rows, which is harmless, matching the model's "no unique
    constraints, duplicates are acceptable" design).

    Returns the list of created Notification instances (bulk_create
    returns them with their primary keys populated, since Notification's
    id is a client-generated UUIDField default, not an auto-incrementing
    one - populated immediately on construction, before the INSERT).
    """
    if not recipient_user_ids:
        raise ValueError("recipient_user_ids is required.")
    if not title:
        raise ValueError("title is required.")

    notifications = [
        Notification(
            recipient_user_id=recipient_user_id,
            title=title,
            body=body,
            category=category,
            link=link,
        )
        for recipient_user_id in recipient_user_ids
    ]
    return Notification.objects.bulk_create(notifications)
