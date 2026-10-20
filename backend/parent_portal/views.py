import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from roles.permissions import HasPermission

from .serializers import ChildExamResultSerializer, ChildTimetableEntrySerializer
from .services import get_child_for_parent, get_linked_children, get_parent_for_user

logger = logging.getLogger(__name__)

NOT_A_PARENT = {"error": "Parent portal access is not available for this account."}
NO_CHILD_ACCESS = {"error": "You do not have access to this child."}


class ParentMeView(APIView):
    """Resolves the caller's own Parent record - no permission beyond
    IsAuthenticated, matching profiles.MyProfileView's "my own resource"
    precedent."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        return Response(
            {
                "parent_id": str(parent.id),
                "full_name": f"{parent.profile.first_name} {parent.profile.last_name}",
                "occupation": parent.occupation,
                "office_address": parent.office_address,
                "income_level": parent.income_level,
                "children_count": parent.student_links.count(),
            }
        )


class LinkedChildrenView(APIView):
    permission_classes = [IsAuthenticated, HasPermission("view_own_children")]

    def get(self, request):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        data = []
        for rel in get_linked_children(parent):
            student = rel.student
            enrollments = getattr(student, "current_enrollment_list", None) or []
            current = enrollments[0] if enrollments else None
            data.append(
                {
                    "student_id": str(student.id),
                    "full_name": f"{student.profile.first_name} {student.profile.last_name}",
                    "enrollment_id": student.enrollment_id,
                    "relation_type": rel.relation_type,
                    "is_primary_contact": rel.is_primary_contact,
                    "can_pickup": rel.can_pickup,
                    "level": current.level.name if current and current.level_id else None,
                    "section": current.section.name if current and current.section_id else None,
                    "academic_year": current.academic_year if current else None,
                }
            )

        return Response(data)


class ChildAttendanceView(APIView):
    """Queries attendance.models.StudentAttendance directly - never calls the
    Attendance API. Reuses attendance.services.calculate_attendance_percentage
    (a pure calculation function) so the percentage formula never drifts from
    the one used everywhere else."""

    permission_classes = [IsAuthenticated, HasPermission("view_child_attendance")]

    def get(self, request, student_id):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        student = get_child_for_parent(parent, student_id)
        if student is None:
            return Response(NO_CHILD_ACCESS, status=403)

        from attendance.models import AttendanceSettings, StudentAttendance
        from attendance.services import calculate_attendance_percentage

        qs = StudentAttendance.objects.filter(student=student).select_related("session")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date:
            qs = qs.filter(session__date__gte=start_date)
        if end_date:
            qs = qs.filter(session__date__lte=end_date)
        qs = qs.order_by("-session__date")

        counts = {}
        for row in qs:
            counts[row.status] = counts.get(row.status, 0) + 1

        percentage = calculate_attendance_percentage(counts, AttendanceSettings.get_solo())

        return Response(
            {
                "student": str(student.id),
                "counts": counts,
                "percentage": percentage,
                "records": [
                    {"date": r.session.date, "status": r.status, "remarks": r.remarks}
                    for r in qs
                ],
            }
        )


class ChildTimetableView(APIView):
    """Queries timetable.models.TimetableEntry directly - never calls the
    Timetable API."""

    permission_classes = [IsAuthenticated, HasPermission("view_child_timetable")]

    def get(self, request, student_id):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        student = get_child_for_parent(parent, student_id)
        if student is None:
            return Response(NO_CHILD_ACCESS, status=403)

        current = student.enrollments.filter(is_current=True).first()
        if not current or not current.section_id:
            return Response({"student": str(student.id), "section": None, "results": []})

        from timetable.models import TimetableEntry

        academic_year = request.query_params.get("academic_year")
        qs = TimetableEntry.objects.filter(section_id=current.section_id).select_related(
            "subject", "period", "room", "instructor__staff_member__profile"
        )
        if academic_year:
            qs = qs.filter(academic_year=academic_year)

        return Response(
            {
                "student": str(student.id),
                "section": str(current.section_id),
                "results": ChildTimetableEntrySerializer(qs, many=True).data,
            }
        )


class ChildResultsView(APIView):
    """Queries only published examinations.models.ExamResult rows.
    ExamResult rows only ever exist post-publication (see
    examinations.services.publish_examination), so this can never leak an
    unpublished/draft result regardless of any other logic here."""

    permission_classes = [IsAuthenticated, HasPermission("view_child_results")]

    def get(self, request, student_id):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        student = get_child_for_parent(parent, student_id)
        if student is None:
            return Response(NO_CHILD_ACCESS, status=403)

        from examinations.models import ExamResult

        academic_year = request.query_params.get("academic_year")
        results = ExamResult.objects.filter(student=student).select_related("examination")
        if academic_year:
            results = results.filter(academic_year=academic_year)

        return Response(ChildExamResultSerializer(results, many=True).data)


class ChildUpcomingExamsView(APIView):
    """
    Not one of the 6 endpoints in the original spec list, added to satisfy
    the Dashboard section's explicit "upcoming examination/schedule
    information" bullet - none of the other endpoints can supply this
    (published ExamResult only ever covers past/graded exams). Queries
    examinations.models.ExamSchedule directly, exactly like every other
    Parent Portal view queries its underlying model directly, and reuses
    view_child_results rather than adding a 5th permission codename.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_child_results")]

    def get(self, request, student_id):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        student = get_child_for_parent(parent, student_id)
        if student is None:
            return Response(NO_CHILD_ACCESS, status=403)

        current = student.enrollments.filter(is_current=True).first()
        if not current or not current.section_id:
            return Response([])

        from django.utils import timezone

        from examinations.models import ExamSchedule

        qs = (
            ExamSchedule.objects.filter(section_id=current.section_id, date__gte=timezone.localdate())
            .select_related("subject", "examination")
            .order_by("date", "start_time")[:10]
        )
        return Response(
            [
                {
                    "id": str(s.id),
                    "examination": str(s.examination_id),
                    "examination_name": s.examination.name,
                    "subject_name": s.subject.name,
                    "date": s.date,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                }
                for s in qs
            ]
        )


class ChildFeesView(APIView):
    """
    Queries fees.models.StudentFee/Payment directly - never calls the
    Fees app's own staff-facing endpoints. Reuses fees.services'
    pure calculation function (get_outstanding_balance), exactly
    matching how ChildAttendanceView reuses attendance.services'
    calculate_attendance_percentage.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_child_fees")]

    def get(self, request, student_id):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        student = get_child_for_parent(parent, student_id)
        if student is None:
            return Response(NO_CHILD_ACCESS, status=403)

        from fees.models import Payment, StudentFee
        from fees.services import get_amount_paid, get_outstanding_balance

        fee_qs = StudentFee.objects.filter(student=student).select_related("fee_head")
        fees_data = []
        total_outstanding = 0
        for sf in fee_qs:
            outstanding = get_outstanding_balance(sf)
            if sf.status == "active":
                total_outstanding += outstanding
            fees_data.append(
                {
                    "id": str(sf.id),
                    "fee_head": sf.fee_head.name,
                    "academic_year": sf.academic_year,
                    "amount_due": sf.amount_due,
                    "discount_amount": sf.discount_amount,
                    "amount_paid": get_amount_paid(sf),
                    "outstanding_balance": outstanding,
                    "due_date": sf.due_date,
                    "status": sf.status,
                }
            )

        payment_qs = Payment.objects.filter(student=student).order_by("-created_at")
        payments_data = [
            {
                "id": str(p.id),
                "amount": p.amount,
                "method": p.method,
                "status": p.status,
                "receipt_number": p.receipt_number,
                "created_at": p.created_at,
            }
            for p in payment_qs
        ]

        return Response(
            {
                "student": str(student.id),
                "total_outstanding": total_outstanding,
                "fees": fees_data,
                "payments": payments_data,
            }
        )


class ChildReportCardView(APIView):
    """
    Renders published examination results, attendance, promotion status, GPA, and school branding
    for the selected child within one academic year.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_child_results")]

    def get(self, request, student_id):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        student = get_child_for_parent(parent, student_id)
        if student is None:
            return Response(NO_CHILD_ACCESS, status=403)

        from examinations.services import build_student_report_card

        academic_year = request.query_params.get("academic_year")
        report_card = build_student_report_card(student, academic_year=academic_year)
        return Response(report_card)


class ChildTranscriptView(APIView):
    """
    Renders official multi-year academic transcript for the selected child.
    """

    permission_classes = [IsAuthenticated, HasPermission("view_child_results")]

    def get(self, request, student_id):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        student = get_child_for_parent(parent, student_id)
        if student is None:
            return Response(NO_CHILD_ACCESS, status=403)

        from examinations.services import build_student_transcript

        transcript = build_student_transcript(student)
        return Response(transcript)


class ChildPayFeeView(APIView):
    """
    POST /api/parent-portal/children/<uuid:student_id>/pay-fees/
    Initiates an online payment order for the parent's linked child.
    Strictly checks parent record and StudentParentRelation before initiating.
    """

    permission_classes = [IsAuthenticated, HasPermission("pay_child_fees")]

    def post(self, request, student_id):
        parent = get_parent_for_user(request.user)
        if parent is None:
            return Response(NOT_A_PARENT, status=403)

        student = get_child_for_parent(parent, student_id)
        if student is None:
            return Response(NO_CHILD_ACCESS, status=403)

        from core.audit import log_action
        from fees.gateways import PaymentConfigurationError, PaymentGatewayError
        from fees.serializers import OnlinePaymentOrderSerializer, ParentPortalChildPayFeeSerializer
        from fees.services import initiate_online_payment_order

        serializer = ParentPortalChildPayFeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

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
                callback_kind="parent_portal",  # return/failure URLs from the client are ignored
            )
        except (PaymentConfigurationError, PaymentGatewayError) as exc:
            logger.error("Parent online payment could not be initiated: %s", exc)
            return Response(
                {"error": "Online payment is currently unavailable. Please try again later or contact the school."},
                status=503,
            )

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
            status=201,
        )
