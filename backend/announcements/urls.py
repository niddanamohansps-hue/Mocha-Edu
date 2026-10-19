from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import AnnouncementViewSet

# SimpleRouter, not DefaultRouter: with an empty prefix DefaultRouter's
# API-root view would collide with the list route at the same URL.
router = SimpleRouter()
router.register(r"", AnnouncementViewSet, basename="announcement")

urlpatterns = [
    path("", include(router.urls)),
]
