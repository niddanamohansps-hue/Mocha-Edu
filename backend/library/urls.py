from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    BookCategoryViewSet,
    BookCopyViewSet,
    BookViewSet,
    FineViewSet,
    LibrarySettingsView,
    LibrarySummaryView,
    LoanViewSet,
)

router = SimpleRouter()
router.register(r"categories", BookCategoryViewSet, basename="library-category")
router.register(r"books", BookViewSet, basename="library-book")
router.register(r"copies", BookCopyViewSet, basename="library-copy")
router.register(r"loans", LoanViewSet, basename="library-loan")
router.register(r"fines", FineViewSet, basename="library-fine")

urlpatterns = [
    path("settings/", LibrarySettingsView.as_view(), name="library-settings"),
    path("summary/", LibrarySummaryView.as_view(), name="library-summary"),
    path("", include(router.urls)),
]
