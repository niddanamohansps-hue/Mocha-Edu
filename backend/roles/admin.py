from django.contrib import admin
from django.db import connection
from .models import Role, UserRole


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


@admin.register(Role)
class RoleAdmin(TenantOnlyAdmin):
    list_display = ("name", "slug", "is_system_role", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("is_system_role",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserRole)
class UserRoleAdmin(TenantOnlyAdmin):
    list_display = ("user", "role", "is_active", "created_at")
    search_fields = ("user__email", "role__name")
    list_filter = ("role", "is_active")
    readonly_fields = ("created_at",)
