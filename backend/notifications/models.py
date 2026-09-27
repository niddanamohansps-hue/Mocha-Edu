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
