from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import connection
from .models import User
from roles.models import UserRole


class GlobalOnlyAdminMixin:
    """
    Mixin to restrict visibility of Shared App models
    to the Public Dashboard only.
    """

    def has_module_permission(self, request):
        return connection.schema_name == "public"

    def has_view_permission(self, request, obj=None):
        return connection.schema_name == "public"

    def has_add_permission(self, request):
        return connection.schema_name == "public"

    def has_change_permission(self, request, obj=None):
        return connection.schema_name == "public"

    def has_delete_permission(self, request, obj=None):
        return connection.schema_name == "public"


# class UserRoleInline(admin.TabularInline):
#     model = UserRole
#     extra = 0
#     can_delete = True


@admin.register(User)
class UserAdmin(GlobalOnlyAdminMixin, BaseUserAdmin):
    list_display = ("email", "is_staff", "is_active", "created_at")
    list_filter = ("is_staff", "is_active")
    search_fields = ("email",)
    ordering = ("email",)
    readonly_fields = ("created_at", "updated_at")

    # inlines = [UserRoleInline]  # UserRole is tenant-specific, cannot show in public admin

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_active",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_active"),
            },
        ),
    )
