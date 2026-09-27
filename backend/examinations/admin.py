from django.contrib import admin
from django.db import connection
from .models import ExamMark, ExamResult, ExamSchedule, Examination, ExamType, GradeBoundary


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


@admin.register(ExamType)
class ExamTypeAdmin(TenantOnlyAdmin):
    list_display = ("name", "order")


@admin.register(Examination)
class ExaminationAdmin(TenantOnlyAdmin):
    list_display = ("name", "academic_year", "exam_type", "start_date", "end_date", "is_published")
    list_filter = ("academic_year", "is_published")


@admin.register(ExamSchedule)
class ExamScheduleAdmin(TenantOnlyAdmin):
    list_display = ("examination", "subject", "section", "date", "start_time", "end_time", "is_locked")
    list_filter = ("date", "is_locked")


@admin.register(ExamMark)
class ExamMarkAdmin(TenantOnlyAdmin):
    list_display = ("exam_schedule", "student", "marks_obtained", "is_absent")
    list_filter = ("is_absent",)


@admin.register(ExamResult)
class ExamResultAdmin(TenantOnlyAdmin):
    list_display = ("examination", "student", "percentage", "overall_grade", "is_pass", "published_at")
    list_filter = ("is_pass", "academic_year")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GradeBoundary)
class GradeBoundaryAdmin(TenantOnlyAdmin):
    list_display = ("grade_label", "academic_year", "min_percentage", "max_percentage", "grade_point")
    list_filter = ("academic_year",)
