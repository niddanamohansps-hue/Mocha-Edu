from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .allocation_views import AdmitCardsView, DutyRosterView, ExamInvigilationViewSet, ExamSittingViewSet, MyDutiesView
from .views import (
    BelowPassingReportView,
    CoScholasticActivityViewSet,
    CoScholasticGradeViewSet,
    ExamMarkGraceView,
    ExamScheduleComponentViewSet,
    ExamScheduleViewSet,
    ExaminationSettingsView,
    ExaminationViewSet,
    ExamTypeViewSet,
    GradeBoundaryViewSet,
    RecheckViewSet,
    StudentReportCardView,
    StudentResultsView,
    StudentTranscriptView,
    TermWeightageViewSet,
)

router = DefaultRouter()
router.register(r"types", ExamTypeViewSet, basename="exam-type")
router.register(r"examinations", ExaminationViewSet, basename="examination")
router.register(r"schedules", ExamScheduleViewSet, basename="exam-schedule")
router.register(r"components", ExamScheduleComponentViewSet, basename="exam-schedule-component")
router.register(r"term-weightages", TermWeightageViewSet, basename="term-weightage")
router.register(r"co-scholastic/activities", CoScholasticActivityViewSet, basename="coscholastic-activity")
router.register(r"co-scholastic/grades", CoScholasticGradeViewSet, basename="coscholastic-grade")
router.register(r"grading", GradeBoundaryViewSet, basename="grade-boundary")
router.register(r"rechecks", RecheckViewSet, basename="exam-recheck")
# A prefix of its own: "examinations/<anything>/" would be read as an examination id.
router.register(r"exam-sittings", ExamSittingViewSet, basename="exam-sitting")
router.register(r"exam-invigilations", ExamInvigilationViewSet, basename="exam-invigilation")

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
    path("duty-roster/", DutyRosterView.as_view(), name="exam-duty-roster"),
    path("my-duties/", MyDutiesView.as_view(), name="exam-my-duties"),
    path("admit-cards/", AdmitCardsView.as_view(), name="exam-admit-cards"),
    path("reports/below-passing/", BelowPassingReportView.as_view(), name="below-passing-report"),
    path("", include(router.urls)),
]
