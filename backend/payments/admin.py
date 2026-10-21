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
        "failure_code",
        "created_at",
    ]
    list_filter = ["status", "failure_code", "created_at"]
    actions = ["retry_provisioning"]
    search_fields = ["transaction_uuid", "organization_name", "email", "subdomain"]
    # The stored signup password is never shown, and money/state fields are written only by the
    # signup flow, not by hand.
    exclude = ["password"]
    readonly_fields = [
        "transaction_uuid",
        "amount",
        "status",
        "expires_at",
        "paid_at",
        "gateway_reference",
        "provisioned_at",
        "provisioning_attempts",
        "gateway_checked_at",
        "attention_notified_at",
        "failure_code",
        "organization",
        "created_at",
        "updated_at",
    ]

    @admin.action(description="Retry creating the institution for the selected paid signups")
    def retry_provisioning(self, request, queryset):
        # A person has decided to retry: this works even for rows the automatic retries skip
        # (retries exhausted, or flagged for review). Only paid signups that still have no
        # institution are queued; the setup itself claims each one, so a double click is harmless.
        from .tasks import provision_signup_payment

        queued = 0
        for pk in queryset.filter(status__in=[Payment.PAID, Payment.PROVISIONING_FAILED]).values_list("pk", flat=True):
            provision_signup_payment.delay(pk)
            queued += 1
        self.message_user(request, f"Queued {queued} signup(s) for setup.")
