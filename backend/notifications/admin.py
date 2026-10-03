from django.contrib import admin
from django.db import connection

from .models import Notification, EmailOutboxEvent


class TenantOnlyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return connection.schema_name != "public"

    def has_view_permission(self, request, obj=None):
        return connection.schema_name != "public"

    def has_add_permission(self, request):
        return connection.schema_name != "public"

    def has_change_permission(self, request, obj=None):
        return connection.schema_name != "public"

    def has_delete_permission(self, request, obj=None):
        return connection.schema_name != "public"


@admin.register(Notification)
class NotificationAdmin(TenantOnlyAdmin):
    """Read-only inspection only - no compose/broadcast action. The
    application service (notifications.services.notify/notify_many) is the
    only intended way to create a Notification."""

    list_display = ("recipient_user_id", "title", "category", "is_read", "created_at")
    list_filter = ("category", "is_read", "created_at")
    search_fields = ("title", "body", "recipient_user_id")
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(EmailOutboxEvent)
class EmailOutboxEventAdmin(TenantOnlyAdmin):
    """
    Read-only operational visibility into the async email outbox - useful
    for seeing stuck/FAILED deliveries without a direct DB query. Creation
    is only ever via notifications.services.queue_email().
    """

    list_display = (
        "to_email",
        "subject",
        "status",
        "attempts",
        "error_type",
        "next_attempt_at",
        "created_at",
        "sent_at",
    )
    list_filter = ("status", "error_type", "created_at")
    search_fields = ("to_email", "subject", "last_error")
    readonly_fields = [f.name for f in EmailOutboxEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
