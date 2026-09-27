from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InstructorTimetableView,
    MyTimetableView,
    PeriodViewSet,
    RoomViewSet,
    SectionTimetableView,
    TimetableEntryViewSet,
    TimetableSubstitutionViewSet,
)

router = DefaultRouter()
router.register(r"periods", PeriodViewSet, basename="period")
router.register(r"rooms", RoomViewSet, basename="room")
router.register(r"entries", TimetableEntryViewSet, basename="timetable-entry")
router.register(r"substitutions", TimetableSubstitutionViewSet, basename="timetable-substitution")

urlpatterns = [
    path(
        "sections/<uuid:section_id>/timetable/",
        SectionTimetableView.as_view(),
        name="section-timetable",
    ),
    path(
        # Instructor's PK is a plain integer (unlike every UUID-keyed model
        # in this app) - staff.Instructor never overrides Django's default
        # auto field. Verified directly against staff/models.py.
        "instructors/<int:instructor_id>/timetable/",
        InstructorTimetableView.as_view(),
        name="instructor-timetable",
    ),
    path("my-timetable/", MyTimetableView.as_view(), name="my-timetable"),
    path("", include(router.urls)),
]
