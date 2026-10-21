"""Stage F2a: signup-payment hardening (init validates before payment, strict signed callback,
generic errors, throttles, production guard, no free registration path).

None of these tests creates a tenant schema: provisioning is either not reached or is patched.
"""
import base64
import contextlib
import io
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from organizations.models import Domain, Organization
from .models import Payment
from .utils import generate_esewa_signature

SECRET = "test-esewa-secret-not-production"
GENERIC = {"error": "Payment could not be verified."}
PRODUCTION = dict(DEBUG=False, EDUSEKAI_ALLOW_DERIVED_TEST_DB=False)
REAL_URL = "https://epay.esewa.com.np/api/epay/main/v2/form"
PROVISION = "payments.services.provision_organization"


class SignupPaymentTestBase(TransactionTestCase):
    def setUp(self):
        connection.set_schema_to_public()
        cache.clear()
        public_org, _ = Organization.objects.get_or_create(
            schema_name="public", defaults={"name": "Public Schema"}
        )
        Domain.objects.get_or_create(domain="testserver", tenant=public_org, defaults={"is_primary": True})

    def tearDown(self):
        cache.clear()
        connection.set_schema_to_public()

    @staticmethod
    def registration(**overrides):
        data = {
            "organization_name": "F2a School",
            "subdomain": "f2a_school",
            "username": "f2aowner",
            "email": "owner@f2a.example",
            "phone": "9800000000",
            "password": "OwnerPass123!",
        }
        data.update(overrides)
        return data

    def init(self, **overrides):
        return APIClient().post("/api/payments/init/", self.registration(**overrides), format="json")

    def make_payment(self, **overrides):
        resp = self.init(**overrides)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        return Payment.objects.get(transaction_uuid=resp.data["transaction_uuid"])

    @staticmethod
    def callback(payment_or_uuid, *, secret=SECRET, signed="transaction_code,status,total_amount,transaction_uuid,product_code",
                 sign_fields=None, **overrides):
        """An encoded eSewa callback. ``overrides`` replace field values BEFORE signing."""
        uuid_value = getattr(payment_or_uuid, "transaction_uuid", payment_or_uuid)
        payload = {
            "transaction_code": "TEST-CODE",
            "status": "COMPLETE",
            "total_amount": "500",
            "transaction_uuid": uuid_value.hex if hasattr(uuid_value, "hex") else uuid_value,
            "product_code": "EPAYTEST",
        }
        payload.update(overrides)
        payload["signed_field_names"] = signed
        names = (sign_fields or signed).split(",")
        message = ",".join(f"{f}={payload[f]}" for f in names)
        payload["signature"] = generate_esewa_signature(secret, message)
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def verify(self, data):
        return APIClient().get("/api/payments/verify/", {"data": data})


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class SignupInitValidationTests(SignupPaymentTestBase):
    def assert_rejected_without_row(self, resp):
        self.assertEqual(resp.status_code, 400, getattr(resp, "data", None))
        self.assertEqual(Payment.objects.count(), 0)

    def test_valid_registration_still_creates_a_pending_payment(self):
        payment = self.make_payment()
        self.assertEqual(payment.status, "PENDING")
        self.assertEqual(payment.subdomain, "f2a_school")
        self.assertNotEqual(payment.password, "OwnerPass123!")

    def test_subdomain_already_taken_is_rejected_before_payment(self):
        self.assert_rejected_without_row(self.init(subdomain="public"))

    def test_username_already_taken_is_rejected_before_payment(self):
        get_user_model().objects.create_user(username="takenname", email="x@x.example", password="Whatever123!")
        self.assert_rejected_without_row(self.init(username="takenname"))

    def test_existing_email_with_wrong_password_is_rejected_before_payment(self):
        get_user_model().objects.create_user(username="existing", email="owner@f2a.example", password="RealPass123!")
        resp = self.init(password="NotTheRealOne1!")
        self.assert_rejected_without_row(resp)
        self.assertIn("password", resp.data)

    def test_existing_email_with_the_right_password_is_accepted(self):
        get_user_model().objects.create_user(username="existing", email="owner@f2a.example", password="RealPass123!")
        resp = self.init(username="anothername", password="RealPass123!")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))

    def test_missing_and_malformed_fields_are_rejected_with_400_not_500(self):
        for label, overrides in {
            "no organization": {"organization_name": ""},
            "bad email": {"email": "not-an-email"},
            "short password": {"password": "short"},
            "bad subdomain": {"subdomain": "has spaces"},
            "long phone": {"phone": "9" * 40},
        }.items():
            with self.subTest(label):
                self.assert_rejected_without_row(self.init(**overrides))

    def test_non_object_bodies_are_rejected_with_400(self):
        for body in ([], "text", 5, None):
            with self.subTest(body=repr(body)):
                resp = APIClient().post("/api/payments/init/", body, format="json")
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)

    def test_missing_fields_object_is_rejected_with_400(self):
        resp = APIClient().post("/api/payments/init/", {}, format="json")
        self.assert_rejected_without_row(resp)


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class SignupCallbackTests(SignupPaymentTestBase):
    def setUp(self):
        super().setUp()
        self.payment = self.make_payment()

    def assert_generic_rejection_and_untouched(self, resp):
        self.assertEqual(resp.status_code, 400, getattr(resp, "data", None))
        self.assertEqual(resp.data, GENERIC)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "PENDING")
        self.assertFalse(Organization.objects.filter(schema_name="f2a_school").exists())

    def test_all_kinds_of_unverifiable_callback_get_the_same_generic_answer(self):
        good = self.callback(self.payment)
        cases = {
            "no data": None,
            "not base64": "!!!not-base64!!!",
            "not json": base64.b64encode(b"plain text").decode(),
            "json list": base64.b64encode(b"[1,2]").decode(),
            "oversized": "A" * 9000,
            "tampered signature": good[:-8] + ("AAAAAAAA" if not good.endswith("AAAAAAAA") else "BBBBBBBB"),
            "wrong secret": self.callback(self.payment, secret="some-other-secret"),
            "unknown transaction": self.callback("0" * 32),
            "not a uuid": self.callback("not-a-uuid"),
            "wrong merchant": self.callback(self.payment, product_code="OTHER"),
            "wrong amount": self.callback(self.payment, total_amount="1"),
            "non-numeric amount": self.callback(self.payment, total_amount="five hundred"),
            "nan amount": self.callback(self.payment, total_amount="NaN"),
        }
        for label, data in cases.items():
            with self.subTest(label):
                resp = APIClient().get("/api/payments/verify/", {"data": data} if data is not None else {})
                self.assert_generic_rejection_and_untouched(resp)

    def test_callback_that_does_not_sign_the_identity_fields_is_rejected(self):
        for signed in ("status", "status,total_amount", "transaction_uuid,total_amount,product_code,transaction_code"):
            with self.subTest(signed=signed):
                self.assert_generic_rejection_and_untouched(self.verify(self.callback(self.payment, signed=signed)))

    def test_signature_over_a_different_field_set_than_named_is_rejected(self):
        data = self.callback(self.payment, sign_fields="status,total_amount,transaction_uuid,product_code")
        self.assert_generic_rejection_and_untouched(self.verify(data))

    def test_non_ascii_signature_is_a_clean_rejection_not_a_500(self):
        payload = json.loads(base64.b64decode(self.callback(self.payment)))
        payload["signature"] = "sïgnature-é"
        data = base64.b64encode(json.dumps(payload).encode()).decode()
        self.assert_generic_rejection_and_untouched(self.verify(data))

    def test_missing_signed_field_value_is_rejected(self):
        payload = json.loads(base64.b64decode(self.callback(self.payment)))
        del payload["transaction_code"]
        data = base64.b64encode(json.dumps(payload).encode()).decode()
        self.assert_generic_rejection_and_untouched(self.verify(data))

    def test_authentic_non_complete_status_is_reported_and_changes_nothing(self):
        resp = self.verify(self.callback(self.payment, status="PENDING"))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {"error": "Payment not complete"})
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "PENDING")

    def test_unsigned_non_complete_status_gets_no_special_answer(self):
        resp = self.verify(self.callback(self.payment, status="PENDING", secret="wrong"))
        self.assertEqual(resp.data, GENERIC)

    def test_already_provisioned_payment_is_not_processed_twice(self):
        Payment.objects.filter(pk=self.payment.pk).update(status="PROVISIONED")
        with mock.patch(PROVISION) as provision:
            resp = self.verify(self.callback(self.payment))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("already processed", resp.data["message"])
        provision.assert_not_called()

    def test_replay_of_a_provisioned_payment_still_needs_a_valid_signature(self):
        Payment.objects.filter(pk=self.payment.pk).update(status="PROVISIONED")
        resp = self.verify(self.callback(self.payment, secret="wrong"))
        self.assertEqual(resp.data, GENERIC)

    def test_a_valid_callback_provisions_the_institution(self):
        public_org = Organization.objects.get(schema_name="public")
        with mock.patch(PROVISION, return_value={"domain_url": "http://x", "organization": public_org}) as provision:
            resp = self.verify(self.callback(self.payment))
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        self.assertEqual(resp.data["domain_url"], "http://x")
        provision.assert_called_once()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "PROVISIONED")


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class SignupProvisioningFailureTests(SignupPaymentTestBase):
    SETUP_FAILED = (
        "Your payment was received, but we could not finish setting up your institution. "
        "Please contact support."
    )

    def test_unexpected_failure_leaks_no_detail_and_is_logged(self):
        payment = self.make_payment()
        boom = RuntimeError("secret internal detail: relation \"x\" does not exist")
        with mock.patch(PROVISION, side_effect=boom):
            with self.assertLogs("payments.services", level="ERROR") as captured:
                resp = self.verify(self.callback(payment))
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.data, {"error": self.SETUP_FAILED})
        self.assertNotIn("secret internal detail", json.dumps(resp.data))
        self.assertIn("could not be provisioned", "\n".join(captured.output))

    def test_no_print_output_on_failure(self):
        payment = self.make_payment()
        stdout = io.StringIO()
        with mock.patch(PROVISION, side_effect=RuntimeError("boom")):
            with contextlib.redirect_stdout(stdout), self.assertLogs("payments.services", level="ERROR"):
                self.verify(self.callback(payment))
        self.assertEqual(stdout.getvalue(), "")

    def test_registration_data_that_became_invalid_after_init_is_generic(self):
        payment = self.make_payment()
        get_user_model().objects.create_user(username=payment.username, email="other@f2a.example", password="Whatever123!")
        resp = self.verify(self.callback(payment))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {"error": self.SETUP_FAILED})
        self.assertNotIn("username", json.dumps(resp.data))


class SignupProductionGuardTests(SignupPaymentTestBase):
    @override_settings(ESEWA_CLIENT_SECRET=SECRET, ESEWA_PRODUCT_CODE="EPAYTEST", ESEWA_URL=REAL_URL, **PRODUCTION)
    def test_init_refuses_the_test_merchant_in_production(self):
        resp = self.init()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(Payment.objects.count(), 0)

    @override_settings(ESEWA_CLIENT_SECRET=SECRET, ESEWA_PRODUCT_CODE="LIVECODE",
                       ESEWA_URL="https://rc-epay.esewa.com.np/api/epay/main/v2/form", **PRODUCTION)
    def test_init_refuses_a_test_endpoint_in_production(self):
        resp = self.init()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(Payment.objects.count(), 0)

    @override_settings(ESEWA_CLIENT_SECRET=SECRET, ESEWA_PRODUCT_CODE="LIVECODE", ESEWA_URL=REAL_URL, **PRODUCTION)
    def test_init_accepts_a_real_merchant_configuration_in_production(self):
        resp = self.init()
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        self.assertEqual(resp.data["product_code"], "LIVECODE")

    @override_settings(ESEWA_CLIENT_SECRET=SECRET, ESEWA_PRODUCT_CODE="LIVECODE", ESEWA_URL=REAL_URL)
    def test_verify_refuses_the_test_merchant_in_production(self):
        payment = self.make_payment()
        data = self.callback(payment, product_code="LIVECODE")
        with override_settings(ESEWA_PRODUCT_CODE="EPAYTEST", ESEWA_URL=REAL_URL, **PRODUCTION):
            resp = self.verify(data)
        self.assertEqual(resp.status_code, 503)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "PENDING")


@override_settings(ESEWA_CLIENT_SECRET=SECRET)
class SignupThrottleAndRouteTests(SignupPaymentTestBase):
    def test_throttle_scopes_are_configured(self):
        for scope in ("signup_payment_init", "signup_payment_verify"):
            self.assertIn(scope, ScopedRateThrottle.THROTTLE_RATES)
            self.assertEqual(ScopedRateThrottle.THROTTLE_RATES[scope], "1000/min")  # test-mode override

    def test_init_is_rate_limited(self):
        rates = {**ScopedRateThrottle.THROTTLE_RATES, "signup_payment_init": "3/min"}
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates):
            codes = [self.init(subdomain=f"throttle{i}", username=f"thr{i}").status_code for i in range(5)]
        self.assertEqual(codes[:3], [200, 200, 200])
        self.assertEqual(codes[3:], [429, 429])
        self.assertEqual(Payment.objects.count(), 3)

    def test_verify_is_rate_limited(self):
        rates = {**ScopedRateThrottle.THROTTLE_RATES, "signup_payment_verify": "2/min"}
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates):
            codes = [self.verify("junk").status_code for _ in range(4)]
        self.assertEqual(codes, [400, 400, 429, 429])

    def test_the_unpaid_registration_endpoint_no_longer_exists(self):
        for method in ("post", "get"):
            resp = getattr(APIClient(), method)("/api/auth/register-organization/", self.registration(), format="json")
            self.assertEqual(resp.status_code, 404, method)
        self.assertFalse(Organization.objects.filter(schema_name="f2a_school").exists())
        self.assertEqual(Payment.objects.count(), 0)
