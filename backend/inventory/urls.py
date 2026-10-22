from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    ItemCategoryViewSet,
    ItemViewSet,
    StockLevelViewSet,
    StockLocationViewSet,
    StockMovementViewSet,
)

router = SimpleRouter()
router.register(r"categories", ItemCategoryViewSet, basename="inventory-category")
router.register(r"locations", StockLocationViewSet, basename="inventory-location")
router.register(r"items", ItemViewSet, basename="inventory-item")
router.register(r"stock", StockLevelViewSet, basename="inventory-stock")
router.register(r"movements", StockMovementViewSet, basename="inventory-movement")

urlpatterns = [
    path("", include(router.urls)),
]
