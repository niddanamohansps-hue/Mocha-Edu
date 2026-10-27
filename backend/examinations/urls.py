from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BelowPassingReportView,
    ExamMarkGraceView,
    ExamScheduleViewSet,
    ExaminationSettingsView,
    ExaminationViewSet,
    ExamTypeViewSet,
    GradeBoundaryViewSet,
    RecheckViewSet,
    StudentReportCardView,
    StudentResultsView,
    StudentTranscriptView,
)

router = DefaultRouter()
router.register(r"types", ExamTypeViewSet, basename="exam-type")
router.register(r"examinations", ExaminationViewSet, basename="examination")
router.register(r"schedules", ExamScheduleViewSet, basename="exam-schedule")
router.register(r"grading", GradeBoundaryViewSet, basename="grade-boundary")
router.register(r"rechecks", RecheckViewSet, basename="exam-recheck")

urlpatterns = [
    path(
        "students/<uuid:student_id>/results/", StudentResultsView.as_view(), name="student-exam-results"
    ),
    path(
        "students/<uuid:student_id>/report-card/",
        StudentReportCardView.as_view(),
        name="student-report-card",
    ),
    path(
        "students/<uuid:student_id>/transcript/",
        StudentTranscriptView.as_view(),
        name="student-transcript",
    ),
    path("marks/<uuid:mark_id>/grace/", ExamMarkGraceView.as_view(), name="exam-mark-grace"),
    path("settings/", ExaminationSettingsView.as_view(), name="examination-settings"),
    path("reports/below-passing/", BelowPassingReportView.as_view(), name="below-passing-report"),
    path("", include(router.urls)),
]
