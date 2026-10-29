from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ParentAvailableSlotsView,
    ParentBookSlotView,
    ParentCancelBookingView,
    ParentMyBookingsView,
    ParentPTMSessionsView,
    PTMSessionViewSet,
    PTMSlotViewSet,
    TeacherScheduleView,
)

router = DefaultRouter()
router.register(r"sessions", PTMSessionViewSet, basename="ptm-sessions")
router.register(r"slots", PTMSlotViewSet, basename="ptm-slots")

urlpatterns = [
    # Admin / Staff / Teacher endpoints
    path("", include(router.urls)),
    path("my-schedule/", TeacherScheduleView.as_view(), name="ptm-teacher-schedule"),
    # Parent portal PTM endpoints
    path("parent/sessions/", ParentPTMSessionsView.as_view(), name="ptm-parent-sessions"),
    path(
        "parent/available-slots/",
        ParentAvailableSlotsView.as_view(),
        name="ptm-parent-available-slots",
    ),
    path("parent/book/", ParentBookSlotView.as_view(), name="ptm-parent-book"),
    path("parent/cancel/", ParentCancelBookingView.as_view(), name="ptm-parent-cancel"),
    path(
        "parent/my-bookings/",
        ParentMyBookingsView.as_view(),
        name="ptm-parent-my-bookings",
    ),
]

