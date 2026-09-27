import uuid

from django.db import models


class AuditLog(models.Model):
    """
    Tenant-scoped record of security-sensitive actions (role changes,
    password changes, credential views, etc). Lives per-tenant-schema like
    every other tenant model, so one school's audit trail is never visible
    to another.

    actor_id is a soft link (not an FK) to accounts.User, following the same
    pattern already used by profiles.Profile.user_id - the User model lives
    in the public schema, so a real FK across schemas isn't possible here.
    actor_username is denormalized so a log entry stays readable even if the
    referenced user is later deleted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    actor_id = models.UUIDField(null=True, blank=True)
    actor_username = models.CharField(max_length=150, null=True, blank=True)

    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    changes = models.JSONField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["model_name", "object_id"]),
            models.Index(fields=["-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor_username or 'system'} {self.action} {self.model_name}:{self.object_id}"
