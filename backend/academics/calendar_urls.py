from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CalendarEventViewSet

router = DefaultRouter()
router.register(r"", CalendarEventViewSet, basename="calendar-events-root")

urlpatterns = [
    path("", include(router.urls)),
]

