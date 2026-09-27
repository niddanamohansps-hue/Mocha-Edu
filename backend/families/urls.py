from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ParentCredentialDistributionView,
    ParentPortalActivationView,
    ParentViewSet,
    StudentParentRelationViewSet,
)

router = DefaultRouter()
router.register(r"parents", ParentViewSet)
router.register(r"relations", StudentParentRelationViewSet)

urlpatterns = [
    path(
        "activate-parent/",
        ParentPortalActivationView.as_view(),
        name="parent-portal-activation",
    ),
    path(
        "credentials-parents/",
        ParentCredentialDistributionView.as_view(),
        name="parent-credentials",
    ),
    path("", include(router.urls)),
]
