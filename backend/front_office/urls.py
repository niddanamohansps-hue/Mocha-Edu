from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    VisitorLogViewSet,
    StudentGatePassViewSet,
    PostalRecordViewSet,
    FrontOfficeOverviewView,
)

router = DefaultRouter()
router.register(r"visitors", VisitorLogViewSet, basename="visitors")
router.register(r"gate-passes", StudentGatePassViewSet, basename="gate-passes")
router.register(r"postal", PostalRecordViewSet, basename="postal")

urlpatterns = [
    path("overview/", FrontOfficeOverviewView.as_view(), name="front-office-overview"),
    path("", include(router.urls)),
]

