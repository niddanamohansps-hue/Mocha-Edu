import logging
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Payment
from .utils import (
    PaymentConfigurationError,
    decode_and_verify_signup_callback,
    ensure_signup_gateway_is_production_safe,
    generate_esewa_signature,
    get_esewa_secret,
    get_signup_payment_amount,
    parse_callback_amount,
)
from accounts.serializers import OrganizationRegisterSerializer
from accounts.utils.crypto import encrypt_secret, decrypt_secret

logger = logging.getLogger(__name__)

PAYMENT_UNAVAILABLE = {"error": "Payment service is not configured."}
# One answer for every callback that cannot be verified: it must not reveal which check failed.
VERIFICATION_FAILED = {"error": "Payment could not be verified."}
# Shown when the payment is verified but the institution could not be set up; details go to the log.
SETUP_FAILED = {
    "error": "Your payment was received, but we could not finish setting up your institution. "
    "Please contact support."
}


class InitPaymentView(APIView):
    # Public signup flow: no account exists yet. Stated explicitly so the strict default
    # permission policy in settings does not apply to it.
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup_payment_init"

    def post(self, request):
        try:
            esewa_secret = get_esewa_secret()
        except PaymentConfigurationError:
            logger.warning("eSewa payment init rejected: payment secret is not configured.")
            return Response(PAYMENT_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            amount = get_signup_payment_amount()
        except PaymentConfigurationError:
            logger.warning("eSewa payment init rejected: signup payment amount is invalid.")
            return Response(PAYMENT_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Use product code from settings or default to EPAYTEST
        product_code = getattr(settings, "ESEWA_PRODUCT_CODE", "EPAYTEST")
        try:
            ensure_signup_gateway_is_production_safe(product_code)
        except PaymentConfigurationError as exc:
            logger.warning("eSewa payment init rejected: %s", exc)
            return Response(PAYMENT_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Validate the registration data now, before any money moves: a customer must not pay and
        # only then learn that the subdomain or username is taken. Nothing is stored on failure.
        registration = OrganizationRegisterSerializer(data=request.data)
        if not registration.is_valid():
            return Response(registration.errors, status=status.HTTP_400_BAD_REQUEST)
        data = registration.validated_data

        # Create pending payment record
        transaction_uuid = uuid.uuid4().hex

        Payment.objects.create(
            transaction_uuid=transaction_uuid,
            amount=amount,
            organization_name=data["organization_name"],
            subdomain=data["subdomain"],
            username=data["username"],
            email=data["email"],
            phone=data.get("phone", ""),
            password=encrypt_secret(data["password"]),
        )

        # Message format strictly: total_amount,transaction_uuid,product_code
        message = f"total_amount={amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        signature = generate_esewa_signature(esewa_secret, message)

        return Response(
            {
                "signature": signature,
                "transaction_uuid": transaction_uuid,
                "product_code": product_code,
                "amount": amount,
                "url": settings.ESEWA_URL,
            }
        )


class VerifyPaymentView(APIView):
    # Public gateway return URL for the signup payment; authenticity is checked via the HMAC signature.
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup_payment_verify"

    @staticmethod
    def _rejected():
        return Response(VERIFICATION_FAILED, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try:
            esewa_secret = get_esewa_secret()
        except PaymentConfigurationError:
            logger.warning("eSewa callback rejected: payment secret is not configured.")
            return Response(PAYMENT_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        product_code = getattr(settings, "ESEWA_PRODUCT_CODE", "EPAYTEST")
        try:
            ensure_signup_gateway_is_production_safe(product_code)
        except PaymentConfigurationError as exc:
            logger.warning("eSewa callback rejected: %s", exc)
            return Response(PAYMENT_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Authenticity first: nothing in the callback is used (not even to find the payment)
        # until its signature has been checked over the fields that carry its identity.
        decoded = decode_and_verify_signup_callback(request.query_params.get("data"), esewa_secret)
        if decoded is None:
            return self._rejected()

        try:
            transaction_uuid = uuid.UUID(str(decoded.get("transaction_uuid")))
        except ValueError:
            return self._rejected()
        payment = Payment.objects.filter(transaction_uuid=transaction_uuid).first()
        if payment is None:
            return self._rejected()

        if decoded.get("product_code") != product_code:
            return self._rejected()
        paid_amount = parse_callback_amount(decoded.get("total_amount"))
        if paid_amount is None or paid_amount != payment.amount:
            return self._rejected()

        # Authentic and about this payment: a status other than COMPLETE is eSewa's own answer.
        if decoded.get("status") != "COMPLETE":
            return Response(
                {"error": "Payment not complete"}, status=status.HTTP_400_BAD_REQUEST
            )

        if payment.status == "COMPLETED":
            return Response(
                {"message": "Payment already processed and organization created"}
            )

        # Proceed to register organization
        # We need to use the data stored in Payment
        payment.status = "COMPLETED"
        payment.save()

        try:
            register_data = {
                "organization_name": payment.organization_name,
                "subdomain": payment.subdomain,
                "username": payment.username,
                "email": payment.email,
                "password": decrypt_secret(payment.password),
                "phone": payment.phone,
            }
            serializer = OrganizationRegisterSerializer(data=register_data)
            if not serializer.is_valid():
                # Validated at init, so this means the data changed since (e.g. the subdomain was
                # taken in the meantime). The payment is already recorded as paid.
                logger.error(
                    "Signup payment %s verified but registration data is no longer valid (fields: %s).",
                    payment.transaction_uuid,
                    sorted(serializer.errors),
                )
                return Response(SETUP_FAILED, status=status.HTTP_400_BAD_REQUEST)
            result = serializer.save()
        except Exception:
            logger.exception(
                "Signup payment %s verified but the institution could not be created.",
                payment.transaction_uuid,
            )
            return Response(SETUP_FAILED, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                "message": "Payment verified and Tenant created successfully",
                "domain_url": result.get("domain_url"),
            }
        )
