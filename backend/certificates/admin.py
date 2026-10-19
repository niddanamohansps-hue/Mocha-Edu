from django.contrib import admin

from .models import Certificate, CertificateSettings


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    """Read-only: certificates change only through the audited services, so the
    integrity hash stays meaningful."""

    list_display = ("certificate_number", "certificate_type", "status", "issue_date")
    search_fields = ("certificate_number",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(CertificateSettings)
