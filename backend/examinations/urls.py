from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BelowPassingReportView,
    ExamScheduleViewSet,
    ExaminationViewSet,
    ExamTypeViewSet,
    GradeBoundaryViewSet,
    StudentReportCardView,
    StudentResultsView,
)

router = DefaultRouter()
router.register(r"types", ExamTypeViewSet, basename="exam-type")
router.register(r"examinations", ExaminationViewSet, basename="examination")
router.register(r"schedules", ExamScheduleViewSet, basename="exam-schedule")
router.register(r"grading", GradeBoundaryViewSet, basename="grade-boundary")

urlpatterns = [
    path(
        "students/<uuid:student_id>/results/", StudentResultsView.as_view(), name="student-exam-results"
    ),
    path(
        "students/<uuid:student_id>/report-card/",
        StudentReportCardView.as_view(),
        name="student-report-card",
    ),
    path("reports/below-passing/", BelowPassingReportView.as_view(), name="below-passing-report"),
    path("", include(router.urls)),
]
