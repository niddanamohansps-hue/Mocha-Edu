import base64
import json

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from organizations.models import Organization, Domain
from .models import Payment
from .utils import generate_esewa_signature
from accounts.utils.crypto import decrypt_secret


class PaymentSecurityTest(TransactionTestCase):
    """
    Phase 0 security-fix verification: InitPaymentView no longer crashes,
    the stored password is encrypted at rest, and VerifyPaymentView rejects
    a payload whose eSewa signature doesn't match.
    """

    def setUp(self):
        connection.set_schema_to_public()
        from django.conf import settings

        self.secret = settings.ESEWA_CLIENT_SECRET or "test-secret"
        settings.ESEWA_CLIENT_SECRET = self.secret

        # payments/organizations endpoints are SHARED_APPS (public schema), but
        # TenantMainMiddleware still requires a matching Domain row to resolve
        # ANY schema (including public) - mirrors what seed_public.py does for
        # the real dev database, which the test database doesn't inherit.
        public_org, _ = Organization.objects.get_or_create(
            schema_name="public", defaults={"name": "Public Schema"}
        )
        Domain.objects.get_or_create(
            domain="testserver", tenant=public_org, defaults={"is_primary": True}
        )

    def tearDown(self):
        connection.set_schema_to_public()
        for org in Organization.objects.filter(schema_name="pay_test_school"):
            org.delete(force_drop=True)

    def _init_payment(self):
        client = APIClient()
        resp = client.post(
            "/api/payments/init/",
            {
                "organization_name": "Pay Test School",
                "subdomain": "pay_test_school",
                "username": "paytestowner",
                "email": "owner@paytest.com",
                "phone": "1234567890",
                "password": "OwnerPass123!",
            },
        )
        return client, resp

    def test_init_payment_does_not_crash_and_encrypts_password(self):
        client, resp = self._init_payment()
        self.assertEqual(resp.status_code, 200, resp.data if hasattr(resp, "data") else resp.content)
        self.assertIn("transaction_uuid", resp.data)

        payment = Payment.objects.get(transaction_uuid=resp.data["transaction_uuid"])
        self.assertNotEqual(
            payment.password,
            "OwnerPass123!",
            "SECURITY REGRESSION: payment password stored in plaintext",
        )
        self.assertEqual(decrypt_secret(payment.password), "OwnerPass123!")

    def _build_verify_payload(self, transaction_uuid, total_amount, tamper=False):
        payload = {
            "transaction_code": "TEST-CODE",
            "status": "COMPLETE",
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": "EPAYTEST",
            "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code",
        }
        message = ",".join(f"{f}={payload[f]}" for f in payload["signed_field_names"].split(","))
        signature = generate_esewa_signature(self.secret, message)
        if tamper:
            signature = "tampered" + signature
        payload["signature"] = signature
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        return encoded

    def test_verify_payment_rejects_forged_signature(self):
        client, init_resp = self._init_payment()
        transaction_uuid = init_resp.data["transaction_uuid"]

        forged_data = self._build_verify_payload(transaction_uuid, "500", tamper=True)
        resp = client.get(f"/api/payments/verify/?data={forged_data}")

        self.assertEqual(resp.status_code, 400)
        self.assertIn("Signature", resp.data.get("error", ""))

        payment = Payment.objects.get(transaction_uuid=transaction_uuid)
        self.assertEqual(
            payment.status,
            "PENDING",
            "SECURITY REGRESSION: payment marked COMPLETED despite invalid signature",
        )

    def test_verify_payment_accepts_valid_signature_and_creates_tenant(self):
        client, init_resp = self._init_payment()
        transaction_uuid = init_resp.data["transaction_uuid"]

        valid_data = self._build_verify_payload(transaction_uuid, "500", tamper=False)
        resp = client.get(f"/api/payments/verify/?data={valid_data}")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            Organization.objects.filter(schema_name="pay_test_school").exists()
        )

        payment = Payment.objects.get(transaction_uuid=transaction_uuid)
        self.assertEqual(payment.status, "COMPLETED")
