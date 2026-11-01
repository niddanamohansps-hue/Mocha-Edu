import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction


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


class WhatsAppOutboxEvent(models.Model):
    """
    Transactional outbox for WhatsApp template messages, the same shape as EmailOutboxEvent: written in the
    caller's transaction, dispatched to Celery only once that has committed, retried with backoff on temporary
    failures and ended in SENT or FAILED. "Sent" means the provider accepted the message; delivery and read
    receipts are not tracked yet.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RETRYING = "retrying", "Retrying"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    to_phone = models.CharField(max_length=20)
    template = models.CharField(max_length=100)
    language = models.CharField(max_length=10, default="en")
    params = models.JSONField(default=list)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    last_error = models.TextField(blank=True)
    error_type = models.CharField(max_length=10, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "updated_at"], name="wa_outbox_status_updated_idx"),
        ]

    def __str__(self):
        return f"{self.template} [{self.status}]"


class NotificationSettings(models.Model):
    """
    Per-school alert settings: exactly one row per tenant schema, enforced by the
    database (see ``singleton``), not by convention.

    Every alert type defaults to OFF, and the row does not exist until an
    administrator first saves it: ``load()`` returns an unsaved default instance
    when there is no row, so reading settings never writes anything and an
    upgrade never switches alerts on for an existing school.

    Time zone: all scheduling and "today" logic in the alert stages uses the
    project's ``TIME_ZONE`` (UTC). There is deliberately no school time zone yet;
    it must exist before schedule-sensitive triggers are relied on.
    """

    EDITABLE_FIELDS = (
        "fee_reminders_enabled",
        "absence_alerts_enabled",
        "payment_receipts_enabled",
        "low_stock_alerts_enabled",
        "fee_reminder_days_before",
        "overdue_reminder_interval_days",
        "max_overdue_reminders",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Always True and unique: a second row cannot exist.
    singleton = models.BooleanField(default=True, unique=True, editable=False)

    fee_reminders_enabled = models.BooleanField(default=False)
    absence_alerts_enabled = models.BooleanField(default=False)
    payment_receipts_enabled = models.BooleanField(default=False)
    low_stock_alerts_enabled = models.BooleanField(default=False)

    fee_reminder_days_before = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(0), MaxValueValidator(30)]
    )
    overdue_reminder_interval_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1), MaxValueValidator(30)]
    )
    max_overdue_reminders = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )

    # Soft link to the (public-schema) user who last saved the settings.
    updated_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Notification settings"
        constraints = [
            models.CheckConstraint(condition=models.Q(singleton=True), name="notifsettings_singleton_true"),
            models.CheckConstraint(
                condition=models.Q(fee_reminder_days_before__gte=0, fee_reminder_days_before__lte=30),
                name="notifsettings_days_before_range",
            ),
            models.CheckConstraint(
                condition=models.Q(overdue_reminder_interval_days__gte=1, overdue_reminder_interval_days__lte=30),
                name="notifsettings_interval_range",
            ),
            models.CheckConstraint(
                condition=models.Q(max_overdue_reminders__gte=1, max_overdue_reminders__lte=10),
                name="notifsettings_max_reminders_range",
            ),
        ]

    def __str__(self):
        return "Notification settings"

    @classmethod
    def load(cls):
        """The saved settings, or an UNSAVED default instance. Never writes."""
        return cls.objects.filter(singleton=True).first() or cls()

    def editable_values(self):
        return {name: getattr(self, name) for name in self.EDITABLE_FIELDS}

    @classmethod
    def update_singleton(cls, *, user_id=None, **values):
        """
        Applies ``values`` to the one settings row, creating it on first use.
        Returns ``(settings, previous_values)``.

        Concurrency: creation goes through ``get_or_create`` on the unique
        ``singleton`` column, so simultaneous first requests end up with one row
        (the loser's insert fails and it re-reads). The row is then re-read with
        ``SELECT ... FOR UPDATE`` before the new values are applied, so two
        concurrent partial updates are serialized and neither is lost.
        """
        unknown = set(values) - set(cls.EDITABLE_FIELDS)
        if unknown:
            raise ValueError(f"Not editable: {sorted(unknown)}")

        with transaction.atomic():
            cls.objects.get_or_create(singleton=True)
            instance = cls.objects.select_for_update().get(singleton=True)
            previous = instance.editable_values()
            for name, value in values.items():
                setattr(instance, name, value)
            instance.updated_by_user_id = user_id
            instance.full_clean()
            instance.save()
        return instance, previous


class AlertLog(models.Model):
    """
    One automated alert to one recipient. The (kind, dedupe_key, recipient) unique
    constraint is what makes sending idempotent: it is claimed by inserting this
    row, in the same transaction as the inbox notification and the outbox email
    (see ``notifications.alerts.dispatch_alert``).

    Deliberately stores no names, amounts or email addresses: only ids, the
    student's enrollment id and a masked recipient hint, snapshotted when the
    alert was sent. Delivery status is not duplicated here: it is read from the
    linked outbox event.
    """

    class Kind(models.TextChoices):
        FEE_DUE_SOON = "fee_due_soon", "Fee due soon"
        FEE_OVERDUE = "fee_overdue", "Fee overdue"
        ABSENCE = "absence", "Absence"
        PAYMENT_RECEIPT = "payment_receipt", "Payment receipt"
        EXAM_DATE_SHEET = "exam_date_sheet", "Exam date sheet"

    IN_APP_ONLY = "in_app_only"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=30, choices=Kind.choices)
    # Stable identity of the logical alert, e.g. "absence:<student_id>:<date>".
    dedupe_key = models.CharField(max_length=120)
    recipient_user_id = models.UUIDField()
    recipient_hint = models.CharField(max_length=80, blank=True)
    # No foreign key: deleting a student must never cascade into the log.
    student_id = models.UUIDField()
    enrollment_id = models.CharField(max_length=50, blank=True, db_index=True)

    notification_id = models.UUIDField(null=True, blank=True)
    outbox_event = models.ForeignKey(
        EmailOutboxEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Set for a WhatsApp alert. Its recipient_user_id then holds the parent's id (parents need no login to be
    # messaged on WhatsApp), which cannot collide with a user id.
    whatsapp_event = models.ForeignKey(
        WhatsAppOutboxEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "dedupe_key", "recipient_user_id"], name="alertlog_unique_alert"
            ),
        ]
        indexes = [models.Index(fields=["kind", "created_at"], name="alertlog_kind_created_idx")]

    def __str__(self):
        return f"{self.kind} [{self.dedupe_key}]"

    @property
    def delivery_status(self):
        """The outbox event's own status (pending / retrying / sent / failed), or
        ``in_app_only`` when no email was queued."""
        if self.outbox_event_id is not None:
            return self.outbox_event.status
        if self.whatsapp_event_id is not None:
            return self.whatsapp_event.status
        return self.IN_APP_ONLY


class PushSubscription(models.Model):
    """
    One browser or phone that agreed to receive push notifications for a user (Web Push). The endpoint and
    keys come from the browser; they are useless without the platform's private VAPID key. A subscription
    the push service reports as gone (404/410) is deleted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    failures = models.PositiveSmallIntegerField(default=0)
