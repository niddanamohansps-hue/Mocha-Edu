from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    DriverViewSet,
    ExpiringDocumentsView,
    RouteStopViewSet,
    RouteViewSet,
    StudentTransportViewSet,
    TransportBillViewSet,
    VehicleViewSet,
)

router = SimpleRouter()
router.register(r"vehicles", VehicleViewSet, basename="transport-vehicle")
router.register(r"drivers", DriverViewSet, basename="transport-driver")
router.register(r"routes", RouteViewSet, basename="transport-route")
router.register(r"stops", RouteStopViewSet, basename="transport-stop")
router.register(r"seats", StudentTransportViewSet, basename="transport-seat")
router.register(r"bills", TransportBillViewSet, basename="transport-bill")

urlpatterns = [
    path("expiring/", ExpiringDocumentsView.as_view(), name="transport-expiring"),
    path("", include(router.urls)),
]
