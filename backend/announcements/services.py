"""
Announcement business operations. Views and the scheduled-publish task go
through these functions; nothing else should change an announcement's
status, because these are the only places that keep status, recipient
snapshots, notifications, and the email outbox consistent.

Delivery reuses notifications.services unchanged: notify_many() for the
in-app inbox (a synchronous bulk_create) and queue_email() for email (an
outbox row written now, dispatched by Celery only after commit).
"""

import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from notifications.services import notify_many, queue_email

from .models import Announcement, AnnouncementRecipient

logger = logging.getLogger(__name__)

EMPTY_AUDIENCE_MESSAGE = "No eligible recipients were found for this audience."
NOTIFICATION_BODY_LIMIT = 500


class AnnouncementStateError(ValidationError):
    """An operation was attempted from a status that does not allow it."""


class AnnouncementAuthorizationError(ValidationError):
    """The creator or publisher lacks the required permissions at publication time."""


def _non_field(message):
    return {"non_field_errors": [message]}


# --- Recipient resolution ---------------------------------------------------


def _student_levels(announcement):
    from students.models import StudentLevel

    current = StudentLevel.objects.filter(is_current=True, student__status="active")
    if announcement.audience_type == Announcement.AudienceType.SECTION:
        return current.filter(section_id=announcement.audience_section_id)
    if announcement.audience_type == Announcement.AudienceType.LEVEL:
        return current.filter(level_id=announcement.audience_level_id)
    return current


def resolve_recipient_user_ids(announcement):
    """
    Returns the deduplicated set of canonical account ids (Profile.user_id)
    the announcement's audience resolves to in the current tenant schema.
    Only scalar user_id values are collected, so several Profile rows that
    reference the same account collapse to one recipient.
    """
    from families.models import StudentParentRelation
    from staff.models import StaffMember

    audience = announcement.audience_type
    A = Announcement.AudienceType
    user_ids = set()

    if audience in (A.ALL, A.ALL_STUDENTS, A.SECTION, A.LEVEL):
        user_ids.update(_student_levels(announcement).values_list("student__profile__user_id", flat=True))

    if audience in (A.ALL, A.ALL_PARENTS):
        user_ids.update(
            StudentParentRelation.objects.filter(student__status="active").values_list(
                "parent__profile__user_id", flat=True
            )
        )

    if audience in (A.ALL, A.ALL_STAFF):
        user_ids.update(StaffMember.objects.filter(is_active=True).values_list("profile__user_id", flat=True))

    user_ids.discard(None)
    return user_ids


def resolve_recipients(announcement):
    """
    Returns {user_id: email_or_None} for every eligible recipient. Accounts
    live in the shared schema (accounts is in SHARED_APPS), so one batched
    query resolves all emails. Ids with no matching account are dropped:
    they cannot log in to read an in-app notification either. A blank email
    keeps the recipient (in-app delivery still works) with email None.
    """
    from accounts.models import User

    user_ids = resolve_recipient_user_ids(announcement)
    if not user_ids:
        return {}
    accounts = User.objects.filter(id__in=user_ids, is_active=True).values_list("id", "email")
    return {user_id: (email or None) for user_id, email in accounts}


# --- Lifecycle operations ---------------------------------------------------


def _locked(announcement_id):
    """Row-locks the announcement for the current transaction."""
    try:
        return Announcement.objects.select_for_update().get(id=announcement_id)
    except Announcement.DoesNotExist:
        raise ValidationError(_non_field("Announcement not found."))


def check_publisher_authorization(announcement, user=None):
    """
    Validates that the creator (or explicit authorizing user) holds an active
    account and active tenant role with the necessary permissions at publication time.
    Fails closed if the user is missing, deactivated, or lacks required permissions.
    """
    from accounts.models import User
    from roles.models import UserRole

    if user is None:
        user = User.objects.filter(id=announcement.created_by_user_id).first()
        if not user:
            raise AnnouncementAuthorizationError(_non_field("Announcement creator account not found."))

    if not user.is_active:
        raise AnnouncementAuthorizationError(_non_field("Announcement creator account is deactivated."))

    if user.is_superuser:
        return True

    user_roles = list(UserRole.objects.filter(user_id=user.id, is_active=True).select_related("role"))
    if not user_roles:
        raise AnnouncementAuthorizationError(_non_field("Announcement creator has no active roles in this school."))

    if any(ur.role.slug == "owner" for ur in user_roles):
        return True

    permissions = set()
    for ur in user_roles:
        permissions.update(ur.role.permissions.values_list("codename", flat=True))

    if "manage_announcements" not in permissions:
        raise AnnouncementAuthorizationError(_non_field("Announcement creator lacks 'manage_announcements' permission."))

    if announcement.audience_type == Announcement.AudienceType.ALL:
        if "broadcast_announcements" not in permissions:
            raise AnnouncementAuthorizationError(_non_field("Announcement creator lacks 'broadcast_announcements' permission for school-wide broadcast."))

    return True


def publish_announcement(announcement_id, authorizing_user=None):
    """
    Publishes one announcement atomically. The row lock means two
    concurrent callers (a user and the scheduled task, or two overlapping
    workers) serialise here: the second sees PUBLISHED and is rejected, so
    recipients, notifications and emails are written exactly once.

    Database writes (status, recipient snapshots, Notification rows,
    EmailOutboxEvent rows) commit or roll back together. Email *dispatch*
    is deferred by queue_email() to after commit; a broker failure there
    leaves the committed publication intact and the outbox row PENDING for
    recover_stale_outbox_events to retry.
    """
    with transaction.atomic():
        announcement = _locked(announcement_id)
        if announcement.status == Announcement.Status.PUBLISHED:
            raise AnnouncementStateError(_non_field("This announcement has already been published."))
        if announcement.status == Announcement.Status.ARCHIVED:
            raise AnnouncementStateError(_non_field("An archived announcement cannot be published."))

        check_publisher_authorization(announcement, user=authorizing_user)

        recipients = resolve_recipients(announcement)
        if not recipients:
            raise ValidationError(_non_field(EMPTY_AUDIENCE_MESSAGE))

        # Status changes before save so an overdue scheduled announcement
        # passes model validation (published may keep a past scheduled_at).
        announcement.status = Announcement.Status.PUBLISHED
        announcement.published_at = timezone.now()
        announcement.save()

        email_targets = {uid: email for uid, email in recipients.items() if announcement.send_email and email}
        AnnouncementRecipient.objects.bulk_create(
            [
                AnnouncementRecipient(announcement=announcement, user_id=uid, email_sent=uid in email_targets)
                for uid in recipients
            ]
        )
        notify_many(
            recipient_user_ids=list(recipients),
            title=announcement.title,
            body=announcement.body[:NOTIFICATION_BODY_LIMIT],
            category="announcement",
            link=f"/dashboard/announcements/{announcement.id}",
        )
        for email in set(email_targets.values()):
            queue_email(to_email=email, subject=announcement.title, body=announcement.body)

    return announcement


def schedule_announcement(announcement_id, scheduled_at):
    with transaction.atomic():
        announcement = _locked(announcement_id)
        if announcement.status not in (Announcement.Status.DRAFT, Announcement.Status.SCHEDULED):
            raise AnnouncementStateError(_non_field("Only a draft or scheduled announcement can be scheduled."))
        announcement.status = Announcement.Status.SCHEDULED
        announcement.scheduled_at = scheduled_at
        announcement.save()
    return announcement


def cancel_schedule(announcement_id):
    with transaction.atomic():
        announcement = _locked(announcement_id)
        if announcement.status != Announcement.Status.SCHEDULED:
            raise AnnouncementStateError(_non_field("Only a scheduled announcement can be cancelled."))
        announcement.status = Announcement.Status.DRAFT
        announcement.scheduled_at = None
        announcement.save()
    return announcement


def archive_announcement(announcement_id):
    with transaction.atomic():
        announcement = _locked(announcement_id)
        if announcement.status != Announcement.Status.PUBLISHED:
            raise AnnouncementStateError(_non_field("Only a published announcement can be archived."))
        announcement.status = Announcement.Status.ARCHIVED
        announcement.save()
    return announcement


def revert_unpublishable_to_draft(announcement_id, reason=None):
    """
    Used by the scheduled task when a due announcement's audience is empty
    or authorization has been revoked: returning it to DRAFT stops it failing
    on every run and leaves it unpublished and visible to admins, instead of
    staying overdue forever.
    """
    with transaction.atomic():
        announcement = _locked(announcement_id)
        if announcement.status != Announcement.Status.SCHEDULED:
            return announcement
        announcement.status = Announcement.Status.DRAFT
        announcement.scheduled_at = None
        announcement.save()
        try:
            from core.models import AuditLog
            AuditLog.objects.create(
                actor_username="system",
                action="announcement_schedule_cancelled",
                model_name="Announcement",
                object_id=str(announcement.id),
                changes={"reason": reason or "Scheduled announcement reverted to draft"},
            )
        except Exception:
            logger.exception("Failed to write audit log for reverted announcement %s", announcement_id)
    return announcement
