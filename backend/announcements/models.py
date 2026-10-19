import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Announcement(models.Model):
    """
    A school notice addressed to an audience. Recipients are resolved and
    notified only at publish time (announcements.services, Phase 2); this
    model stores the audience rule, not the recipient list.
    """

    class AudienceType(models.TextChoices):
        ALL = "all", "Everyone"
        ALL_STAFF = "all_staff", "All Staff"
        ALL_PARENTS = "all_parents", "All Parents"
        ALL_STUDENTS = "all_students", "All Students"
        SECTION = "section", "Section"
        LEVEL = "level", "Level"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    body = models.TextField()

    # Soft link to accounts.User (public schema), same convention as
    # notifications.Notification.recipient_user_id - never a cross-schema FK.
    created_by_user_id = models.UUIDField(db_index=True)

    audience_type = models.CharField(max_length=20, choices=AudienceType.choices)
    audience_section = models.ForeignKey(
        "academics.Section",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="announcements",
    )
    audience_level = models.ForeignKey(
        "academics.AcademicLevel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="announcements",
    )

    send_email = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    def clean(self):
        errors = {}

        if self.audience_type == self.AudienceType.SECTION:
            if not self.audience_section_id:
                errors["audience_section"] = "A section is required for a section audience."
            if self.audience_level_id:
                errors["audience_level"] = "A section audience cannot also set a level."
        elif self.audience_type == self.AudienceType.LEVEL:
            if not self.audience_level_id:
                errors["audience_level"] = "A level is required for a level audience."
            if self.audience_section_id:
                errors["audience_section"] = "A level audience cannot also set a section."
        else:
            if self.audience_section_id:
                errors["audience_section"] = "Only a section audience can set a section."
            if self.audience_level_id:
                errors["audience_level"] = "Only a level audience can set a level."

        # Published/archived announcements keep their (now past) scheduled_at,
        # so the scheduling rules only apply before publication. They apply on
        # every save, not just creation, so an overdue scheduled announcement
        # cannot be silently re-saved as valid.
        now = timezone.now()
        if self.status == self.Status.DRAFT:
            if self.scheduled_at is not None and self.scheduled_at <= now:
                errors["scheduled_at"] = "The scheduled time must be in the future."
        elif self.status == self.Status.SCHEDULED:
            if self.scheduled_at is None:
                errors["scheduled_at"] = "A scheduled announcement requires a scheduled time."
            elif self.scheduled_at <= now:
                errors["scheduled_at"] = (
                    "The scheduled time must be in the future."
                    if self._state.adding
                    else "This announcement's scheduled time has passed. Reschedule it to a future time or cancel it."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Same convention as examinations.GradeBoundary: every ordinary save
        # is validated. QuerySet.update()/bulk_create() bypass save() and
        # therefore this check; this app's code must not use them for
        # Announcement writes.
        self.full_clean()
        super().save(*args, **kwargs)


class AnnouncementRecipient(models.Model):
    """
    Persisted delivery snapshot: one row per canonical account an
    announcement was resolved to at publish time. Never re-derived from
    current audience membership.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="recipients"
    )
    user_id = models.UUIDField(db_index=True)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("announcement", "user_id")

    def __str__(self):
        return f"{self.announcement_id} -> {self.user_id}"
