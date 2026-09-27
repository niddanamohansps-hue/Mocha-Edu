from django.contrib import admin
from django.db import connection
from .models import Payment


class GlobalOnlyAdmin(admin.ModelAdmin):
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


@admin.register(Payment)
class PaymentAdmin(GlobalOnlyAdmin):
    list_display = [
        "transaction_uuid",
        "organization_name",
        "amount",
        "status",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["transaction_uuid", "organization_name", "email", "subdomain"]
    readonly_fields = ["transaction_uuid", "created_at", "updated_at"]
