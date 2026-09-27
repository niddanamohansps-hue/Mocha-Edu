from django.contrib import admin
from django.db import connection

from .models import FeeHead, FeeStructure, Payment, PaymentAllocation, StudentFee


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


@admin.register(FeeHead)
class FeeHeadAdmin(TenantOnlyAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(FeeStructure)
class FeeStructureAdmin(TenantOnlyAdmin):
    list_display = ("fee_head", "academic_year", "level", "section", "amount", "frequency", "is_active")
    list_filter = ("academic_year", "frequency", "is_active")


@admin.register(StudentFee)
class StudentFeeAdmin(TenantOnlyAdmin):
    list_display = ("student", "fee_head", "academic_year", "amount_due", "discount_amount", "status", "due_date")
    list_filter = ("academic_year", "status", "fee_head")
    search_fields = ("student__enrollment_id",)


@admin.register(Payment)
class PaymentAdmin(TenantOnlyAdmin):
    """Immutable financial record - view/add only, never change or delete."""

    list_display = ("receipt_number", "student", "amount", "method", "status", "created_at")
    list_filter = ("method", "status", "created_at")
    search_fields = ("receipt_number", "student__enrollment_id")
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(TenantOnlyAdmin):
    """Immutable financial record - view/add only, never change or delete."""

    list_display = ("payment", "student_fee", "amount", "created_at")
    readonly_fields = [f.name for f in PaymentAllocation._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
