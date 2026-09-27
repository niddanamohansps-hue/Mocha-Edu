from django.contrib import admin
from django.db import connection
from .models import Period, Room, TimetableEntry, TimetableSubstitution


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


@admin.register(Period)
class PeriodAdmin(TenantOnlyAdmin):
    list_display = ("name", "academic_year", "order", "start_time", "end_time", "is_break")
    list_filter = ("academic_year", "is_break")


@admin.register(Room)
class RoomAdmin(TenantOnlyAdmin):
    list_display = ("name", "capacity")


@admin.register(TimetableEntry)
class TimetableEntryAdmin(TenantOnlyAdmin):
    list_display = ("section", "academic_year", "day_of_week", "period", "subject", "instructor", "room")
    list_filter = ("academic_year", "day_of_week")
    search_fields = ("section__name", "subject__name")


@admin.register(TimetableSubstitution)
class TimetableSubstitutionAdmin(TenantOnlyAdmin):
    list_display = ("timetable_entry", "date", "substitute_instructor", "created_by")
    list_filter = ("date",)
