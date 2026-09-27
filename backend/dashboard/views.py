"""
Read-only cross-module aggregation. No models of its own - this app is a
pure read layer over students/staff/academics/attendance/fees/notifications,
exactly mirroring parent_portal's "query other apps' models/services
directly, never their permission-gated views" convention. Every value is
computed via a small, fixed number of database-level Count()/Sum() queries
- never by loading every row into Python and counting there, and never via
an internal HTTP call to another app's endpoint.
"""

from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from roles.permissions import HasPermission

STUDENT_STATUSES = ["active", "inactive", "graduated", "withdrawn", "transferred"]


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_dashboard")]

    def get(self, request):
        return Response(
            {
                "students": self._student_counts(),
                "staff": self._staff_counts(),
                "academics": self._academic_counts(),
                "attendance": self._today_attendance(),
                "fees": self._fees_outstanding(),
                "promotion": self._recent_promotion_activity(),
                "notifications": self._unread_notifications(request),
            }
        )

    def _student_counts(self):
        """One query (values/annotate, matching the exact idiom already
        used by attendance.views.TenantAttendanceSummaryView) - never a
        per-status .count() call, never loading every Student row."""
        from students.models import Student

        by_status = dict(Student.objects.values_list("status").annotate(count=Count("id")))
        counts = {status: by_status.get(status, 0) for status in STUDENT_STATUSES}
        counts["total"] = sum(counts.values())
        return counts

    def _staff_counts(self):
        """Uses StaffMember.is_active - the exact "active" convention
        already defined on the model itself, not an invented one."""
        from staff.models import StaffMember

        return {"active": StaffMember.objects.filter(is_active=True).count()}

    def _academic_counts(self):
        """Program has an is_active field (used here); AcademicLevel and
        Section do not, so they are plain counts - no invented filter."""
        from academics.models import AcademicLevel, Program, Section

        return {
            "programs": Program.objects.filter(is_active=True).count(),
            "levels": AcademicLevel.objects.count(),
            "sections": Section.objects.count(),
        }

    def _today_attendance(self):
        """
        Mirrors attendance.views.TenantAttendanceSummaryView's exact query
        shape and calculation for "today" - same StudentAttendance filter,
        same calculate_attendance_percentage() call, same
        AttendanceSettings.get_solo(). Reuses the Python service function
        directly; never makes an HTTP request to that view.
        """
        from attendance.models import AttendanceSettings, StudentAttendance
        from attendance.services import calculate_attendance_percentage

        target_date = timezone.localdate().isoformat()
        counts = dict(
            StudentAttendance.objects.filter(session__date=target_date)
            .values_list("status")
            .annotate(total=Count("id"))
        )
        percentage = calculate_attendance_percentage(counts, AttendanceSettings.get_solo())
        return {"today_percentage": percentage}

    def _fees_outstanding(self):
        """
        Mathematically identical to summing fees.services.
        get_outstanding_balance(student_fee) - amount_due - discount_amount
        - sum(allocations) - over every active StudentFee (the same
        "active" filter fees.views.OutstandingReportView already uses).
        get_outstanding_balance operates per-row (one query per StudentFee
        via get_total_allocated's aggregate), which is fine for that
        report page but would be an N+1 risk here at 10,000-student scale
        on every dashboard load. This computes the same formula as two
        tenant-wide aggregate queries instead - not a redefinition of
        "outstanding," just an aggregate-safe equivalent of the exact same
        fields. fees/models.py and fees/services.py are not modified.
        """
        from fees.models import PaymentAllocation, StudentFee

        totals = StudentFee.objects.filter(status="active").aggregate(
            total_due=Sum("amount_due"), total_discount=Sum("discount_amount")
        )
        total_due = totals["total_due"] or Decimal("0")
        total_discount = totals["total_discount"] or Decimal("0")

        total_allocated = (
            PaymentAllocation.objects.filter(student_fee__status="active").aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0")
        )

        outstanding = total_due - total_discount - total_allocated
        return {"outstanding": str(outstanding)}

    def _recent_promotion_activity(self):
        """Reuses PromotionRecordSerializer as-is - no duplicated field
        mapping. Limited to 10 rows, never the whole table."""
        from students.models import PromotionRecord
        from students.serializers import PromotionRecordSerializer

        recent = PromotionRecord.objects.select_related(
            "student__profile", "source_level", "target_level", "source_section", "target_section"
        ).order_by("-created_at")[:10]
        return {"recent": PromotionRecordSerializer(recent, many=True).data}

    def _unread_notifications(self, request):
        """Scoped to the authenticated dashboard user only - the exact
        same query as notifications.views.UnreadCountView, never a
        tenant-wide count."""
        from notifications.models import Notification

        count = Notification.objects.filter(
            recipient_user_id=request.user.id, is_read=False
        ).count()
        return {"unread": count}
