"""
EduSekai Staff Leave Management URL Routing (Phase 5)
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .leave_views import (
    ApproverInboxView,
    AssignLeaveSubstitutionView,
    LeaveApplicationAffectedPeriodsView,
    LeaveApplicationApproveView,
    LeaveApplicationCancelView,
    LeaveApplicationCreateView,
    LeaveApplicationDetailView,
    LeaveApplicationDocumentDownloadView,
    LeaveApplicationMyListView,
    LeaveApplicationRejectView,
    LeaveTypeViewSet,
    StaffLeaveBalanceAdjustView,
    StaffLeaveBalanceListView,
    StaffLeaveBalanceMyView,
)

router = DefaultRouter()
router.register(r"types", LeaveTypeViewSet, basename="leave-type")

urlpatterns = [
    # Balances
    path("balances/my/", StaffLeaveBalanceMyView.as_view(), name="staff-leave-balance-my"),
    path("balances/", StaffLeaveBalanceListView.as_view(), name="staff-leave-balance-list"),
    path("balances/adjust/", StaffLeaveBalanceAdjustView.as_view(), name="staff-leave-balance-adjust"),

    # Applications
    path("applications/my/", LeaveApplicationMyListView.as_view(), name="staff-leave-application-my"),
    path("applications/", LeaveApplicationCreateView.as_view(), name="staff-leave-application-create"),
    path("applications/<uuid:pk>/", LeaveApplicationDetailView.as_view(), name="staff-leave-application-detail"),
    path("applications/<uuid:pk>/cancel/", LeaveApplicationCancelView.as_view(), name="staff-leave-application-cancel"),
    path("applications/<uuid:pk>/approve/", LeaveApplicationApproveView.as_view(), name="staff-leave-application-approve"),
    path("applications/<uuid:pk>/reject/", LeaveApplicationRejectView.as_view(), name="staff-leave-application-reject"),
    path("applications/<uuid:pk>/document/", LeaveApplicationDocumentDownloadView.as_view(), name="staff-leave-application-document"),
    path("applications/<uuid:pk>/affected-periods/", LeaveApplicationAffectedPeriodsView.as_view(), name="staff-leave-application-affected-periods"),

    # Approver Actions
    path("approvals/inbox/", ApproverInboxView.as_view(), name="staff-leave-approver-inbox"),

    # Timetable Substitute Assignment
    path("substitutions/assign/", AssignLeaveSubstitutionView.as_view(), name="staff-leave-substitutions-assign"),

    # Leave Types ViewSet Router
    path("", include(router.urls)),
]

