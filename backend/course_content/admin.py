from django.contrib import admin
from django.db import connection
from .models import CourseContent, SubjectEnrollment, Assignment, AssignmentSubmission


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


@admin.register(CourseContent)
class CourseContentAdmin(TenantOnlyAdmin):
    list_display = ["title", "content_type", "created_by", "is_published", "created_at"]
    list_filter = ["content_type", "is_published", "is_pinned", "created_at"]
    search_fields = ["title", "description"]
    filter_horizontal = [
        "target_programs",
        "target_levels",
        "target_sections",
        "target_subjects",
        "specific_students",
    ]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SubjectEnrollment)
class SubjectEnrollmentAdmin(TenantOnlyAdmin):
    list_display = ["student", "subject", "academic_year", "enrolled_at"]
    list_filter = ["academic_year", "enrolled_at"]
    search_fields = [
        "student__profile__first_name",
        "student__profile__last_name",
        "subject__name",
    ]
    readonly_fields = ["enrolled_at"]


@admin.register(Assignment)
class AssignmentAdmin(TenantOnlyAdmin):
    list_display = ["content", "due_date", "total_points", "submission_type"]
    list_filter = ["submission_type", "allow_late_submission", "due_date"]
    readonly_fields = ["content"]


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(TenantOnlyAdmin):
    list_display = ["assignment", "student", "status", "score", "submitted_at"]
    list_filter = ["status", "submitted_at", "graded_at"]
    search_fields = ["student__profile__first_name", "student__profile__last_name"]
    readonly_fields = ["created_at", "updated_at", "is_late"]
