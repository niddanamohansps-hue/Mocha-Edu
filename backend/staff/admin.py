from django.contrib import admin
from django.db import connection
from .models import StaffMember, Instructor


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


class InstructorInline(admin.StackedInline):
    model = Instructor
    extra = 0
    can_delete = True


class StaffMemberInline(admin.StackedInline):
    model = StaffMember
    extra = 0
    can_delete = False
    verbose_name = "Staff record for this Identity"


@admin.register(StaffMember)
class StaffMemberAdmin(TenantOnlyAdmin):
    list_display = (
        "get_full_name",
        "employee_id",
        "designation",
        "department",
        "is_active",
        "joining_date",
    )
    list_filter = ("is_active", "department", "designation")
    search_fields = (
        "profile__first_name",
        "profile__last_name",
        "employee_id",
        "designation",
    )
    inlines = [InstructorInline]
    raw_id_fields = ("profile",)

    def get_full_name(self, obj):
        return f"{obj.profile.first_name} {obj.profile.last_name}"

    get_full_name.short_description = "Name"


@admin.register(Instructor)
class InstructorAdmin(TenantOnlyAdmin):
    list_display = ("get_staff_name", "specialization", "license_number")
    search_fields = ("staff_member__profile__first_name", "specialization")

    def get_staff_name(self, obj):
        return f"{obj.staff_member.profile.first_name} {obj.staff_member.profile.last_name}"

    get_staff_name.short_description = "Staff Member"
