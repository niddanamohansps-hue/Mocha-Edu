from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .allocation_views import (
    AdmitCardsView,
    AnalyticsCompareView,
    AnalyticsView,
    DutyRosterView,
    ExamInvigilationViewSet,
    ExamSittingViewSet,
    MalpracticeViewSet,
    MarksProgressView,
    MyAdmitCardView,
    MyDutiesView,
    ModerationApplyView,
    ModerationPreviewView,
    MyExamsView,
    RankListView,
    WeakStudentsView,
)
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
router.register(r"malpractice", MalpracticeViewSet, basename="exam-malpractice")

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
    path("marks-progress/", MarksProgressView.as_view(), name="exam-marks-progress"),
    path("rank-list/", RankListView.as_view(), name="exam-rank-list"),
    path("moderation/<uuid:schedule_id>/preview/", ModerationPreviewView.as_view(), name="exam-moderation-preview"),
    path("moderation/<uuid:schedule_id>/apply/", ModerationApplyView.as_view(), name="exam-moderation-apply"),
    path("analytics/", AnalyticsView.as_view(), name="exam-analytics"),
    path("analytics/compare/", AnalyticsCompareView.as_view(), name="exam-analytics-compare"),
    path("weak-students/", WeakStudentsView.as_view(), name="exam-weak-students"),
    path("my-exams/", MyExamsView.as_view(), name="exam-my-exams"),
    path("my-admit-card/", MyAdmitCardView.as_view(), name="exam-my-admit-card"),
    path("reports/below-passing/", BelowPassingReportView.as_view(), name="below-passing-report"),
    path("", include(router.urls)),
]
