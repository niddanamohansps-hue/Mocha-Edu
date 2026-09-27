from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceSessionViewSet,
    AttendanceSettingsView,
    BelowThresholdReportView,
    SectionAttendanceSummaryView,
    SectionRosterView,
    StaffAttendanceBulkView,
    StaffAttendanceHistoryView,
    StudentAttendanceHistoryView,
    TenantAttendanceSummaryView,
)

router = DefaultRouter()
router.register(r"sessions", AttendanceSessionViewSet, basename="attendance-session")

urlpatterns = [
    path(
        "sections/<uuid:section_id>/roster/",
        SectionRosterView.as_view(),
        name="attendance-section-roster",
    ),
    path(
        "sections/<uuid:section_id>/summary/",
        SectionAttendanceSummaryView.as_view(),
        name="attendance-section-summary",
    ),
    path(
        "students/<uuid:student_id>/history/",
        StudentAttendanceHistoryView.as_view(),
        name="attendance-student-history",
    ),
    path(
        "reports/below-threshold/",
        BelowThresholdReportView.as_view(),
        name="attendance-below-threshold",
    ),
    path(
        "reports/tenant-summary/",
        TenantAttendanceSummaryView.as_view(),
        name="attendance-tenant-summary",
    ),
    path("staff-sessions/", StaffAttendanceBulkView.as_view(), name="attendance-staff-sessions"),
    path(
        "staff/<uuid:staff_id>/history/",
        StaffAttendanceHistoryView.as_view(),
        name="attendance-staff-history",
    ),
    path("settings/", AttendanceSettingsView.as_view(), name="attendance-settings"),
    path("", include(router.urls)),
]
