import uuid

from django.db import models


class Notification(models.Model):
    """
    In-app notification inbox, V1. One row per (recipient, event) - no
    broadcast/recipient-join-table, since a broadcast is just notify_many()
    creating several of these rows at once (see services.py).

    recipient_user_id is intentionally a SOFT LINK (not a ForeignKey to
    accounts.User) - the User model lives in the public schema while this
    model is tenant-scoped, so a real cross-schema FK isn't possible here,
    exactly mirroring the pattern already used by profiles.Profile.user_id
    and core.AuditLog.actor_id.

    category is a display/grouping hint only (e.g. "fee", "exam",
    "promotion") - deliberately a plain CharField, not a choices list or a
    separate model, since V1 has no module actually producing these yet
    (see services.py's notify()/notify_many() - ready for future modules
    to call, not wired into anything in this milestone).

    link is an optional RELATIVE frontend path (e.g. "/dashboard/fees"),
    never an absolute URL.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_user_id = models.UUIDField(db_index=True)

    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    category = models.CharField(max_length=30, blank=True)
    link = models.CharField(max_length=255, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["recipient_user_id", "is_read", "-created_at"],
                name="notif_recipient_unread_idx",
            ),
        ]

    def __str__(self):
        return f"{self.recipient_user_id} - {self.title}"


class EmailOutboxEvent(models.Model):
    """
    Transactional outbox for async email delivery. A row is written in the
    same database transaction as whatever triggered it (e.g. a password
    reset request); the Celery task that actually sends the email is only
    dispatched via transaction.on_commit() (see services.queue_email()),
    so a task can never be queued for an event that ends up rolled back.

    Tenant-scoped like every other model in this app - the Celery task
    receives the schema name explicitly and enters it via schema_context()
    before touching this table, since a worker process has no per-request
    tenant context the way TenantMainMiddleware provides one.

    Lifecycle: PENDING -> (failure) -> RETRYING -> (failure) -> RETRYING
    -> ... -> SENT or FAILED (terminal, either after a permanent error or
    after max_attempts temporary failures). See tasks.send_outbox_email.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RETRYING = "retrying", "Retrying"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    class ErrorType(models.TextChoices):
        """
        Set on the most recent failure. TEMPORARY (connection errors,
        timeouts, transient SMTP codes) is retried with backoff; PERMANENT
        (bad recipient address, auth failure, malformed header) is moved
        straight to FAILED - retrying it would just burn through attempts
        against an error that can never succeed. See tasks._is_permanent_error.
        """

        TEMPORARY = "temporary", "Temporary"
        PERMANENT = "permanent", "Permanent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    last_error = models.TextField(blank=True)
    error_type = models.CharField(max_length=10, choices=ErrorType.choices, blank=True)

    # When the next retry is scheduled for (set on RETRYING, cleared on
    # SENT/FAILED) - operational visibility into backoff timing, and the
    # signal recover_stale_outbox_events uses to find retries whose
    # countdown fired but were never picked up (see tasks.py).
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"], name="outbox_status_created_idx"),
            models.Index(fields=["status", "updated_at"], name="outbox_status_updated_idx"),
        ]

    def __str__(self):
        return f"{self.to_email} [{self.status}]"
