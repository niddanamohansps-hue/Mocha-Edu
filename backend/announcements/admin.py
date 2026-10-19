from django.contrib import admin
from django.db import connection

from .models import Announcement, AnnouncementRecipient


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


@admin.register(Announcement)
class AnnouncementAdmin(TenantOnlyAdmin):
    """Read-only inspection. Publishing must go through
    announcements.services so recipients and notifications are created."""

    list_display = ("title", "audience_type", "status", "scheduled_at", "published_at", "created_at")
    list_filter = ("status", "audience_type", "created_at")
    search_fields = ("title", "body")
    readonly_fields = [f.name for f in Announcement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AnnouncementRecipient)
class AnnouncementRecipientAdmin(TenantOnlyAdmin):
    list_display = ("announcement", "user_id", "email_sent", "created_at")
    list_filter = ("email_sent",)
    search_fields = ("user_id",)
    readonly_fields = [f.name for f in AnnouncementRecipient._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
