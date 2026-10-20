"""
Building blocks for automated alerts: eligible-recipient resolution, privacy masking and an
idempotent, all-or-nothing ``dispatch_alert``. No alert *trigger* lives here or anywhere in this
stage; later stages (fee reminders, absence alerts, payment receipts) call these functions.

Why a log row: neither the inbox (``Notification``) nor the outbox (``EmailOutboxEvent``) records
why a message was sent, so neither can detect a duplicate. ``AlertLog`` has a unique
(kind, dedupe_key, recipient) constraint, and a send is "claimed" by inserting that row.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django_tenants.utils import get_public_schema_name

from .models import AlertLog
from .services import notify, queue_email

logger = logging.getLogger(__name__)

NO_EMAIL_HINT = "in-app only"
TITLE_MAX = 200  # Notification.title
BODY_MAX = 500  # Notification.body
SUBJECT_MAX = 255  # EmailOutboxEvent.subject
KEY_MAX = 120  # AlertLog.dedupe_key


class AlertError(Exception):
    """An alert could not be dispatched because the request itself is invalid."""


@dataclass(frozen=True)
class AlertRecipient:
    user_id: object
    email: Optional[str] = None


@dataclass(frozen=True)
class AlertResult:
    created: bool
    log: AlertLog


def mask_email(email):
    """``jane.doe@example.com`` -> ``j***@e***.com``; never returns the full address."""
    if not email or "@" not in email:
        return NO_EMAIL_HINT
    local, _, domain = email.rpartition("@")
    if not local or not domain:
        return NO_EMAIL_HINT
    host, dot, tld = domain.rpartition(".")
    masked_domain = f"{host[:1]}***{dot}{tld}" if host else f"{tld[:1]}***"
    return f"{local[:1]}***@{masked_domain}"


def resolve_alert_recipients(student):
    """
    Eligible recipients for an alert about ``student``, in a stable order:
    the student's own portal account, then each parent linked through
    ``families.StudentParentRelation`` (their portal account).

    A recipient needs a linked ``accounts.User`` that is active. That is the only
    "verified" notion the system has: there is no email-verified flag, so this does not
    imply the address has been verified. A user without an email still receives the in-app
    notification. Students and parents with no linked account, and inactive accounts,
    are skipped; no other contact source is consulted.
    """
    from families.models import StudentParentRelation

    ordered_ids = []
    if student.profile.user_id:
        ordered_ids.append(student.profile.user_id)
    links = StudentParentRelation.objects.filter(student=student).select_related("parent__profile")
    for link in links:
        user_id = link.parent.profile.user_id
        if user_id:
            ordered_ids.append(user_id)

    if not ordered_ids:
        return []

    User = apps.get_model("accounts", "User")
    active = {u.id: u for u in User.objects.filter(id__in=set(ordered_ids), is_active=True)}

    recipients, seen = [], set()
    for user_id in ordered_ids:
        if user_id in seen or user_id not in active:
            continue
        seen.add(user_id)
        recipients.append(AlertRecipient(user_id=user_id, email=active[user_id].email or None))
    return recipients


def dispatch_alert(
    *,
    kind,
    dedupe_key,
    recipient,
    student,
    title,
    body="",
    link="",
    email_subject=None,
    email_body=None,
):
    """
    Sends one alert to one recipient exactly once.

    Algorithm (one transaction; a savepoint if the caller is already in one):
      1. Claim the alert by inserting its ``AlertLog`` row inside a nested savepoint. A unique
         violation means it was already handled (by an earlier run, a retry, or a concurrent
         worker, which blocks on the unique index until the other transaction ends) ->
         ``AlertResult(created=False)``. The savepoint keeps the violation from aborting the
         caller's transaction. If the row is not actually there, the error was something else
         and is re-raised.
      2. Create the in-app notification and, when the recipient has an email, queue the email
         through the existing outbox (``queue_email`` registers its Celery dispatch with
         ``transaction.on_commit``, so nothing is sent unless this transaction commits).
      3. Record both on the log row.

    The log row, the inbox row and the outbox row therefore commit or roll back together:
    there is never a log without its message, nor a message without its log. If email
    delivery later fails permanently, the outbox event stays FAILED and this alert is not
    regenerated. A delivery worker that dies after the SMTP send but before saving the
    status can still repeat that one email (documented in ``notifications.tasks``); that
    never creates a second alert.

    Must run inside a tenant schema; a public-schema call is refused rather than guessed at.
    """
    if connection.schema_name == get_public_schema_name():
        raise AlertError("Alerts can only be dispatched inside a tenant schema.")
    if kind not in AlertLog.Kind.values:
        raise AlertError(f"Unknown alert kind: {kind!r}")
    if not dedupe_key or len(dedupe_key) > KEY_MAX:
        raise AlertError(f"dedupe_key must be 1-{KEY_MAX} characters.")
    if not title or len(title) > TITLE_MAX:
        raise AlertError(f"title must be 1-{TITLE_MAX} characters.")
    if len(body) > BODY_MAX:
        raise AlertError(f"body must be at most {BODY_MAX} characters.")
    if recipient is None or not recipient.user_id:
        raise AlertError("A recipient with a user id is required.")
    send_email = bool(recipient.email)
    if send_email:
        subject = email_subject or title
        if len(subject) > SUBJECT_MAX:
            raise AlertError(f"email subject must be at most {SUBJECT_MAX} characters.")

    with transaction.atomic():
        try:
            with transaction.atomic():
                log = AlertLog.objects.create(
                    kind=kind,
                    dedupe_key=dedupe_key,
                    recipient_user_id=recipient.user_id,
                    recipient_hint=mask_email(recipient.email) if send_email else NO_EMAIL_HINT,
                    student_id=student.id,
                    enrollment_id=student.enrollment_id or "",
                )
        except IntegrityError:
            existing = AlertLog.objects.filter(
                kind=kind, dedupe_key=dedupe_key, recipient_user_id=recipient.user_id
            ).first()
            if existing is None:
                raise
            return AlertResult(created=False, log=existing)

        notification = notify(
            recipient_user_id=recipient.user_id,
            title=title,
            body=body,
            category="alert",
            link=link,
        )
        event = None
        if send_email:
            event = queue_email(
                to_email=recipient.email,
                subject=email_subject or title,
                body=email_body or body or title,
            )

        log.notification_id = notification.id
        log.outbox_event = event
        log.save(update_fields=["notification_id", "outbox_event"])

    return AlertResult(created=True, log=log)
