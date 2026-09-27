from django.contrib import admin
from .models import Profile, InstitutionProfile
from django.db import connection


class TenantOnlyAdmin(admin.ModelAdmin):
    """
    Helper to prevent tenant-specific models from appearing or crashing
    the Global (Public) Admin.
    """

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


@admin.register(Profile)
class ProfileAdmin(TenantOnlyAdmin):
    list_display = ("first_name", "last_name", "user_id", "phone", "gender")
    list_filter = ("gender", "blood_group")
    search_fields = ("first_name", "last_name", "phone")
    readonly_fields = ("created_at", "updated_at")

    def get_inlines(self, request, obj):
        if connection.schema_name == "public":
            return []

        inlines = []
        # Student Inline
        try:
            from students.admin import StudentInline

            inlines.append(StudentInline)
        except ImportError:
            pass

        # Staff Inline
        try:
            from staff.admin import StaffMemberInline

            inlines.append(StaffMemberInline)
        except ImportError:
            pass

        # Parent Inline
        try:
            from families.admin import ParentInline

            inlines.append(ParentInline)
        except ImportError:
            pass

        return inlines


@admin.register(InstitutionProfile)
class InstitutionProfileAdmin(TenantOnlyAdmin):
    list_display = ("organization_id", "website", "established_date")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("website",)
