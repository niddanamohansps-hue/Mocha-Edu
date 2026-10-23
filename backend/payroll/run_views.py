from django.db import connection
from django.db.models import Count, Q, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from . import services
from .models import PayrollAdjustment, PayrollRun, Payslip
from .my_views import PayrollReportMixin, payslip_filename, pdf_response
from .run_serializers import (
    CreateAdjustmentSerializer,
    CreateRunSerializer,
    PayrollAdjustmentSerializer,
    PayrollRunSerializer,
    PayslipDetailSerializer,
    PayslipSerializer,
    ReasonSerializer,
    RecordPaymentSerializer,
)

READ = "view_payroll"
RUN = "run_payroll"
APPROVE = "approve_payroll"
PAY = "record_payroll_payment"


class RunBase(viewsets.GenericViewSet):
    pagination_class = StandardResultsPagination

    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)

    def _need(self, request, permission):
        if not HasPermission(permission).has_permission(request, self):
            raise PermissionDenied()


class PayrollRunViewSet(PayrollReportMixin, RunBase, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Runs are created and moved through their states by actions; they are never edited or deleted."""

    serializer_class = PayrollRunSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "year", "month"]

    PERMISSIONS = {"create": RUN, "calculate": RUN, "cancel": RUN, "approve": APPROVE, "pay": PAY}

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission(self.PERMISSIONS.get(self.action, READ))]

    def get_queryset(self):
        return PayrollRun.objects.annotate(
            payslip_count=Count("payslips"), gross_total=Sum("payslips__gross_amount"),
            deductions_total=Sum("payslips__deductions_amount"), net_total=Sum("payslips__net_amount"),
        ).order_by("-year", "-month", "-created_at")

    def _fresh(self, run):
        return PayrollRunSerializer(self.get_queryset().get(pk=run.pk)).data

    def _audit(self, request, run, name, **changes):
        log_action(request, action=name, model_name="PayrollRun", object_id=run.pk,
                   changes={"month": f"{run.year}-{run.month:02d}", **changes})

    def create(self, request):
        serializer = CreateRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = services.create_run(user_id=request.user.id, **serializer.validated_data)
        self._audit(request, run, "payroll_run_created")
        return Response(self._fresh(run), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        run = services.calculate_run(self.get_object(), user_id=request.user.id)
        self._audit(request, run, "payroll_run_calculated", payslips=run.calculation_notes.get("payslips"))
        return Response(self._fresh(run))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        run = services.approve_run(self.get_object(), user_id=request.user.id)
        self._audit(request, run, "payroll_run_approved")
        return Response(self._fresh(run))

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = services.record_payment(self.get_object(), user_id=request.user.id, **serializer.validated_data)
        self._audit(request, run, "payroll_run_paid", method=run.payment_method, paid_on=run.paid_on.isoformat())
        return Response(self._fresh(run))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = self.get_object()
        if run.is_locked:
            self._need(request, APPROVE)  # undoing an approved run is as serious as approving it
        run = services.cancel_run(run, reason=serializer.validated_data["reason"], user_id=request.user.id)
        self._audit(request, run, "payroll_run_cancelled", reason=run.cancellation_reason)
        return Response(self._fresh(run))

    @action(detail=True, methods=["get"])
    def payslips(self, request, pk=None):
        rows = self.get_object().payslips.select_related("run")
        search = request.query_params.get("search", "").strip()
        if search:
            rows = rows.filter(Q(staff_name__icontains=search) | Q(employee_id__icontains=search))
        if request.query_params.get("problems", "").lower() in ("1", "true", "yes"):
            rows = rows.filter(Q(net_amount__lt=0) | Q(unmarked_days__gt=0))
        page = self.paginate_queryset(rows.order_by("staff_name", "employee_id"))
        return self.get_paginated_response(PayslipSerializer(page, many=True).data)

    @action(detail=True, methods=["get"])
    def adjustments(self, request, pk=None):
        rows = self.get_object().adjustments.select_related("staff__profile")
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(PayrollAdjustmentSerializer(page, many=True).data)


class PayslipViewSet(RunBase, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Every payslip, for payroll managers (staff read their own through ``my-payslips``)."""

    queryset = Payslip.objects.select_related("run").prefetch_related("lines")
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["staff", "run"]

    def get_serializer_class(self):
        return PayslipDetailSerializer if self.action == "retrieve" else PayslipSerializer

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission(READ)]

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        payslip = self.get_object()
        log_action(request, action="payslip_pdf_viewed", model_name="Payslip", object_id=payslip.pk)
        return pdf_response(payslip, payslip_filename(payslip))


class PayrollAdjustmentViewSet(RunBase):
    serializer_class = PayrollAdjustmentSerializer
    queryset = PayrollAdjustment.objects.select_related("staff__profile", "run")

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission(RUN)]

    def create(self, request):
        serializer = CreateAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        run = data.pop("run")
        adjustment = services.add_adjustment(run, user_id=request.user.id, **data)
        log_action(request, action="payroll_adjustment_added", model_name="PayrollAdjustment", object_id=adjustment.pk,
                   changes={"run": str(run.pk), "staff": str(adjustment.staff_id), "kind": adjustment.kind,
                            "amount": str(adjustment.amount)})
        return Response(PayrollAdjustmentSerializer(adjustment).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        adjustment = self.get_object()
        services.remove_adjustment(adjustment, user_id=request.user.id)
        log_action(request, action="payroll_adjustment_removed", model_name="PayrollAdjustment", object_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
