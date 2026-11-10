import base64
from decimal import Decimal
import json
import logging
import uuid

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from core.query_params import model_param
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from .gateways import MAX_CALLBACK_CHARS, PaymentConfigurationError, PaymentGatewayError
from .models import FeeHead, FeeStructure, OnlinePaymentOrder, Payment, StudentFee
from .serializers import (
    AssignStudentFeeSerializer,
    CancelStudentFeeSerializer,
    FeeHeadSerializer,
    FeeStructureSerializer,
    OnlinePaymentOrderInitiateSerializer,
    OnlinePaymentOrderSerializer,
    OnlinePaymentVerifySerializer,
    PaymentSerializer,
    PublicOnlinePaymentOrderSerializer,
    RecordPaymentSerializer,
    ReversePaymentSerializer,
    StudentFeeSerializer,
    UpdateStudentFeeSerializer,
)
from .services import (
    PaymentEvidenceRejected,
    annotate_with_allocation_total,
    annotate_with_outstanding_balance,
    assign_student_fee,
    cancel_student_fee,
    get_child_for_parent,
    get_linked_children,
    get_outstanding_balance,
    get_parent_for_user,
    get_staff_member_for_user,
    get_student_for_user,
    initiate_online_payment_order,
    reconcile_online_payment_order,
    record_payment,
    reverse_payment,
    settle_online_payment_order,
    update_student_fee,
    user_can_initiate_student_online_payment,
    user_can_view_online_order,
    user_can_view_student_finances,
)

logger = logging.getLogger(__name__)

# The only reason an unauthenticated caller is ever given for a reconciliation_required result.
# The real reason (fee names, allocation details, balances) stays on the order for staff.
PUBLIC_RECONCILIATION_MESSAGE = "Payment requires additional verification."

# Shown when online payments cannot be started (details go to the log, never to the caller).
PAYMENT_UNAVAILABLE_MESSAGE = "Online payment is currently unavailable. Please try again later or contact the school."

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
        qs = annotate_with_allocation_total(qs)

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
    """
    Server-paginated (StandardResultsPagination, matching every other list
    endpoint in this project). "Outstanding" (amount_due - discount_amount
    - net allocations > 0) is filtered at the database level via
    annotate_with_outstanding_balance() BEFORE pagination, so page
    boundaries are over the outstanding dataset itself, not over the raw
    StudentFee set with Python-side filtering applied afterward - the
    latter would silently return fewer than page_size rows (or an empty
    later page) whenever some fees on a given raw page turn out not to be
    outstanding.

    The response also carries `total_outstanding_amount` - the sum of
    EVERY matching outstanding fee (not just the current page), computed
    by one extra database aggregate over the exact same filtered queryset
    used for `count`/`results` (Phase 9C-F). `results` still contains only
    the current page.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_financial_reports")]
    pagination_class = StandardResultsPagination

    def get(self, request):
        from academics.models import Section

        section_id = model_param(request, "section", Section)
        academic_year = request.query_params.get("academic_year")

        qs = StudentFee.objects.filter(status="active").select_related("student__profile", "fee_head")
        if academic_year:
            qs = qs.filter(academic_year=academic_year)
        if section_id:
            # A subquery (not a join) on purpose: annotate_with_outstanding_balance()
            # below adds its own to-many join (allocations), and combining that
            # with a second to-many join here (student__enrollments) in the same
            # queryset would let Django's JOIN cross-multiply rows before the
            # Sum is grouped, silently inflating every allocation total for a
            # student with more than one matching enrollment row. A student_id
            # membership subquery filters the same set of StudentFee rows
            # without introducing that second join.
            from students.models import StudentLevel

            current_student_ids = StudentLevel.objects.filter(
                section_id=section_id, is_current=True
            ).values_list("student_id", flat=True)
            qs = qs.filter(student_id__in=current_student_ids)

        # Outstanding-balance filtering happens in SQL (HAVING, verified via
        # .query during Phase 9C) BEFORE pagination - only the matching rows
        # are counted/paginated, never the full active-StudentFee set.
        qs = annotate_with_outstanding_balance(qs).filter(_outstanding__gt=0)

        # Full-report total: ONE extra SQL aggregate over the SAME filtered
        # queryset used for count/pagination below (same filters, same
        # annotation, same HAVING clause - see Phase 9C-F report for the
        # generated SQL: Django wraps this already-grouped queryset as a
        # subquery and sums its _outstanding column). This must happen
        # before .order_by()/pagination slice it, and it reads from the
        # exact same `qs` so it can never drift from what `count`/`results`
        # describe - it is not a second, independently-filtered query.
        total_outstanding_amount = qs.aggregate(total=Sum("_outstanding"))["total"] or Decimal("0")

        # annotate() with an aggregate-derived expression drops the model's
        # default Meta.ordering (["-created_at"]) as a side effect - verified
        # empirically in Phase 9C. Re-applying it here restores the exact
        # ordering this report already had; it is not a new choice.
        qs = qs.order_by("-created_at")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        page_rows = page if page is not None else qs

        rows = []
        for student_fee in page_rows:
            outstanding = get_outstanding_balance(student_fee)
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

        if page is not None:
            response = paginator.get_paginated_response(rows)
            response.data["total_outstanding_amount"] = total_outstanding_amount
            return response

        return Response({"count": len(rows), "total_outstanding_amount": total_outstanding_amount, "results": rows})


class DuesByStudentView(APIView):
    """One row per student who owes fees, aged by their oldest unpaid fee, with the guardian's phone number."""

    permission_classes = [IsAuthenticated, HasPermission("view_financial_reports")]

    def get(self, request):
        import uuid

        from .dues import BANDS, PROMISES, SORTS, dues_by_student

        params = request.query_params
        band = params.get("band") or None
        promise = params.get("promise") or None
        if promise is not None and promise not in PROMISES:
            return Response({"promise": [f"Choose one of: {', '.join(PROMISES)}."]}, status=status.HTTP_400_BAD_REQUEST)
        sort = params.get("sort") or "amount"
        if band is not None and band not in BANDS:
            return Response({"band": [f"Choose one of: {', '.join(BANDS)}."]}, status=status.HTTP_400_BAD_REQUEST)
        if sort not in SORTS:
            return Response({"sort": [f"Choose one of: {', '.join(SORTS)}."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            level = uuid.UUID(params["level"]) if params.get("level") else None
            section = uuid.UUID(params["section"]) if params.get("section") else None
            page = max(int(params.get("page", 1)), 1)
            page_size = min(max(int(params.get("page_size", 25)), 1), 100)
        except (ValueError, TypeError):
            return Response({"error": "That filter is not valid."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(dues_by_student(
            academic_year=params.get("academic_year") or None, level=level, section=section, band=band,
            search=params.get("search", ""), sort=sort, page=page, page_size=page_size, promise=promise,
        ))


class CollectionSummaryView(APIView):
    """Billed, collected and outstanding by month and by class for one academic year."""

    permission_classes = [IsAuthenticated, HasPermission("view_financial_reports")]

    def get(self, request):
        import re

        from .collection import collection_summary

        year = (request.query_params.get("academic_year") or "").strip()
        if not year:
            return Response({"academic_year": ["Choose the academic year."]}, status=status.HTTP_400_BAD_REQUEST)
        month = (request.query_params.get("month") or "").strip() or None
        if month is not None and month != "undated" and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            return Response({"month": ["Use the form 2026-04."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(collection_summary(year, month))


class FollowUpDeskView(APIView):
    """Broken promises, promises due today, and overdue families nobody has called in two weeks."""

    permission_classes = [IsAuthenticated, HasPermission("view_financial_reports")]

    def get(self, request):
        from .followups import desk

        return Response(desk())


class StudentCallsView(APIView):
    """The calls made about one student's unpaid fees. Reading needs view_financial_reports; writing a call needs
    collect_payments, the same right as taking the money."""

    def get_permissions(self):
        code = "view_financial_reports" if self.request.method == "GET" else "collect_payments"
        return [IsAuthenticated(), HasPermission(code)]

    def get(self, request, student_id):
        from students.models import Student

        from .followups import history

        get_object_or_404(Student, pk=student_id)
        return Response(history(student_id))

    def post(self, request, student_id):
        from django.utils.dateparse import parse_date

        from students.models import Student

        from .followups import history, record_call

        student = get_object_or_404(Student, pk=student_id)
        raw = request.data.get("promise_date")
        promise_date = None
        if raw:
            promise_date = parse_date(str(raw))
            if promise_date is None:
                return Response({"promise_date": ["Enter a valid date."]}, status=status.HTTP_400_BAD_REQUEST)
        record_call(
            student, outcome=request.data.get("outcome"), note=request.data.get("note", ""),
            promise_amount=request.data.get("promise_amount"), promise_date=promise_date, user=request.user, request=request,
        )
        return Response(history(student_id), status=status.HTTP_201_CREATED)


class OnlinePaymentInitiateView(APIView):
    """
    POST /api/fees/online/initiate/
    Initiates an online payment order for a student.
    Authorized for:
    - Staff/Owner with 'collect_payments'
    - Student paying for themselves with 'pay_own_fees'
    - Parent paying for their linked child with 'pay_child_fees'
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from students.models import Student

        serializer = OnlinePaymentOrderInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = get_object_or_404(Student.objects.select_related("profile"), id=data["student"])

        if not user_can_initiate_student_online_payment(request, student):
            return Response(
                {"error": "You do not have permission to initiate fee payments for this student."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            order, gateway_payload = initiate_online_payment_order(
                student=student,
                amount=data["amount"],
                allocations=[
                    {"student_fee_id": a["student_fee"], "amount": a["amount"]}
                    for a in data["allocations"]
                ],
                gateway=data.get("gateway", "esewa"),
                created_by=request.user,
                ttl_minutes=data.get("ttl_minutes", 60),
                callback_kind="fees",  # return/failure URLs from the client are ignored
            )
        except (PaymentConfigurationError, PaymentGatewayError) as exc:
            logger.error("Online payment could not be initiated: %s", exc)
            return Response({"error": PAYMENT_UNAVAILABLE_MESSAGE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        log_action(
            request,
            action="online_payment_initiated",
            model_name="OnlinePaymentOrder",
            object_id=order.id,
            changes={
                "student": str(student.id),
                "amount": str(order.amount),
                "gateway": order.gateway,
                "gateway_order_id": order.gateway_order_id,
            },
        )

        payload_dict = {
            "gateway": gateway_payload.gateway,
            "gateway_url": gateway_payload.gateway_url,
            "method": gateway_payload.method,
            "form_parameters": gateway_payload.form_parameters,
            "order_id": gateway_payload.order_id,
            "gateway_order_id": gateway_payload.gateway_order_id,
        }

        return Response(
            {
                "order": OnlinePaymentOrderSerializer(order).data,
                "gateway_payload": payload_dict,
            },
            status=status.HTTP_201_CREATED,
        )


class OnlinePaymentVerifyView(APIView):
    """
    POST/GET /api/fees/online/verify/
    Verifies the gateway callback or redirect payload and settles the payment order.
    Idempotent: repeated calls for already settled or reconciled orders return existing status safely.
    Security: HMAC signature check against secret key verifies payload integrity before settlement.
    Anything that cannot be verified changes nothing and gets one generic 400.
    """
    permission_classes = [AllowAny]
    # Public entry point (the callback subclass inherits this): rate-limited per client address.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "online_payment_verify"

    @staticmethod
    def _rejected():
        # One generic answer for every kind of unverifiable request: it must not reveal which
        # check failed, and it says nothing about whether the payment itself succeeded.
        return Response({"error": PaymentEvidenceRejected.GENERIC_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

    def _process_verify(self, request, payload_data):
        if not isinstance(payload_data, dict):
            return self._rejected()
        encoded_data = payload_data.get("data") or payload_data.get("encoded_data")
        if isinstance(encoded_data, str) and len(encoded_data) > MAX_CALLBACK_CHARS:
            return self._rejected()
        order_id = payload_data.get("order_id")

        # If order_id not explicitly supplied, extract from payload if base64 encoded
        if not order_id and encoded_data:
            try:
                padded = encoded_data + "=" * ((4 - len(encoded_data) % 4) % 4)
                decoded_bytes = base64.b64decode(padded)
                decoded_json = json.loads(decoded_bytes.decode("utf-8"))
                order_id = decoded_json.get("transaction_uuid")
            except Exception:
                pass
        elif not order_id and isinstance(payload_data, dict):
            order_id = payload_data.get("transaction_uuid")

        if not order_id:
            return self._rejected()

        recorded_by = None
        if request.user and request.user.is_authenticated:
            recorded_by = get_staff_member_for_user(request.user)

        try:
            result = settle_online_payment_order(
                order_id_or_gateway_order_id=order_id,
                raw_callback_payload=payload_data,
                recorded_by=recorded_by,
            )
        except serializers.ValidationError:
            return self._rejected()
        except Exception:
            logger.exception("Unexpected error while verifying an online payment callback.")
            return self._rejected()

        order = result.get("order")
        if request.user and request.user.is_authenticated and order:
            log_action(
                request,
                action="online_payment_settled",
                model_name="OnlinePaymentOrder",
                object_id=order.id,
                changes={"status": result.get("status")},
            )

        # Unauthenticated callers get only what the payment-return page needs.
        response_data = {
            "status": result.get("status"),
            "order": PublicOnlinePaymentOrderSerializer(order).data if order else None,
            "receipt_number": result.get("receipt_number", ""),
            "reason": PUBLIC_RECONCILIATION_MESSAGE if result.get("status") == "reconciliation_required" else "",
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def post(self, request):
        return self._process_verify(request, request.data)

    def get(self, request):
        return self._process_verify(request, request.query_params.dict())


class OnlinePaymentCallbackView(OnlinePaymentVerifyView):
    """
    GET /api/fees/online/callback/
    Dedicated redirect endpoint for gateways returning via browser GET (e.g. eSewa v2 success_url).
    """
    pass


class OnlinePaymentOrderDetailView(APIView):
    """
    GET /api/fees/online/orders/<uuid:order_id>/
    Retrieves full details of an online payment order.
    Scoped by user_can_view_online_order.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(
            OnlinePaymentOrder.objects.select_related("student__profile", "payment"),
            id=order_id,
        )

        if not user_can_view_online_order(request, order):
            return Response(
                {"error": "You do not have permission to view this payment order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(OnlinePaymentOrderSerializer(order).data)


class OnlinePaymentOrderListView(APIView):
    """
    GET /api/fees/online/orders/
    Lists online payment orders scoped by caller role.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get(self, request):
        qs = OnlinePaymentOrder.objects.select_related("student__profile", "payment").order_by("-created_at")

        # Role scoping
        has_staff_perm = (
            HasPermission("view_fees").has_permission(request, None)
            or HasPermission("collect_payments").has_permission(request, None)
        )

        if not has_staff_perm:
            own_student = get_student_for_user(request.user)
            parent = get_parent_for_user(request.user)

            if own_student is not None and HasPermission("view_own_fees").has_permission(request, None):
                qs = qs.filter(student=own_student)
            elif parent is not None and HasPermission("view_child_fees").has_permission(request, None):
                child_ids = [rel.student_id for rel in get_linked_children(parent)]
                qs = qs.filter(student_id__in=child_ids)
            else:
                return Response(
                    {"error": "You do not have permission to view payment orders."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            student_id = model_param(request, "student", qs.model, "student")
            if student_id is not None:
                qs = qs.filter(student_id=student_id)

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        gateway_filter = request.query_params.get("gateway")
        if gateway_filter:
            qs = qs.filter(gateway=gateway_filter)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(OnlinePaymentOrderSerializer(page, many=True).data)

        return Response(OnlinePaymentOrderSerializer(qs, many=True).data)


class OnlinePaymentOrderReconcileView(APIView):
    """
    POST /api/fees/online/orders/<uuid:order_id>/reconcile/
    Allows administrative staff to trigger an on-demand status check and reconciliation with the gateway.
    """
    permission_classes = [IsAuthenticated, HasPermission("collect_payments")]

    def post(self, request, order_id):
        order = get_object_or_404(
            OnlinePaymentOrder.objects.select_related("student__profile", "payment"),
            id=order_id,
        )
        staff_member = get_staff_member_for_user(request.user)

        try:
            result = reconcile_online_payment_order(order, recorded_by=staff_member)
        except serializers.ValidationError:
            return Response({"error": PaymentEvidenceRejected.GENERIC_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected error during manual online payment reconciliation.")
            return Response({"error": "Reconciliation could not be completed."}, status=status.HTTP_400_BAD_REQUEST)

        order.refresh_from_db()

        log_action(
            request,
            action="online_payment_reconciled",
            model_name="OnlinePaymentOrder",
            object_id=order.id,
            changes={"status": order.status, "reason": order.reconciliation_reason},
        )

        return Response(
            {
                "status": result.get("status"),
                "gateway_status": result.get("gateway_status"),
                "order": OnlinePaymentOrderSerializer(order).data,
                "reason": order.reconciliation_reason,
            },
            status=status.HTTP_200_OK,
        )
