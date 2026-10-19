from django.contrib import admin
from django.db import connection
from .models import Student, AcademicHistory, StudentLevel


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


class AcademicHistoryInline(admin.TabularInline):
    model = AcademicHistory
    extra = 1


class StudentLevelInline(admin.TabularInline):
    model = StudentLevel
    extra = 0
    sortable_field_name = "academic_year"


class StudentInline(admin.StackedInline):
    model = Student
    extra = 0
    can_delete = False
    verbose_name = "Student record for this Identity"


@admin.register(Student)
class StudentAdmin(TenantOnlyAdmin):
    list_display = (
        "get_full_name",
        "enrollment_id",
        "status",
        "admission_date",
        "get_current_level",
    )
    list_filter = ("status", "enrollments__level", "enrollments__is_current")
    search_fields = ("profile__first_name", "profile__last_name", "enrollment_id")
    inlines = [StudentLevelInline, AcademicHistoryInline]
    raw_id_fields = ("profile",)

    def get_full_name(self, obj):
        return f"{obj.profile.first_name} {obj.profile.last_name}"

    get_full_name.short_description = "Name"

    def get_current_level(self, obj):
        current = obj.enrollments.filter(is_current=True).first()
        return f"{current.level} ({current.section})" if current else "N/A"

    get_current_level.short_description = "Current Level"


@admin.register(StudentLevel)
class StudentLevelAdmin(TenantOnlyAdmin):
    list_display = ("student", "level", "section", "academic_year", "is_current")
    list_filter = ("level", "academic_year", "is_current")
    search_fields = ("student__profile__first_name", "student__enrollment_id")


from .models import (
    AdmissionEnquiry,
    AdmissionApplication,
    AdmissionDocument,
    AdmissionInterview,
    AdmissionActivityLog,
)


@admin.register(AdmissionEnquiry)
class AdmissionEnquiryAdmin(TenantOnlyAdmin):
    list_display = ("enquiry_number", "student_name", "guardian_name", "guardian_phone", "preferred_level", "academic_year", "status", "enquiry_date")
    list_filter = ("status", "source", "academic_year")
    search_fields = ("enquiry_number", "student_name", "guardian_name", "guardian_phone")


class AdmissionDocumentInline(admin.TabularInline):
    model = AdmissionDocument
    extra = 0
    fields = ("document_type", "title", "file", "verification_status", "verified_by", "rejection_reason")


class AdmissionInterviewInline(admin.TabularInline):
    model = AdmissionInterview
    extra = 0
    fields = ("interview_type", "scheduled_at", "status", "score", "recommendation")


class AdmissionActivityLogInline(admin.TabularInline):
    model = AdmissionActivityLog
    extra = 0
    readonly_fields = ("action", "from_status", "to_status", "performed_by", "notes", "created_at")
    can_delete = False


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(TenantOnlyAdmin):
    list_display = ("application_number", "first_name", "last_name", "level", "academic_year", "status", "submission_date", "student")
    list_filter = ("status", "academic_year", "level")
    search_fields = ("application_number", "first_name", "last_name", "phone", "guardian_phone")
    inlines = [AdmissionDocumentInline, AdmissionInterviewInline, AdmissionActivityLogInline]


@admin.register(AdmissionDocument)
class AdmissionDocumentAdmin(TenantOnlyAdmin):
    list_display = ("title", "application", "document_type", "verification_status", "verified_by", "uploaded_at")
    list_filter = ("document_type", "verification_status")
    search_fields = ("title", "application__application_number")


@admin.register(AdmissionInterview)
class AdmissionInterviewAdmin(TenantOnlyAdmin):
    list_display = ("application", "interview_type", "scheduled_at", "status", "recommendation")
    list_filter = ("interview_type", "status", "recommendation")
    search_fields = ("application__application_number",)

