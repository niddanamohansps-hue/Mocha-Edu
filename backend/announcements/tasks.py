import logging
import time

from celery import shared_task
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from .services import (
    AnnouncementAuthorizationError,
    AnnouncementStateError,
    publish_announcement,
    revert_unpublishable_to_draft,
)

logger = logging.getLogger(__name__)

# Bounds work per tenant per run; any remainder is picked up next run.
BATCH_SIZE = 100

# settings.CELERY_TASK_TIME_LIMIT (30s) hard-kills a task that overruns it.
# A kill mid-publish is safe (the transaction rolls back and the announcement
# stays scheduled) but would repeat on every run if a backlog never fits, so
# the task stops *starting* new announcements after this budget and leaves the
# rest for the next run. It cannot shorten a single publish already in flight.
TIME_BUDGET_SECONDS = 20


def publish_due_in_current_schema(schema_name, now=None, deadline=None):
    """Publishes due scheduled announcements in the already-active schema.

    `deadline` is a time.monotonic() value; once passed, remaining due
    announcements are counted as deferred and left scheduled for the next run.
    """
    from .models import Announcement

    now = now or timezone.now()
    due_ids = list(
        Announcement.objects.filter(status=Announcement.Status.SCHEDULED, scheduled_at__lte=now)
        .order_by("scheduled_at", "id")
        .values_list("id", flat=True)[:BATCH_SIZE]
    )
    counts = {"published": 0, "skipped": 0, "reverted": 0, "failed": 0, "deferred": 0}
    for index, announcement_id in enumerate(due_ids):
        if deadline is not None and time.monotonic() > deadline:
            counts["deferred"] = len(due_ids) - index
            logger.warning(
                "Time budget reached in schema %s; deferring %s due announcement(s) to the next run.",
                schema_name, counts["deferred"],
            )
            break
        try:
            publish_announcement(announcement_id)
            counts["published"] += 1
        except AnnouncementStateError:
            # Published or archived by someone else since the ids were read.
            counts["skipped"] += 1
        except AnnouncementAuthorizationError as exc:
            # Creator lost broadcast permission, was deactivated, or left tenant:
            # fail-closed and return to draft with audit log.
            revert_unpublishable_to_draft(announcement_id, reason=str(exc))
            counts["reverted"] += 1
            logger.warning(
                "Scheduled announcement %s in schema %s cancelled (authorization failed: %s); returned to draft.",
                announcement_id, schema_name, exc,
            )
        except ValidationError:
            # Empty audience: return to draft so it stops failing every run.
            revert_unpublishable_to_draft(announcement_id, reason="No eligible recipients found for audience")
            counts["reverted"] += 1
            logger.warning(
                "Scheduled announcement %s in schema %s had no eligible recipients; returned to draft.",
                announcement_id, schema_name,
            )
        except Exception:
            # Left SCHEDULED, so the next run retries it.
            counts["failed"] += 1
            logger.exception("Failed to publish scheduled announcement %s in schema %s", announcement_id, schema_name)
    return counts


@shared_task
def publish_due_announcements():
    """
    Celery Beat entry point. Iterates active tenants the same way
    notifications.tasks.recover_stale_outbox_events does, but also skips
    inactive organizations and isolates each tenant: one tenant's failure is
    logged and the loop continues with the next. Tenants are visited in random
    order so a consistently busy tenant cannot starve the others when the time
    budget runs out.
    """
    deadline = time.monotonic() + TIME_BUDGET_SECONDS
    totals = {"published": 0, "skipped": 0, "reverted": 0, "failed": 0, "deferred": 0, "tenant_errors": 0}
    tenants = get_tenant_model().objects.filter(is_active=True).exclude(schema_name="public").order_by("?")
    for tenant in tenants:
        if time.monotonic() > deadline:
            logger.warning("Time budget reached; remaining tenants will be processed on the next run.")
            break
        try:
            with schema_context(tenant.schema_name):
                for key, value in publish_due_in_current_schema(tenant.schema_name, deadline=deadline).items():
                    totals[key] += value
        except Exception:
            totals["tenant_errors"] += 1
            logger.exception("publish_due_announcements failed for schema %s", tenant.schema_name)

    if any(totals.values()):
        logger.info("publish_due_announcements: %s", totals)
    return totals
