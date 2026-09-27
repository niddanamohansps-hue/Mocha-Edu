from django.contrib import admin
from django.db import connection
from .models import AttendanceSession, AttendanceSettings, StaffAttendance, StudentAttendance


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


class StudentAttendanceInline(admin.TabularInline):
    model = StudentAttendance
    extra = 0
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(TenantOnlyAdmin):
    list_display = ("section", "date", "is_locked", "recorded_by", "created_at")
    list_filter = ("is_locked", "date")
    search_fields = ("section__name",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [StudentAttendanceInline]


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(TenantOnlyAdmin):
    list_display = ("staff", "date", "status", "recorded_by")
    list_filter = ("status", "date")
    search_fields = ("staff__employee_id",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(AttendanceSettings)
class AttendanceSettingsAdmin(TenantOnlyAdmin):
    list_display = ("minimum_attendance_percentage", "lock_after_days", "updated_at")
    readonly_fields = ("created_at", "updated_at")
