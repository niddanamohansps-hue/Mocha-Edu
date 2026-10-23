"""A staff member's own payslips, plus the PDF, the month summary and the export for payroll managers.

"My payslips" needs no payroll permission: seeing your own pay follows from who you are. It shows only runs
that have been approved or paid (never a draft that is still being worked on, never a cancelled run), and
only the signed-in user's own staff record.
"""
import csv
import io

from django.db import connection
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from .models import PayrollRun, Payslip, PayslipLine
from .pdf import render_payslip_pdf
from .run_serializers import MONTH_NAMES, PayslipDetailSerializer, PayslipSerializer, money

VISIBLE_TO_STAFF = (PayrollRun.Status.APPROVED, PayrollRun.Status.PAID)


def _staff_for(user):
    from attendance.services import get_staff_member_for_user

    return get_staff_member_for_user(user)


def school_name():
    tenant = getattr(connection, "tenant", None)
    return getattr(tenant, "name", "") or "School"


def pdf_response(payslip, filename):
    pdf = render_payslip_pdf(payslip, list(payslip.lines.all()), school_name=school_name())
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    return response


def payslip_filename(payslip):
    return f"payslip-{payslip.employee_id}-{payslip.run.year}-{payslip.run.month:02d}.pdf"


class MyPayslipViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    pagination_class = StandardResultsPagination
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)
        self.staff = _staff_for(request.user)
        if self.staff is None:
            raise PermissionDenied("Only staff members have payslips.")

    def get_serializer_class(self):
        return PayslipDetailSerializer if self.action == "retrieve" else PayslipSerializer

    def get_queryset(self):
        return (
            Payslip.objects.filter(staff=self.staff, run__status__in=VISIBLE_TO_STAFF)
            .select_related("run").prefetch_related("lines")
            .order_by("-run__year", "-run__month")
        )

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        payslip = self.get_object()
        return pdf_response(payslip, payslip_filename(payslip))


class PayrollReportMixin:
    """Actions added to the run viewset: the PDF of any payslip, the month summary and the CSV export."""

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        run = self.get_object()
        payslips = run.payslips.all()
        totals = payslips.aggregate(
            gross=Sum("gross_amount"), deductions=Sum("deductions_amount"), net=Sum("net_amount"), people=Count("id"),
        )
        by_department = [
            {"department": row["department"] or "(none)", "people": row["people"], "gross": money(row["gross"]),
             "deductions": money(row["deductions"]), "net": money(row["net"])}
            for row in payslips.values("department").annotate(
                people=Count("id"), gross=Sum("gross_amount"), deductions=Sum("deductions_amount"), net=Sum("net_amount")
            ).order_by("department")
        ]
        by_component = [
            {"code": row["code"], "name": row["name"], "kind": row["kind"], "people": row["people"], "total": money(row["total"])}
            for row in PayslipLine.objects.filter(payslip__run=run).values("code", "name", "kind")
            .annotate(people=Count("payslip", distinct=True), total=Sum("amount")).order_by("kind", "name")
        ]
        return Response({
            "run": str(run.pk), "month_label": f"{MONTH_NAMES[run.month]} {run.year}", "status": run.status,
            "people": totals["people"], "gross": money(totals["gross"]), "deductions": money(totals["deductions"]),
            "net": money(totals["net"]), "unpaid_days_total": f"{(payslips.aggregate(t=Sum('unpaid_days'))['t'] or 0):f}",
            "negative_net": payslips.filter(net_amount__lt=0).count(),
            "unmarked_attendance": payslips.filter(unmarked_days__gt=0).count(),
            "by_department": by_department, "by_component": by_component,
        })

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        """A CSV for the bank or the accountant: one row per person with the net amount to pay."""
        run = self.get_object()
        if run.status not in VISIBLE_TO_STAFF:
            raise PermissionDenied("Only an approved or paid run can be exported.")
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["Employee ID", "Name", "Designation", "Department", "Gross", "Deductions", "Net pay"])
        for slip in run.payslips.order_by("staff_name", "employee_id"):
            writer.writerow([_safe(v) for v in (
                slip.employee_id, slip.staff_name, slip.designation, slip.department,
                f"{slip.gross_amount:.2f}", f"{slip.deductions_amount:.2f}", f"{slip.net_amount:.2f}",
            )])
        log_action(request, action="payroll_run_exported", model_name="PayrollRun", object_id=run.pk,
                   changes={"month": f"{run.year}-{run.month:02d}", "rows": run.payslips.count()})
        response = HttpResponse(out.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="payroll-{run.year}-{run.month:02d}.csv"'
        response["Cache-Control"] = "private, no-store"
        return response


def _safe(value):
    """A spreadsheet runs a cell that starts with = + - @ (or a tab/return) as a formula. Names and
    designations are typed by people, so such a cell is made harmless by a leading apostrophe."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") and not _is_plain_number(text) else text


def _is_plain_number(text):
    try:
        float(text)
        return True
    except ValueError:
        return False
