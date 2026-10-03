import logging
import smtplib
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import BadHeaderError, send_mail
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

logger = logging.getLogger(__name__)

# Exponential backoff for retried sends: 60s, 120s, 240s, ... capped so a
# high max_attempts can't schedule a retry days out.
BASE_RETRY_DELAY_SECONDS = 60
MAX_RETRY_DELAY_SECONDS = 900

# How long an event may sit in PENDING/RETRYING without progress before
# recover_stale_outbox_events treats it as stuck and re-dispatches it.
STALE_THRESHOLD_MINUTES = 15

# Errors send_mail can raise that no amount of retrying will fix (bad
# recipient address, bad credentials, malformed header). Anything else
# (connection refused, timeout, transient 4xx) is treated as temporary.
PERMANENT_ERROR_TYPES = (
    smtplib.SMTPRecipientsRefused,
    smtplib.SMTPSenderRefused,
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPNotSupportedError,
    BadHeaderError,
    ValidationError,
)


def _is_permanent_error(exc):
    return isinstance(exc, PERMANENT_ERROR_TYPES)


def _backoff_seconds(attempt_number):
    return min(BASE_RETRY_DELAY_SECONDS * (2 ** (attempt_number - 1)), MAX_RETRY_DELAY_SECONDS)


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def send_outbox_email(self, schema_name, outbox_event_id):
    """
    Delivers one EmailOutboxEvent. Runs in a Celery worker process, which
    has no per-request tenant context - schema_name is passed explicitly
    by the caller (queue_email()) and entered here via schema_context(),
    mirroring how every other tenant-aware piece of code in this project
    (e.g. core.audit.log_action) relies on the connection already being on
    the right schema rather than filtering by a tenant FK.

    acks_late + reject_on_worker_lost: if the worker process dies mid-send
    (crash, OOM-kill, deploy), the broker redelivers this task to another
    worker instead of silently losing it. The trade-off is that a send can
    then run twice under a true crash - safe here because the status
    check below makes re-running against an already-SENT/FAILED event a
    no-op.

    Failures are classified: a PERMANENT error (bad address, bad auth)
    goes straight to FAILED - retrying it can't ever succeed. A TEMPORARY
    error (connection refused, timeout) retries with exponential backoff
    up to the event's own max_attempts, then goes to FAILED. attempts/
    max_attempts/next_attempt_at are driven by the EmailOutboxEvent row
    itself (not Celery's self.request.retries), so the attempt count
    survives worker restarts and manual re-dispatch (e.g. from
    recover_stale_outbox_events) exactly as it would a normal retry.
    """
    from .models import EmailOutboxEvent

    with schema_context(schema_name):
        try:
            event = EmailOutboxEvent.objects.get(id=outbox_event_id)
        except EmailOutboxEvent.DoesNotExist:
            logger.error(
                "EmailOutboxEvent %s not found in schema %s", outbox_event_id, schema_name
            )
            return

        if event.status in (EmailOutboxEvent.Status.SENT, EmailOutboxEvent.Status.FAILED):
            return  # terminal state already reached - idempotent against duplicate/late dispatch

        try:
            send_mail(
                subject=event.subject,
                message=event.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[event.to_email],
                fail_silently=False,
            )
        except Exception as exc:
            event.attempts += 1
            event.last_error = str(exc)[:1000]
            permanent = _is_permanent_error(exc)
            event.error_type = (
                EmailOutboxEvent.ErrorType.PERMANENT
                if permanent
                else EmailOutboxEvent.ErrorType.TEMPORARY
            )

            if permanent or event.attempts >= event.max_attempts:
                event.status = EmailOutboxEvent.Status.FAILED
                event.next_attempt_at = None
                event.save(
                    update_fields=["attempts", "last_error", "error_type", "status", "next_attempt_at"]
                )
                logger.error(
                    "EmailOutboxEvent %s permanently failed after %s attempt(s) (%s): %s",
                    outbox_event_id,
                    event.attempts,
                    "permanent error" if permanent else "max attempts reached",
                    event.last_error,
                )
                return

            countdown = _backoff_seconds(event.attempts)
            event.status = EmailOutboxEvent.Status.RETRYING
            event.next_attempt_at = timezone.now() + timedelta(seconds=countdown)
            event.save(
                update_fields=["attempts", "last_error", "error_type", "status", "next_attempt_at"]
            )
            raise self.retry(exc=exc, countdown=countdown)

        event.status = EmailOutboxEvent.Status.SENT
        event.sent_at = timezone.now()
        event.next_attempt_at = None
        event.save(update_fields=["status", "sent_at", "next_attempt_at"])


@shared_task
def recover_stale_outbox_events():
    """
    Safety net for events stuck in PENDING or RETRYING with no progress
    for more than STALE_THRESHOLD_MINUTES - covers a task that was queued
    (on_commit fired) but never actually ran because the broker message
    was lost before a worker picked it up, or a scheduled retry whose
    countdown fired while no worker was running. Intended to run on a
    periodic Celery beat schedule (e.g. every 10 minutes); no beat process
    is wired up in this project yet, so for now this is invoked manually
    or from an external scheduler.

    Re-dispatches via the normal task entry point rather than sending
    directly, so send_outbox_email's own idempotency/attempt-limit/
    classification logic still applies - this task's only job is
    "notice stuck events and give them another chance to run."

    Iterates every tenant schema explicitly since, like the task above, a
    periodic task has no per-request tenant context to rely on.
    """
    from .models import EmailOutboxEvent

    cutoff = timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES)
    recovered = 0

    for tenant in get_tenant_model().objects.exclude(schema_name="public"):
        with schema_context(tenant.schema_name):
            stale_events = EmailOutboxEvent.objects.filter(
                status__in=[EmailOutboxEvent.Status.PENDING, EmailOutboxEvent.Status.RETRYING],
                updated_at__lt=cutoff,
            )
            for event in stale_events:
                send_outbox_email.delay(tenant.schema_name, str(event.id))
                recovered += 1

    if recovered:
        logger.warning("recover_stale_outbox_events requeued %s stale event(s)", recovered)
    return recovered
