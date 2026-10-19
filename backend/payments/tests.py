import base64
import json

from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from organizations.models import Organization, Domain
from .models import Payment
from .utils import PaymentConfigurationError, generate_esewa_signature, get_esewa_secret
from accounts.utils.crypto import decrypt_secret

TEST_ESEWA_SECRET = "test-esewa-secret-not-production"


@override_settings(ESEWA_CLIENT_SECRET=TEST_ESEWA_SECRET)
class PaymentSecurityTest(TransactionTestCase):
    """
    Phase 0 security-fix verification: InitPaymentView no longer crashes,
    the stored password is encrypted at rest, and VerifyPaymentView rejects
    a payload whose eSewa signature doesn't match.
    """

    def setUp(self):
        connection.set_schema_to_public()
        self.secret = TEST_ESEWA_SECRET

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


class PaymentFailClosedTest(TransactionTestCase):
    """
    Phase 0.1: with no eSewa secret, payment init and callback verification
    must reject every request, and must never sign or accept with an empty key.
    """

    def setUp(self):
        connection.set_schema_to_public()
        public_org, _ = Organization.objects.get_or_create(
            schema_name="public", defaults={"name": "Public Schema"}
        )
        Domain.objects.get_or_create(
            domain="testserver", tenant=public_org, defaults={"is_primary": True}
        )

    def tearDown(self):
        connection.set_schema_to_public()
        for org in Organization.objects.filter(schema_name="failclosed_test_school"):
            org.delete(force_drop=True)

    def _init_payload(self):
        return {
            "organization_name": "Fail Closed School",
            "subdomain": "failclosed_test_school",
            "username": "failclosedowner",
            "email": "owner@failclosed.com",
            "phone": "1234567890",
            "password": "OwnerPass123!",
        }

    def _signed_callback(self, transaction_uuid):
        payload = {
            "transaction_code": "TEST-CODE",
            "status": "COMPLETE",
            "total_amount": "500",
            "transaction_uuid": transaction_uuid,
            "product_code": "EPAYTEST",
            "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code",
        }
        message = ",".join(f"{f}={payload[f]}" for f in payload["signed_field_names"].split(","))
        payload["signature"] = generate_esewa_signature(TEST_ESEWA_SECRET, message)
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def _assert_unavailable(self, resp):
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data, {"error": "Payment service is not configured."})
        self.assertNotIn(TEST_ESEWA_SECRET, str(resp.data))

    @override_settings(ESEWA_CLIENT_SECRET=None)
    def test_init_rejects_missing_secret_and_creates_no_payment(self):
        before = Payment.objects.count()
        resp = APIClient().post("/api/payments/init/", self._init_payload())
        self._assert_unavailable(resp)
        self.assertEqual(Payment.objects.count(), before)

    @override_settings(ESEWA_CLIENT_SECRET="")
    def test_init_rejects_empty_secret_and_creates_no_payment(self):
        before = Payment.objects.count()
        resp = APIClient().post("/api/payments/init/", self._init_payload())
        self._assert_unavailable(resp)
        self.assertEqual(Payment.objects.count(), before)

    @override_settings(ESEWA_CLIENT_SECRET=TEST_ESEWA_SECRET)
    def test_verify_with_valid_signature_is_rejected_when_secret_later_removed(self):
        init = APIClient().post("/api/payments/init/", self._init_payload())
        self.assertEqual(init.status_code, 200)
        transaction_uuid = init.data["transaction_uuid"]
        callback = self._signed_callback(transaction_uuid)

        with override_settings(ESEWA_CLIENT_SECRET=None):
            resp = APIClient().get(f"/api/payments/verify/?data={callback}")

        self._assert_unavailable(resp)
        self.assertEqual(Payment.objects.get(transaction_uuid=transaction_uuid).status, "PENDING")
        self.assertFalse(Organization.objects.filter(schema_name="failclosed_test_school").exists())

    @override_settings(ESEWA_CLIENT_SECRET=None)
    def test_verify_rejects_malformed_callback_when_secret_missing(self):
        resp = APIClient().get("/api/payments/verify/?data=not-base64-at-all")
        self._assert_unavailable(resp)

    @override_settings(ESEWA_CLIENT_SECRET=None)
    def test_signing_helper_refuses_missing_and_empty_keys(self):
        for bad_key in (None, ""):
            with self.subTest(key=repr(bad_key)):
                with self.assertRaises(PaymentConfigurationError):
                    generate_esewa_signature(bad_key, "total_amount=500")
        with self.assertRaises(PaymentConfigurationError):
            get_esewa_secret()

    @override_settings(ESEWA_CLIENT_SECRET=TEST_ESEWA_SECRET, ESEWA_PRODUCT_CODE="EPAYTEST")
    def test_valid_secret_still_signs_and_verifies(self):
        self.assertEqual(get_esewa_secret(), TEST_ESEWA_SECRET)
        resp = APIClient().post("/api/payments/init/", self._init_payload())
        self.assertEqual(resp.status_code, 200)
        expected = generate_esewa_signature(
            TEST_ESEWA_SECRET,
            f"total_amount=500,transaction_uuid={resp.data['transaction_uuid']},product_code=EPAYTEST",
        )
        self.assertEqual(resp.data["signature"], expected)

    @override_settings(ESEWA_CLIENT_SECRET=None)
    def test_secret_never_appears_in_logs_on_rejection(self):
        with self.assertLogs("payments.views", level="WARNING") as captured:
            APIClient().post("/api/payments/init/", self._init_payload())
        joined = "\n".join(captured.output)
        self.assertIn("payment secret is not configured", joined)
        self.assertNotIn(TEST_ESEWA_SECRET, joined)


class PaymentSignupAmountTest(TransactionTestCase):
    """
    Phase 0.2: the signup amount comes from ESEWA_SIGNUP_PAYMENT_AMOUNT, and
    invalid values are rejected before any payment row or signature is created.
    """

    def setUp(self):
        connection.set_schema_to_public()
        public_org, _ = Organization.objects.get_or_create(
            schema_name="public", defaults={"name": "Public Schema"}
        )
        Domain.objects.get_or_create(
            domain="testserver", tenant=public_org, defaults={"is_primary": True}
        )

    def _init(self):
        return APIClient().post(
            "/api/payments/init/",
            {
                "organization_name": "Amount School",
                "subdomain": "amount_test_school",
                "username": "amountowner",
                "email": "owner@amount.com",
                "phone": "1234567890",
                "password": "OwnerPass123!",
            },
        )

    @override_settings(ESEWA_CLIENT_SECRET=TEST_ESEWA_SECRET, ESEWA_SIGNUP_PAYMENT_AMOUNT="500")
    def test_default_amount_preserves_existing_500(self):
        resp = self._init()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["amount"], "500")
        payment = Payment.objects.get(transaction_uuid=resp.data["transaction_uuid"])
        self.assertEqual(payment.amount, Decimal("500"))

    @override_settings(ESEWA_CLIENT_SECRET=TEST_ESEWA_SECRET, ESEWA_SIGNUP_PAYMENT_AMOUNT="750", ESEWA_PRODUCT_CODE="EPAYTEST")
    def test_custom_amount_reaches_payload_signature_and_record(self):
        resp = self._init()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["amount"], "750")
        expected = generate_esewa_signature(
            TEST_ESEWA_SECRET,
            f"total_amount=750,transaction_uuid={resp.data['transaction_uuid']},product_code=EPAYTEST",
        )
        self.assertEqual(resp.data["signature"], expected)
        payment = Payment.objects.get(transaction_uuid=resp.data["transaction_uuid"])
        self.assertEqual(payment.amount, Decimal("750"))

    @override_settings(ESEWA_CLIENT_SECRET=TEST_ESEWA_SECRET, ESEWA_SIGNUP_PAYMENT_AMOUNT="750.50")
    def test_decimal_amount_with_two_places_accepted(self):
        resp = self._init()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["amount"], "750.50")

    def test_invalid_amounts_rejected_without_creating_payment(self):
        bad_values = ["", "   ", "abc", "0", "0.00", "-5", "NaN", "Infinity", "1e3", "750.555", "100000000"]
        for bad in bad_values:
            with self.subTest(value=repr(bad)):
                before = Payment.objects.count()
                with override_settings(ESEWA_CLIENT_SECRET=TEST_ESEWA_SECRET, ESEWA_SIGNUP_PAYMENT_AMOUNT=bad):
                    resp = self._init()
                self.assertEqual(resp.status_code, 503)
                self.assertEqual(resp.data, {"error": "Payment service is not configured."})
                self.assertEqual(Payment.objects.count(), before)

    @override_settings(ESEWA_CLIENT_SECRET=None, ESEWA_SIGNUP_PAYMENT_AMOUNT="750")
    def test_phase_0_1_missing_secret_still_fails_closed_with_valid_amount(self):
        before = Payment.objects.count()
        resp = self._init()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(Payment.objects.count(), before)

    @override_settings(ESEWA_CLIENT_SECRET="", ESEWA_SIGNUP_PAYMENT_AMOUNT="750")
    def test_phase_0_1_empty_secret_still_fails_closed_with_valid_amount(self):
        before = Payment.objects.count()
        resp = self._init()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(Payment.objects.count(), before)
