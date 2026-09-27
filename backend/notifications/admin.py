from django.contrib import admin
from django.db import connection

from .models import Notification


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
