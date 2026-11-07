import logging

from django.db import connection
from django.http import Http404
from django_tenants.utils import get_public_schema_name
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.audit import log_action

from . import paylinks
from .gateways import PaymentConfigurationError, PaymentGatewayError

logger = logging.getLogger(__name__)
UNAVAILABLE = "Online payment is not available right now. Please pay at the school office."


def _student_or_404(token):
    if connection.schema_name == get_public_schema_name():
        raise Http404()
    student = paylinks.student_from_token(token)
    if student is None:
        raise Http404()  # the same answer for a forged, expired or unknown link
    return student


class PayLinkDetailView(APIView):
    """What a reminder's pay link shows: the student's outstanding fees. No login."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_pay_link"

    def get(self, request, token):
        student = _student_or_404(token)
        fees = paylinks.outstanding_fees(student)
        response = Response(
            {
                "school": getattr(connection.tenant, "name", ""),
                "student": f"{student.profile.first_name} {student.profile.last_name}".strip(),
                "available": paylinks.online_payment_available(),
                "total": sum((f._outstanding for f in fees), 0),
                "fees": [
                    {"id": f.id, "fee_head": f.fee_head.name, "due_date": f.due_date, "outstanding": f._outstanding}
                    for f in fees
                ],
            }
        )
        response["Cache-Control"] = "no-store"
        return response


class PayLinkStartView(APIView):
    """Start paying from a reminder's pay link. Returns what the gateway's checkout needs."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_pay_link_start"

    def post(self, request, token):
        student = _student_or_404(token)
        fee_ids = request.data.get("fees") if hasattr(request.data, "get") else None
        if fee_ids is not None and not isinstance(fee_ids, list):
            return Response({"error": "Choose the fees to pay."}, status=status.HTTP_400_BAD_REQUEST)
        if not paylinks.online_payment_available():
            return Response({"error": UNAVAILABLE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            order, payload = paylinks.start_payment(student, fee_ids)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (PaymentConfigurationError, PaymentGatewayError):
            logger.exception("A pay link payment could not be started.")
            return Response({"error": UNAVAILABLE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        log_action(
            request, "pay_link_payment_started", "OnlinePaymentOrder", str(order.id),
            {"student": str(student.id), "amount": str(order.amount), "gateway": order.gateway},
        )
        response = Response(
            {
                "gateway_payload": {
                    "gateway": payload.gateway,
                    "gateway_url": payload.gateway_url,
                    "method": payload.method,
                    "form_parameters": payload.form_parameters,
                    "order_id": payload.order_id,
                    "gateway_order_id": payload.gateway_order_id,
                },
                "amount": order.amount,
            },
            status=status.HTTP_201_CREATED,
        )
        response["Cache-Control"] = "no-store"
        return response
