from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProgramViewSet,
    AcademicLevelViewSet,
    SectionViewSet,
    SubjectViewSet,
    SubjectAssignmentViewSet,
    AcademicYearViewSet,
    CalendarEventViewSet,
)

router = DefaultRouter()
router.register(r"programs", ProgramViewSet)
router.register(r"levels", AcademicLevelViewSet)
router.register(r"sections", SectionViewSet)
router.register(r"subjects", SubjectViewSet)
router.register(r"assignments", SubjectAssignmentViewSet, basename="assignment")
router.register(r"academic-years", AcademicYearViewSet, basename="academic-year")
router.register(r"calendar-events", CalendarEventViewSet, basename="calendar-event")

urlpatterns = [
    path("", include(router.urls)),
]
