from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AssetCategoryViewSet,
    AssetViewSet,
    ItemCategoryViewSet,
    ItemViewSet,
    PurchaseViewSet,
    StockLevelViewSet,
    StockLocationViewSet,
    StockMovementViewSet,
    SupplierViewSet,
)

router = SimpleRouter()
router.register(r"categories", ItemCategoryViewSet, basename="inventory-category")
router.register(r"locations", StockLocationViewSet, basename="inventory-location")
router.register(r"items", ItemViewSet, basename="inventory-item")
router.register(r"stock", StockLevelViewSet, basename="inventory-stock")
router.register(r"suppliers", SupplierViewSet, basename="inventory-supplier")
router.register(r"purchases", PurchaseViewSet, basename="inventory-purchase")
router.register(r"asset-categories", AssetCategoryViewSet, basename="inventory-asset-category")
router.register(r"assets", AssetViewSet, basename="inventory-asset")
router.register(r"movements", StockMovementViewSet, basename="inventory-movement")

urlpatterns = [
    path("", include(router.urls)),
]
