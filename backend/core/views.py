import django_filters
from django_filters import rest_framework as drf_filters
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from roles.permissions import HasPermission

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogFilter(drf_filters.FilterSet):
    """
    actor_id/action/model_name/object_id are simple exact-match filters.
    date_from/date_to are range filters over created_at's date component.
    Inherits from django_filters.rest_framework.FilterSet (not the bare
    django_filters.FilterSet) specifically so an invalid date string raises
    a normal DRF ValidationError (400) instead of being silently ignored.
    """

    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = ["actor_id", "action", "model_name", "object_id", "date_from", "date_to"]


class AuditLogPagination(PageNumberPagination):
    """
    Same pattern as notifications.views.NotificationPagination - there is
    no project-wide pagination config (confirmed: no DEFAULT_PAGINATION_CLASS
    anywhere in settings.py), so this turns on DRF's stock paginator for
    this endpoint only, without touching any other view's behavior.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/audit-logs/        - list, filterable, paginated, newest first
    GET /api/audit-logs/{id}/   - retrieve

    Read-only by construction: ReadOnlyModelViewSet only ever wires up
    list/retrieve, so POST/PUT/PATCH/DELETE are unreachable regardless of
    permissions or router registration - there is no create/update/destroy
    method for them to call.

    Tenant isolation is NOT implemented here - it comes entirely from
    django-tenants' schema search_path, set by TenantMainMiddleware from
    the request's Host header, exactly like every other tenant-scoped
    ViewSet in this project (e.g. fees.views.FeeHeadViewSet's
    `FeeHead.objects.all()`). AuditLog.objects.all() therefore only ever
    reaches the current tenant's own rows - a second tenant-resolution
    mechanism would be redundant and risks diverging from that guarantee.

    Repo-wide audit of every log_action() call site's `changes=` payload
    (grepped for password/secret/token/credential/key, case-insensitive)
    found none - the existing audit logging never puts sensitive values
    into the JSON this endpoint exposes.
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, HasPermission("view_audit_log")]
    pagination_class = AuditLogPagination
    filter_backends = [drf_filters.DjangoFilterBackend]
    filterset_class = AuditLogFilter

    def get_queryset(self):
        # AuditLog.Meta.ordering is already ["-created_at"], so this is
        # just explicit about the newest-first contract rather than
        # relying silently on the model default.
        return AuditLog.objects.all().order_by("-created_at")
