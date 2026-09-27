from django.urls import path

from .views import (
    ChildAttendanceView,
    ChildFeesView,
    ChildReportCardView,
    ChildResultsView,
    ChildTimetableView,
    ChildUpcomingExamsView,
    LinkedChildrenView,
    ParentMeView,
)

urlpatterns = [
    path("me/", ParentMeView.as_view(), name="parent-portal-me"),
    path("children/", LinkedChildrenView.as_view(), name="parent-portal-children"),
    path(
        "children/<uuid:student_id>/attendance/",
        ChildAttendanceView.as_view(),
        name="parent-portal-child-attendance",
    ),
    path(
        "children/<uuid:student_id>/timetable/",
        ChildTimetableView.as_view(),
        name="parent-portal-child-timetable",
    ),
    path(
        "children/<uuid:student_id>/results/",
        ChildResultsView.as_view(),
        name="parent-portal-child-results",
    ),
    path(
        "children/<uuid:student_id>/upcoming-exams/",
        ChildUpcomingExamsView.as_view(),
        name="parent-portal-child-upcoming-exams",
    ),
    path(
        "children/<uuid:student_id>/report-card/",
        ChildReportCardView.as_view(),
        name="parent-portal-child-report-card",
    ),
    path(
        "children/<uuid:student_id>/fees/",
        ChildFeesView.as_view(),
        name="parent-portal-child-fees",
    ),
]
