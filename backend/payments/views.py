import base64
import hmac
import json
import logging
import uuid
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# Payment Viewsttings
from .models import Payment
from .utils import (
    PaymentConfigurationError,
    generate_esewa_signature,
    get_esewa_secret,
    get_signup_payment_amount,
)
from accounts.serializers import OrganizationRegisterSerializer
from accounts.utils.crypto import encrypt_secret, decrypt_secret

logger = logging.getLogger(__name__)

PAYMENT_UNAVAILABLE = {"error": "Payment service is not configured."}


class InitPaymentView(APIView):
    # Public signup flow: no account exists yet. Stated explicitly so the strict default
    # permission policy in settings does not apply to it.
    permission_classes = [AllowAny]

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

        data = request.data

        # Create pending payment record
        transaction_uuid = uuid.uuid4().hex

        Payment.objects.create(
            transaction_uuid=transaction_uuid,
            amount=amount,
            organization_name=data.get("organization_name"),
            subdomain=data.get("subdomain"),
            username=data.get("username"),
            email=data.get("email"),
            phone=data.get("phone"),
            password=encrypt_secret(data.get("password")),
        )

        # Use product code from settings or default to EPAYTEST
        # Use getattr only if not adding it to settings, but since we added it, we can use settings.ESEWA_PRODUCT_CODE
        # provided it's safely loaded.
        product_code = getattr(settings, "ESEWA_PRODUCT_CODE", "EPAYTEST")

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

    def get(self, request):
        try:
            esewa_secret = get_esewa_secret()
        except PaymentConfigurationError:
            logger.warning("eSewa callback rejected: payment secret is not configured.")
            return Response(PAYMENT_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        encoded_data = request.query_params.get("data")
        if not encoded_data:
            return Response(
                {"error": "Missing data"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            decoded_bytes = base64.b64decode(encoded_data)
            decoded_json = json.loads(decoded_bytes)
        except Exception:
            return Response(
                {"error": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST
            )

        if decoded_json.get("status") != "COMPLETE":
            return Response(
                {"error": "Payment not complete"}, status=status.HTTP_400_BAD_REQUEST
            )

        transaction_uuid = decoded_json.get("transaction_uuid")

        try:
            payment = Payment.objects.get(transaction_uuid=transaction_uuid)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if payment.status == "COMPLETED":
            return Response(
                {"message": "Payment already processed and organization created"}
            )

        # Validate Amount (Simple check)
        # eSewa returns total_amount.
        if float(decoded_json.get("total_amount", 0)) != float(payment.amount):
            return Response(
                {"error": "Amount mismatch"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Verify eSewa's signature over the fields it says it signed, using the
        # same shared secret/HMAC scheme used to sign the initial payment request.
        # Without this, the payload above is entirely client-suppliable and anyone
        # could forge a "COMPLETE" response for an existing transaction_uuid.
        signed_field_names = decoded_json.get("signed_field_names")
        provided_signature = decoded_json.get("signature")
        if not signed_field_names or not provided_signature:
            return Response(
                {"error": "Missing signature"}, status=status.HTTP_400_BAD_REQUEST
            )

        fields = [f.strip() for f in signed_field_names.split(",") if f.strip()]
        try:
            message = ",".join(f"{field}={decoded_json.get(field, '')}" for field in fields)
        except Exception:
            return Response(
                {"error": "Invalid signed_field_names"}, status=status.HTTP_400_BAD_REQUEST
            )

        expected_signature = generate_esewa_signature(esewa_secret, message)
        if not hmac.compare_digest(expected_signature, provided_signature):
            return Response(
                {"error": "Signature verification failed"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Proceed to register organization
        # We need to use the data stored in Payment
        payment.status = "COMPLETED"
        payment.save()

        register_data = {
            "organization_name": payment.organization_name,
            "subdomain": payment.subdomain,
            "username": payment.username,
            "email": payment.email,
            "password": decrypt_secret(payment.password),
            "phone": payment.phone,
        }

        serializer = OrganizationRegisterSerializer(data=register_data)
        if serializer.is_valid():
            try:
                result = serializer.save()

                return Response(
                    {
                        "message": "Payment verified and Tenant created successfully",
                        "domain_url": result.get("domain_url"),
                    }
                )
            except Exception as e:
                # Log the actual error for debugging
                print(f"Error during tenant creation: {str(e)}")
                # Return a cleaner error message to the frontend
                return Response(
                    {
                        "error": f"Payment verified but failed to set up institution: {str(e)}"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            # If registration fails, we might want to log this or handle it manually
            # Payment is marked COMPLETED but Org not created?
            # We should probably revert payment status or log invalid data.
            # detailed error response
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
