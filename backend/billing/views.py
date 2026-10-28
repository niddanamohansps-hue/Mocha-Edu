"""
Public signup on a plan (public site, no login):

- GET  /api/billing/plans/            plans for the pricing page and signup
- POST /api/billing/signup/           {plan, cycle, organization_name, subdomain, username, email, phone,
                                       password}: a trial school is created at once; otherwise Razorpay
                                       Checkout parameters for the first payment are returned
- POST /api/billing/signup/confirm/   Razorpay's signed answer; the school is created once it is verified
"""
import logging

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.serializers import OrganizationRegisterSerializer
from fees.gateways import PaymentGatewayError
from payments import services as signup_services

from .models import Plan
from .services import BillingError
from .signup import SignupPaymentRejected, confirm_razorpay_signup, razorpay_checkout, resolve_plan, signup_total

logger = logging.getLogger(__name__)

UNAVAILABLE = {"error": "Online payment is not available right now. Please try again later."}
NOT_VERIFIED = {"error": "Payment could not be verified."}
SETUP_FAILED = {"error": "Your payment was received, but we could not finish setting up your school. Please contact support."}


def _price(value):
    return None if value is None else str(value)


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["code", "name", "description", "features", "student_limit", "monthly_price", "yearly_price",
                  "one_time_price", "one_time_validity_days", "trial_days", "gst_percent"]


class PublicPlansView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(PlanSerializer(Plan.objects.filter(is_public=True), many=True).data)


def _setup_response(outcome, result, payment):
    if outcome == signup_services.PROVISIONED:
        return Response({"status": "ready", "login_url": result.get("domain_url")})
    if outcome == signup_services.ALREADY_PROVISIONED:
        return Response({"status": "ready", "login_url": ""})
    if outcome == signup_services.IN_PROGRESS:
        return Response({"status": "setting_up"}, status=status.HTTP_202_ACCEPTED)
    payment.refresh_from_db()
    retryable = payment.failure_code not in signup_services.PERMANENT_FAILURE_CODES
    return Response(SETUP_FAILED, status=status.HTTP_500_INTERNAL_SERVER_ERROR if retryable else status.HTTP_400_BAD_REQUEST)


class PlanSignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup_payment_init"

    def post(self, request):
        try:
            plan = resolve_plan(request.data.get("plan"), request.data.get("cycle"))
        except BillingError as exc:
            return Response({"plan": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        cycle = request.data["cycle"]

        # Check the school's details before any money moves; nothing is stored when they are invalid.
        registration = OrganizationRegisterSerializer(data=request.data)
        if not registration.is_valid():
            return Response(registration.errors, status=status.HTTP_400_BAD_REQUEST)

        trial = plan.trial_days > 0
        amount = 0 if trial else signup_total(plan, cycle)
        payment = signup_services.create_pending_payment(amount=amount, data=registration.validated_data)
        if payment is None:
            return Response({"subdomain": ["This subdomain is already taken."]}, status=status.HTTP_400_BAD_REQUEST)
        payment.plan, payment.cycle = plan, cycle
        payment.save(update_fields=["plan", "cycle", "updated_at"])

        if trial:
            payment.gateway = "trial"
            payment.save(update_fields=["gateway", "updated_at"])
            outcome, result = signup_services.process_confirmed_payment(payment.pk, gateway_reference="trial")
            return _setup_response(outcome, result, payment)

        try:
            checkout = razorpay_checkout(payment)
        except (BillingError, PaymentGatewayError) as exc:
            logger.error("Signup payment could not start: %s", exc)
            return Response(UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"status": "pay", "checkout": checkout, "total": str(amount)})


class PlanSignupConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup_payment_verify"

    def post(self, request):
        try:
            payment, confirmed = confirm_razorpay_signup(
                razorpay_order_id=request.data.get("razorpay_order_id"),
                razorpay_payment_id=request.data.get("razorpay_payment_id"),
                razorpay_signature=request.data.get("razorpay_signature"),
            )
        except SignupPaymentRejected:
            return Response(NOT_VERIFIED, status=status.HTTP_400_BAD_REQUEST)
        except BillingError:
            return Response(UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not confirmed:
            return Response({"status": "checking"}, status=status.HTTP_202_ACCEPTED)
        outcome, result = signup_services.process_confirmed_payment(
            payment.pk, gateway_reference=str(request.data["razorpay_payment_id"])[:100]
        )
        return _setup_response(outcome, result, payment)
