from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from roles.permissions import HasPermission

from .models import FeeHead, FeeStructure, Payment, StudentFee
from .serializers import (
    AssignStudentFeeSerializer,
    CancelStudentFeeSerializer,
    FeeHeadSerializer,
    FeeStructureSerializer,
    PaymentSerializer,
    RecordPaymentSerializer,
    ReversePaymentSerializer,
    StudentFeeSerializer,
    UpdateStudentFeeSerializer,
)
from .services import (
    assign_student_fee,
    cancel_student_fee,
    get_outstanding_balance,
    get_staff_member_for_user,
    record_payment,
    reverse_payment,
    update_student_fee,
    user_can_view_student_finances,
)

NO_METHOD_NAMES_WITH_DELETE = ["get", "post", "patch", "head", "options"]


class FeeHeadViewSet(viewsets.ModelViewSet):
    """
    Reference data (charge categories). No DELETE - a FeeHead referenced by
    months of FeeStructure/StudentFee history must never disappear; use
    is_active=False to retire one instead.
    """

    queryset = FeeHead.objects.all()
    serializer_class = FeeHeadSerializer
    http_method_names = NO_METHOD_NAMES_WITH_DELETE

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            perm = HasPermission("view_fees")
        else:
            perm = HasPermission("manage_fee_structures")
        return [IsAuthenticated(), perm]

    def perform_create(self, serializer):
        instance = serializer.save()
        log_action(
            self.request, action="fee_structure_created", model_name="FeeHead", object_id=instance.id,
            changes={"name": instance.name},
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        log_action(
            self.request, action="fee_structure_updated", model_name="FeeHead", object_id=instance.id,
            changes={"name": instance.name, "is_active": instance.is_active},
        )


class FeeStructureViewSet(viewsets.ModelViewSet):
    """Definition layer. No DELETE, same reasoning as FeeHead - use
    is_active=False instead."""

    queryset = FeeStructure.objects.select_related("fee_head", "level", "section")
    serializer_class = FeeStructureSerializer
    http_method_names = NO_METHOD_NAMES_WITH_DELETE
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["academic_year", "fee_head", "level", "section", "is_active"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            perm = HasPermission("view_fees")
        else:
            perm = HasPermission("manage_fee_structures")
        return [IsAuthenticated(), perm]

    def perform_create(self, serializer):
        instance = serializer.save()
        log_action(
            self.request, action="fee_structure_created", model_name="FeeStructure", object_id=instance.id,
            changes={
                "fee_head": str(instance.fee_head_id), "academic_year": instance.academic_year,
                "amount": str(instance.amount),
            },
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        log_action(
            self.request, action="fee_structure_updated", model_name="FeeStructure", object_id=instance.id,
            changes={"amount": str(instance.amount), "is_active": instance.is_active},
        )


class StudentFeesView(APIView):
    """
    GET /api/fees/students/{student_id}/ - list this student's StudentFee
    rows plus a total-outstanding summary. Mixed audience: the student
    themself (with view_own_fees) or staff (with view_fees) - see
    user_can_view_student_finances for the exact rule. Never trusts the
    URL student_id beyond that check.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from students.models import Student

        student = get_object_or_404(Student.objects.select_related("profile"), id=student_id)

        if not user_can_view_student_finances(request, student):
            return Response(
                {"error": "You do not have permission to view this student's fees."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = StudentFee.objects.filter(student=student).select_related("fee_head")
        academic_year = request.query_params.get("academic_year")
        if academic_year:
            qs = qs.filter(academic_year=academic_year)

        total_outstanding = sum((get_outstanding_balance(sf) for sf in qs if sf.status == "active"), 0)

        return Response(
            {
                "student": str(student.id),
                "total_outstanding": total_outstanding,
                "fees": StudentFeeSerializer(qs, many=True).data,
            }
        )


class AssignStudentFeeView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("manage_fee_structures")]

    def post(self, request, student_id):
        from students.models import Student

        student = get_object_or_404(Student, id=student_id)
        serializer = AssignStudentFeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student_fee = assign_student_fee(
            student=student,
            fee_head=data["fee_head_obj"],
            academic_year=data["academic_year"],
            amount_due=data["amount_due"],
            fee_structure=data.get("fee_structure_obj"),
            due_date=data.get("due_date"),
            discount_amount=data.get("discount_amount") or 0,
            discount_reason=data.get("discount_reason", ""),
        )

        log_action(
            request, action="student_fee_assigned", model_name="StudentFee", object_id=student_fee.id,
            changes={
                "student": str(student.id), "fee_head": str(student_fee.fee_head_id),
                "amount_due": str(student_fee.amount_due),
            },
        )
        if student_fee.discount_amount:
            log_action(
                request, action="discount_applied", model_name="StudentFee", object_id=student_fee.id,
                changes={"discount_amount": str(student_fee.discount_amount), "reason": student_fee.discount_reason},
            )

        return Response(StudentFeeSerializer(student_fee).data, status=status.HTTP_201_CREATED)


class StudentFeeUpdateView(APIView):
    """PATCH only - amount_due/due_date/discount are immutable once any
    payment has been allocated (see can_edit_student_fee)."""

    permission_classes = [IsAuthenticated, HasPermission("manage_fee_structures")]

    def patch(self, request, student_id, fee_id):
        student_fee = get_object_or_404(StudentFee, id=fee_id, student_id=student_id)
        serializer = UpdateStudentFeeSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        student_fee, discount_changed = update_student_fee(student_fee, **serializer.validated_data)

        log_action(
            request, action="fee_structure_updated", model_name="StudentFee", object_id=student_fee.id,
            changes=serializer.validated_data,
        )
        if discount_changed:
            log_action(
                request, action="discount_applied", model_name="StudentFee", object_id=student_fee.id,
                changes={"discount_amount": str(student_fee.discount_amount), "reason": student_fee.discount_reason},
            )

        return Response(StudentFeeSerializer(student_fee).data)


class CancelStudentFeeView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("manage_fee_structures")]

    def post(self, request, student_id, fee_id):
        student_fee = get_object_or_404(StudentFee, id=fee_id, student_id=student_id)
        serializer = CancelStudentFeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student_fee = cancel_student_fee(student_fee, reason=serializer.validated_data["cancellation_reason"])

        log_action(
            request, action="student_fee_cancelled", model_name="StudentFee", object_id=student_fee.id,
            changes={"reason": student_fee.cancellation_reason},
        )

        return Response(StudentFeeSerializer(student_fee).data)


class RecordPaymentView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("collect_payments")]

    def post(self, request):
        from students.models import Student

        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = get_object_or_404(Student, id=data["student"])
        staff_member = get_staff_member_for_user(request.user)

        payment = record_payment(
            student=student,
            amount=data["amount"],
            method=data["method"],
            allocations=[
                {"student_fee_id": a["student_fee"], "amount": a["amount"]} for a in data["allocations"]
            ],
            recorded_by=staff_member,
            reference_note=data.get("reference_note", ""),
        )

        log_action(
            request, action="payment_recorded", model_name="Payment", object_id=payment.id,
            changes={
                "student": str(student.id), "amount": str(payment.amount), "method": payment.method,
                "receipt_number": payment.receipt_number,
            },
        )

        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class ReversePaymentView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("collect_payments")]

    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        serializer = ReversePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        staff_member = get_staff_member_for_user(request.user)
        reversal = reverse_payment(payment=payment, recorded_by=staff_member, reason=serializer.validated_data.get("reason", ""))

        log_action(
            request, action="payment_reversed", model_name="Payment", object_id=reversal.id,
            changes={"reverses": str(payment.id), "amount": str(reversal.amount)},
        )

        return Response(PaymentSerializer(reversal).data, status=status.HTTP_201_CREATED)


class StudentPaymentsView(APIView):
    """GET /api/fees/students/{student_id}/payments/ - payment history.
    Same mixed self/staff authorization as StudentFeesView."""

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from students.models import Student

        student = get_object_or_404(Student.objects.select_related("profile"), id=student_id)

        if not user_can_view_student_finances(request, student):
            return Response(
                {"error": "You do not have permission to view this student's payments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = Payment.objects.filter(student=student).select_related("student__profile").prefetch_related(
            "allocations__student_fee__fee_head"
        )
        return Response(PaymentSerializer(qs, many=True).data)


class PaymentReceiptView(APIView):
    """GET /api/fees/payments/{id}/receipt/ - a rendered view of the
    Payment + its allocations. No stored Receipt model - mirrors
    examinations' StudentReportCardView "aggregation only" precedent."""

    permission_classes = [IsAuthenticated]

    def get(self, request, payment_id):
        payment = get_object_or_404(
            Payment.objects.select_related("student__profile").prefetch_related(
                "allocations__student_fee__fee_head"
            ),
            id=payment_id,
        )

        if not user_can_view_student_finances(request, payment.student):
            return Response(
                {"error": "You do not have permission to view this receipt."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(PaymentSerializer(payment).data)


class OutstandingReportView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_financial_reports")]

    def get(self, request):
        section_id = request.query_params.get("section")
        academic_year = request.query_params.get("academic_year")

        qs = StudentFee.objects.filter(status="active").select_related("student__profile", "fee_head")
        if academic_year:
            qs = qs.filter(academic_year=academic_year)
        if section_id:
            qs = qs.filter(student__enrollments__section_id=section_id, student__enrollments__is_current=True)

        rows = []
        for student_fee in qs:
            outstanding = get_outstanding_balance(student_fee)
            if outstanding <= 0:
                continue
            rows.append(
                {
                    "student": str(student_fee.student_id),
                    "full_name": f"{student_fee.student.profile.first_name} {student_fee.student.profile.last_name}",
                    "enrollment_id": student_fee.student.enrollment_id,
                    "fee_head": student_fee.fee_head.name,
                    "academic_year": student_fee.academic_year,
                    "due_date": student_fee.due_date,
                    "outstanding": outstanding,
                }
            )

        return Response({"count": len(rows), "results": rows})
