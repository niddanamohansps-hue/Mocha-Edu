"""
Project-wide pagination standard for administrative list endpoints.

One shared class, reused everywhere a list endpoint needs pagination,
rather than each app inventing its own (notifications.views.NotificationPagination
and core.views.AuditLogPagination already independently converged on the
same page_size=20 shape - this consolidates that into one definition new
endpoints should use directly instead of redefining it a third time).

Deliberately NOT set as REST_FRAMEWORK's DEFAULT_PAGINATION_CLASS: this
project has ~15 existing ModelViewSets whose list() already calls
self.paginate_queryset() (DRF's default ListModelMixin behavior) while
having no pagination_class configured anywhere - meaning every one of them
currently returns a bare JSON array. Setting a global default would
silently flip EVERY one of those endpoints to the paginated envelope at
once, including several with no verified frontend consumer. Applying this
class explicitly, endpoint by endpoint, keeps each change auditable
against its actual frontend consumer.
"""

from rest_framework.pagination import PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
