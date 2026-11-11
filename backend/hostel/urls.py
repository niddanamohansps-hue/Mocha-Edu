from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AllocateView, HostelViewSet, RoomViewSet, StudentHostelView, VacateView

router = DefaultRouter()
router.register(r"hostels", HostelViewSet, basename="hostel")
router.register(r"rooms", RoomViewSet, basename="hostel-room")

urlpatterns = [
    path("allocations/", AllocateView.as_view(), name="hostel-allocate"),
    path("allocations/<uuid:allocation_id>/vacate/", VacateView.as_view(), name="hostel-vacate"),
    path("students/<uuid:student_id>/", StudentHostelView.as_view(), name="hostel-student"),
    path("", include(router.urls)),
]
