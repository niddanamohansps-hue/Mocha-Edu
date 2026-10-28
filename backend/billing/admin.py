from django.contrib import admin

from payments.admin import GlobalOnlyAdmin

from .models import Invoice, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(GlobalOnlyAdmin):
    list_display = ["name", "code", "monthly_price", "yearly_price", "one_time_price", "one_time_validity_days",
                    "student_limit", "trial_days", "is_public", "sort_order"]
    list_editable = ["monthly_price", "yearly_price", "one_time_price", "trial_days", "is_public", "sort_order"]
    prepopulated_fields = {"code": ("name",)}
    readonly_fields = ["razorpay_monthly_plan_id", "razorpay_yearly_plan_id", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "code", "description", "features", "student_limit", "is_public", "sort_order"]}),
        ("Prices in ₹, before GST (leave empty to not offer that way)", {
            "fields": ["monthly_price", "yearly_price", "one_time_price", "one_time_validity_days", "gst_percent"]}),
        ("Free trial", {"fields": ["trial_days"]}),
        ("Razorpay (filled in automatically)", {"fields": ["razorpay_monthly_plan_id", "razorpay_yearly_plan_id",
                                                           "created_at", "updated_at"]}),
    ]


class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    can_delete = False
    fields = ["number", "status", "cycle", "total", "period_start", "period_end", "paid_at"]
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(GlobalOnlyAdmin):
    list_display = ["organization", "plan", "cycle", "status", "paid_until", "trial_ends_at", "is_legacy"]
    list_filter = ["status", "cycle", "plan", "is_legacy"]
    search_fields = ["organization__name", "organization__schema_name"]
    readonly_fields = ["razorpay_subscription_id", "created_at", "updated_at"]
    inlines = [InvoiceInline]


@admin.register(Invoice)
class InvoiceAdmin(GlobalOnlyAdmin):
    list_display = ["number", "billed_name", "plan_name", "cycle", "total", "status", "paid_at"]
    list_filter = ["status", "cycle"]
    search_fields = ["number", "billed_name", "razorpay_payment_id"]
    # Invoices are records of money: never edited by hand.
    readonly_fields = [f.name for f in Invoice._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
