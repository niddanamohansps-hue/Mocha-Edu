"""
Notification creation - the ONLY intended way Notification rows come into
existence (the API never accepts a create/write body - see views.py).
In-app notifications (notify/notify_many) remain synchronous and
dependency-free, as originally decided for V1. Outbound EMAIL now goes
through the async transactional-outbox pipeline below (queue_email) -
Celery/Redis, added once password-reset needed real email delivery
without blocking the request (see EmailOutboxEvent in models.py).
"""

import logging

from celery.exceptions import CeleryError
from django.db import connection, transaction
from kombu.exceptions import KombuError

from .models import Notification, EmailOutboxEvent

logger = logging.getLogger(__name__)


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


def queue_email(*, to_email, subject, body):
    """
    Queues an email for async delivery via the transactional outbox:
    writes an EmailOutboxEvent row, then schedules the Celery task that
    actually sends it via transaction.on_commit() - so the task is only
    ever dispatched once this write (and anything else in the caller's
    surrounding transaction.atomic() block, if any) has actually
    committed. A task queued against a row that got rolled back would
    fail with "does not exist"; on_commit() makes that impossible.

    The current tenant schema is captured explicitly (connection.schema_name)
    and passed to the task, since a Celery worker has no per-request tenant
    context of its own - see tasks.send_outbox_email.

    The EmailOutboxEvent write itself is NOT wrapped in any try/except
    here - a database/validation error creating it is a genuine failure
    of the caller's business operation and must propagate exactly as it
    did before, rolling back the caller's transaction along with it.

    The on_commit callback IS wrapped: by the time it runs, the event row
    (and everything else in the caller's transaction) has already
    committed, so a broker/dispatch failure at that point can no longer
    change whether the business operation succeeded - only whether the
    email gets sent promptly. Catching CeleryError (covers Celery's own
    Retry/task-level failures - e.g. the self.retry() raised synchronously
    under CELERY_TASK_ALWAYS_EAGER in tests) and KombuError (covers
    broker/transport-level failures, e.g. Redis briefly unreachable at the
    moment of dispatch) keeps this narrowly scoped to "the message could
    not be handed to Celery," never to a programming/data error - which
    would be some other exception type and is deliberately left
    unhandled, propagating normally. The event is left exactly as
    created (PENDING); recover_stale_outbox_events already re-dispatches
    any PENDING/RETRYING event with no progress past its staleness
    threshold, so a dispatch failure here is not a dead end.
    """
    from .tasks import send_outbox_email

    event = EmailOutboxEvent.objects.create(to_email=to_email, subject=subject, body=body)
    schema_name = connection.schema_name

    def _dispatch():
        try:
            send_outbox_email.delay(schema_name, str(event.id))
        except (CeleryError, KombuError) as exc:
            logger.warning(
                "Failed to dispatch EmailOutboxEvent %s (schema=%s) to Celery after its "
                "transaction committed - it remains PENDING and will be picked up by "
                "recover_stale_outbox_events: %s",
                event.id, schema_name, exc,
            )

    transaction.on_commit(_dispatch)
    return event
