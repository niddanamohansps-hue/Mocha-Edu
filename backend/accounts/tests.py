from django.test import TransactionTestCase, override_settings
from django.core.cache import cache
from django.core.management import call_command
from django.core import mail
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import connection
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from io import StringIO
import logging
import uuid
from accounts.models import User
from core.models import AuditLog
from organizations.models import Organization, Domain
from profiles.models import Profile
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
import uuid


class EduSekaiIdentityJanitorTest(TransactionTestCase):
    """
    The EduSekai Janitor Suite: Advanced identity integrity testing.
    Verifies that User Identity is managed correctly across the entire
    Multi-Tenant cluster.
    """

    def setUp(self):
        # Reset Connection
        connection.set_schema_to_public()

        # 1. Create a Primary Cluster (School A)
        self.school_a = Organization.objects.create(
            schema_name="school_a", name="St. Marys Academy"
        )
        Domain.objects.create(
            domain="marys.localhost", tenant=self.school_a, is_primary=True
        )

        # 2. Create a Secondary Cluster (School B)
        self.school_b = Organization.objects.create(
            schema_name="school_b", name="Oxford University"
        )
        Domain.objects.create(
            domain="oxford.localhost", tenant=self.school_b, is_primary=True
        )

        # 3. Create a Global Identity
        self.identity_username = "prof.jones"
        self.identity_password = "password123"
        self.user = User.objects.create_user(
            username=self.identity_username,
            email="jones@edu.com",
            password=self.identity_password,
        )

    def test_global_user_purge_cascade(self):
        """
        Scenario: A user is deleted from the platform.
        Expectation: All institutional records (Profiles) are wiped from ALL schemas.
        This is critical for GDRP and data minimization.
        """
        # STEP 1: Enroll in both institutions
        with tenant_context(self.school_a):
            Profile.objects.create(
                user_id=self.user.id, first_name="Indiana", last_name="Jones"
            )

        with tenant_context(self.school_b):
            Profile.objects.create(
                user_id=self.user.id, first_name="Indy", last_name="Jones"
            )

        # STEP 2: Ensure we are in Public Context for the delete
        connection.set_schema_to_public()
        self.user.delete()

        # STEP 3: Verify the Cleanup
        for school in [self.school_a, self.school_b]:
            with tenant_context(school):
                count = Profile.objects.filter(user_id=self.user.id).count()
                self.assertEqual(
                    count,
                    0,
                    f"DATA LEAK DETECTED: Profile for {self.identity_username} still exists in {school.name} ({school.schema_name})",
                )

    def test_tenant_login_isolation(self):
        """
        Scenario: A student attempts to login at a specific school subdomain.
        Expectation: They should only be able to login if they have a 'local_username'
        mapping in that specific school.
        """
        # STEP 1: Set up a local identity for School A ONLY
        with tenant_context(self.school_a):
            Profile.objects.create(
                user_id=self.user.id, first_name="Jonesy", local_username="jonesy_local"
            )

        # STEP 2: Attempt Login at School A Subdomain
        connection.set_schema(self.school_a.schema_name)
        login_a = authenticate(username="jonesy_local", password=self.identity_password)
        self.assertIsNotNone(
            login_a, "Institutional login failed for valid local_username"
        )

        # STEP 3: Attempt same Local Login at School B (where they don't exist locally)
        connection.set_schema(self.school_b.schema_name)
        login_b = authenticate(username="jonesy_local", password=self.identity_password)
        self.assertIsNone(
            login_b, "SECURITY FLAW: Local username leaked across schools"
        )

        # STEP 4: Global login should still work if enabled, but let's test isolation
        login_global = authenticate(
            username=self.identity_username, password=self.identity_password
        )
        self.assertIsNotNone(login_global, "Global identifier login failed")

    def test_janitor_audit_discovery(self):
        """
        Scenario: Orphaned data exists (profiles with dead user links).
        Expectation: The audit tools find and report them correctly.
        """
        # Create an 'Orphan' manually by using a fake UUID
        broken_link = uuid.uuid4()
        with tenant_context(self.school_b):
            Profile.objects.create(
                user_id=broken_link, first_name="Orphan", last_name="Data"
            )

        # Run the 'Orphan' janitor
        out = StringIO()
        call_command("audit_orphans", stdout=out)

        report = out.getvalue()
        self.assertIn("Oxford University", report)
        self.assertIn("1 dead links DETECTED", report)

    def tearDown(self):
        connection.set_schema_to_public()
        self.school_a.delete(force_drop=True)
        self.school_b.delete(force_drop=True)


class SecurityFixesTest(TransactionTestCase):
    """
    Phase 0 security-fix verification: JWT blacklist on logout, and real
    password-strength validation on change-password.
    """

    def setUp(self):
        connection.set_schema_to_public()
        self.school = Organization.objects.create(
            schema_name="sec_test_school", name="Security Test School"
        )
        Domain.objects.create(
            domain="sectest.localhost", tenant=self.school, is_primary=True
        )
        self.password = "S3curePass!2024"
        self.user = User.objects.create_user(
            username="sectestuser", email="sec@sectest.com", password=self.password
        )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)

    def test_logout_blacklists_refresh_token(self):
        from rest_framework.test import APIClient

        client = APIClient()
        login_resp = client.post(
            "/api/auth/login/",
            {"username": "sectestuser", "password": self.password},
            HTTP_HOST="sectest.localhost",
        )
        self.assertEqual(login_resp.status_code, 200)
        refresh_cookie_value = client.cookies["refresh_token"].value

        # Refresh works fine before logout.
        refresh_resp = client.post("/api/auth/refresh/", HTTP_HOST="sectest.localhost")
        self.assertEqual(refresh_resp.status_code, 200)

        logout_resp = client.post("/api/auth/logout/", HTTP_HOST="sectest.localhost")
        self.assertEqual(logout_resp.status_code, 200)

        # Re-attach the (now blacklisted) refresh token and confirm it no longer works.
        stale_client = APIClient()
        stale_client.cookies["refresh_token"] = refresh_cookie_value
        stale_refresh_resp = stale_client.post(
            "/api/auth/refresh/", HTTP_HOST="sectest.localhost"
        )
        self.assertEqual(
            stale_refresh_resp.status_code,
            401,
            "SECURITY REGRESSION: refresh token remained valid after logout",
        )

    def test_change_password_rejects_common_password(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.post(
            "/api/auth/login/",
            {"username": "sectestuser", "password": self.password},
            HTTP_HOST="sectest.localhost",
        )

        weak_resp = client.post(
            "/api/auth/change-password/",
            {"new_password": "password"},
            HTTP_HOST="sectest.localhost",
        )
        self.assertEqual(weak_resp.status_code, 400)
        self.assertIn("error", weak_resp.data)

    def test_change_password_accepts_strong_password(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.post(
            "/api/auth/login/",
            {"username": "sectestuser", "password": self.password},
            HTTP_HOST="sectest.localhost",
        )

        strong_resp = client.post(
            "/api/auth/change-password/",
            {"new_password": "Tr0ub4dor&3xtra"},
            HTTP_HOST="sectest.localhost",
        )
        self.assertEqual(strong_resp.status_code, 200)

        self.user.refresh_from_db()
        self.assertFalse(self.user.needs_password_change)
        self.assertIsNone(self.user.initial_password_display)


class SecurityHardeningTest(TransactionTestCase):
    """
    Task B security hardening verification: JWT cookie `secure` flag is
    environment-configurable (not hardcoded), and authentication-sensitive
    endpoints are scoped-throttled against brute-force/enumeration abuse.
    """

    def setUp(self):
        connection.set_schema_to_public()
        # The scoped throttles share Django's default (in-process) cache
        # across the whole test run, so each test starts from a clean
        # counter instead of inheriting hits from earlier tests.
        cache.clear()
        self.school = Organization.objects.create(
            schema_name="hardening_test_school", name="Hardening Test School"
        )
        Domain.objects.create(
            domain="hardening.localhost", tenant=self.school, is_primary=True
        )
        self.password = "S3curePass!2024"
        self.user = User.objects.create_user(
            username="hardeninguser",
            email="hardening@sectest.com",
            password=self.password,
        )

    def tearDown(self):
        cache.clear()
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)

    @override_settings(COOKIE_SECURE=True)
    def test_jwt_cookies_are_secure_when_cookie_secure_enabled(self):
        from rest_framework.test import APIClient

        client = APIClient()
        resp = client.post(
            "/api/auth/login/",
            {"username": "hardeninguser", "password": self.password},
            HTTP_HOST="hardening.localhost",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Secure", str(resp.cookies["access_token"]))
        self.assertIn("Secure", str(resp.cookies["refresh_token"]))

    @override_settings(COOKIE_SECURE=False)
    def test_jwt_cookies_are_not_secure_when_cookie_secure_disabled(self):
        from rest_framework.test import APIClient

        client = APIClient()
        resp = client.post(
            "/api/auth/login/",
            {"username": "hardeninguser", "password": self.password},
            HTTP_HOST="hardening.localhost",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Secure", str(resp.cookies["access_token"]))
        self.assertNotIn("Secure", str(resp.cookies["refresh_token"]))

    def test_login_endpoint_is_throttled(self):
        from rest_framework.test import APIClient
        from rest_framework.throttling import SimpleRateThrottle

        # config/settings.py deliberately raises the ambient "login" rate
        # while `manage.py test` is running, so that the many incidental
        # logins other apps' tests perform don't trip the real production
        # ceiling (see the comment there). DRF binds
        # SimpleRateThrottle.THROTTLE_RATES once, at import time, from
        # REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] - a plain
        # @override_settings(REST_FRAMEWORK=...) replaces that setting
        # with a new dict and would never reach the already-bound class
        # attribute. Patch THROTTLE_RATES directly instead, so this test
        # genuinely exercises the real production "5/min" threshold.
        original_rate = SimpleRateThrottle.THROTTLE_RATES["login"]
        SimpleRateThrottle.THROTTLE_RATES["login"] = "5/min"
        try:
            client = APIClient()
            last_status = None
            for _ in range(6):  # real production rate is 5/min
                resp = client.post(
                    "/api/auth/login/",
                    {"username": "hardeninguser", "password": "wrong-password"},
                    HTTP_HOST="hardening.localhost",
                )
                last_status = resp.status_code
            self.assertEqual(
                last_status,
                429,
                "Login endpoint did not throttle at the real production rate (5/min)",
            )
        finally:
            SimpleRateThrottle.THROTTLE_RATES["login"] = original_rate

    def test_verify_account_endpoint_is_throttled(self):
        from rest_framework.test import APIClient

        client = APIClient()
        last_status = None
        for _ in range(6):  # configured rate is 5/min
            resp = client.post(
                "/api/auth/verify-account/",
                {"email": "hardening@sectest.com", "password": "wrong-password"},
                HTTP_HOST="hardening.localhost",
            )
            last_status = resp.status_code
        self.assertEqual(
            last_status,
            429,
            "verify-account endpoint did not throttle after exceeding the configured rate",
        )

    def test_refresh_endpoint_is_throttled(self):
        from rest_framework.test import APIClient

        client = APIClient()
        last_status = None
        for _ in range(11):  # configured rate is 10/min
            resp = client.post("/api/auth/refresh/", HTTP_HOST="hardening.localhost")
            last_status = resp.status_code
        self.assertEqual(
            last_status,
            429,
            "Refresh endpoint did not throttle after exceeding the configured rate",
        )

    def test_register_organization_endpoint_is_throttled(self):
        from rest_framework.test import APIClient

        client = APIClient()
        last_status = None
        for _ in range(4):  # configured rate is 3/hour
            resp = client.post(
                "/api/auth/register-organization/",
                {},
                HTTP_HOST="hardening.localhost",
            )
            last_status = resp.status_code
        self.assertEqual(
            last_status,
            429,
            "Register-organization endpoint did not throttle after exceeding the configured rate",
        )


class PasswordResetFlowTest(TransactionTestCase):
    """
    Focused tests for POST /api/auth/forgot-password/ and
    POST /api/auth/reset-password-confirm/. Mirrors the tenant+cache
    setup already used by SecurityHardeningTest above.
    """

    DOMAIN = "pwreset.localhost"

    def setUp(self):
        connection.set_schema_to_public()
        cache.clear()
        mail.outbox = []
        self.school = Organization.objects.create(
            schema_name="pwreset_test_school", name="Password Reset Test School"
        )
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.password = "OldPass!2024"
        self.user = User.objects.create_user(
            username="pwresetuser",
            email="pwreset.user@example.com",
            password=self.password,
        )

    def tearDown(self):
        cache.clear()
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)

    def _request_reset(self, email="pwreset.user@example.com"):
        client = APIClient()
        return client.post(
            "/api/auth/forgot-password/", {"email": email}, HTTP_HOST=self.DOMAIN
        )

    def _extract_uid_and_token(self):
        """Pulls uid/token out of the real emailed reset link (not re-derived)."""
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        url_line = next(line for line in body.splitlines() if "/reset-password?" in line)
        query = url_line.split("?", 1)[1]
        params = dict(pair.split("=") for pair in query.split("&"))
        return params["uid"], params["token"]

    def _confirm_reset(self, uid, token, new_password="NewSecurePass!2025"):
        client = APIClient()
        return client.post(
            "/api/auth/reset-password-confirm/",
            {"uid": uid, "token": token, "new_password": new_password},
            HTTP_HOST=self.DOMAIN,
        )

    # ---- FORGOT PASSWORD ----

    def test_existing_email_returns_generic_response(self):
        resp = self._request_reset()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data["message"],
            "If an account with that email exists, a reset link has been sent.",
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_nonexistent_and_existing_email_responses_are_indistinguishable(self):
        existing_resp = self._request_reset(email="pwreset.user@example.com")
        cache.clear()  # isolate from the throttle counter, not from enumeration behavior
        nonexistent_resp = self._request_reset(email="nobody-here@example.com")

        self.assertEqual(existing_resp.status_code, nonexistent_resp.status_code)
        self.assertEqual(set(existing_resp.data.keys()), set(nonexistent_resp.data.keys()))
        self.assertEqual(existing_resp.data["message"], nonexistent_resp.data["message"])
        # Only the real account actually gets an email - but that's a
        # server-side side effect, never reflected in the HTTP response.
        self.assertEqual(len(mail.outbox), 1)

    def test_email_lookup_normalizes_domain_case_like_signup_does(self):
        """
        UserManager.create_user() calls self.normalize_email(), which
        lowercases only the domain part (Django's documented behavior,
        not full case-folding). A user signed up with a mixed-case domain
        must still be found when requesting a reset with the lowercase
        form - otherwise lookup normalization would be inconsistent with
        what was actually stored at signup.
        """
        User.objects.create_user(
            username="domaincaseuser",
            email="someone@EXAMPLE-DOMAIN.com",
            password="Pass1234!",
        )
        # Stored value is normalized to a lowercase domain at signup
        # ("someone@example-domain.com"); requesting with the ORIGINAL
        # mixed-case domain must still resolve to that same stored row.
        resp = self._request_reset(email="someone@EXAMPLE-DOMAIN.com")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["someone@example-domain.com"])

    def test_forgot_password_is_throttled(self):
        last_status = None
        for _ in range(6):  # configured rate is 5/hour
            resp = self._request_reset(email="nobody-here@example.com")
            last_status = resp.status_code
        self.assertEqual(last_status, 429)

    def test_reset_token_is_stateless_and_not_persisted(self):
        """
        Django's PasswordResetTokenGenerator is deterministic/stateless - it
        recomputes an HMAC from the user's pk/password-hash/last_login/a
        timestamp each time, rather than generating-and-storing a random
        value. Calling it twice for the same unchanged user state produces
        the identical token, which would NOT be true if a token were being
        randomly generated and persisted somewhere.
        """
        generator = PasswordResetTokenGenerator()
        token_1 = generator.make_token(self.user)
        token_2 = generator.make_token(self.user)
        self.assertEqual(token_1, token_2)
        # No custom token model exists in this project to assert empty -
        # confirmed by inspecting accounts/models.py; this test documents
        # *why* that's safe rather than asserting an absence.

    # ---- RESET PASSWORD ----

    def test_valid_token_resets_password_and_new_password_works(self):
        self._request_reset()
        uid, token = self._extract_uid_and_token()
        resp = self._confirm_reset(uid, token, new_password="NewSecurePass!2025")
        self.assertEqual(resp.status_code, 200)

        login_client = APIClient()
        login_resp = login_client.post(
            "/api/auth/login/",
            {"username": "pwresetuser", "password": "NewSecurePass!2025"},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(login_resp.status_code, 200)

    def test_weak_password_is_rejected_by_django_validators(self):
        self._request_reset()
        uid, token = self._extract_uid_and_token()
        resp = self._confirm_reset(uid, token, new_password="password")
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password), "Weak password must not have been applied")

    def test_invalid_token_is_rejected(self):
        resp = self._confirm_reset(
            urlsafe_base64_encode(force_bytes(self.user.pk)), "garbage-token-value"
        )
        self.assertEqual(resp.status_code, 400)

    def test_expired_token_is_rejected(self):
        self._request_reset()
        uid, token = self._extract_uid_and_token()
        # PASSWORD_RESET_TIMEOUT=-1 means "expired the instant it's checked" -
        # the standard way to deterministically test Django token expiry
        # without manipulating the clock.
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            resp = self._confirm_reset(uid, token)
        self.assertEqual(resp.status_code, 400)

    def test_token_cannot_be_reused_after_successful_reset(self):
        self._request_reset()
        uid, token = self._extract_uid_and_token()

        first = self._confirm_reset(uid, token, new_password="NewSecurePass!2025")
        self.assertEqual(first.status_code, 200)

        second = self._confirm_reset(uid, token, new_password="AnotherPass!2026")
        self.assertEqual(
            second.status_code,
            400,
            "SECURITY REGRESSION: reset token was accepted a second time",
        )

    def test_malformed_uid_is_rejected_safely(self):
        resp = self._confirm_reset("not-valid-base64!!!", "sometoken")
        self.assertEqual(resp.status_code, 400)

    def test_nonexistent_uid_is_rejected_safely(self):
        fake_uid = urlsafe_base64_encode(force_bytes(uuid.uuid4()))
        resp = self._confirm_reset(fake_uid, "sometoken")
        self.assertEqual(resp.status_code, 400)

    def test_disabled_account_cannot_complete_reset(self):
        self._request_reset()
        uid, token = self._extract_uid_and_token()

        self.user.is_active = False
        self.user.save()

        resp = self._confirm_reset(uid, token)
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password(self.password),
            "Disabled account's password must not have been changed",
        )

    def test_successful_reset_blacklists_existing_refresh_tokens(self):
        login_client = APIClient()
        login_resp = login_client.post(
            "/api/auth/login/",
            {"username": "pwresetuser", "password": self.password},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(login_resp.status_code, 200)
        old_refresh_cookie = login_client.cookies["refresh_token"].value
        self.assertEqual(OutstandingToken.objects.filter(user=self.user).count(), 1)

        self._request_reset()
        uid, token = self._extract_uid_and_token()
        reset_resp = self._confirm_reset(uid, token, new_password="NewSecurePass!2025")
        self.assertEqual(reset_resp.status_code, 200)

        stale_client = APIClient()
        stale_client.cookies["refresh_token"] = old_refresh_cookie
        refresh_resp = stale_client.post("/api/auth/refresh/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(
            refresh_resp.status_code,
            401,
            "SECURITY REGRESSION: pre-reset refresh token still works after password reset",
        )

    def test_no_secrets_appear_in_audit_log(self):
        self._request_reset()
        uid, token = self._extract_uid_and_token()
        self._confirm_reset(uid, token, new_password="NewSecurePass!2025")

        with tenant_context(self.school):
            logs = list(AuditLog.objects.filter(model_name="User", object_id=str(self.user.id)))
        self.assertTrue(len(logs) >= 2)  # requested + completed
        for entry in logs:
            serialized = f"{entry.action} {entry.changes} {entry.object_id}"
            self.assertNotIn(token, serialized)
            self.assertNotIn("NewSecurePass!2025", serialized)
            self.assertNotIn(self.password, serialized)

    # ---- EMAIL ----

    def test_reset_email_sent_via_existing_email_infrastructure(self):
        self._request_reset()
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["pwreset.user@example.com"])
        self.assertEqual(sent.subject, "Reset your EDU Sekai password")
        self.assertIn("/reset-password?uid=", sent.body)
        self.assertIn("expires in", sent.body)
        self.assertNotIn(self.password, sent.body)

    @override_settings(PASSWORD_RESET_FRONTEND_PROTOCOL="https", PASSWORD_RESET_FRONTEND_PORT="")
    def test_reset_url_uses_configured_protocol_and_port_not_hardcoded(self):
        self._request_reset()
        body = mail.outbox[0].body
        self.assertIn(f"https://{self.DOMAIN}/reset-password?", body)
        self.assertNotIn("http://", body)
        self.assertNotIn(":3555", body)

    # ---- SECURITY ----

    def test_raw_token_never_written_to_logs(self):
        with self.assertLogs(level="DEBUG") as captured:
            logging.getLogger(__name__).debug("marker-to-guarantee-at-least-one-record")
            self._request_reset()
            uid, token = self._extract_uid_and_token()
            self._confirm_reset(uid, token, new_password="NewSecurePass!2025")

        for record in captured.records:
            self.assertNotIn(token, record.getMessage())

    def test_reset_password_confirm_endpoint_is_throttled(self):
        last_status = None
        for _ in range(11):  # configured rate is 10/min
            resp = self._confirm_reset(
                urlsafe_base64_encode(force_bytes(self.user.pk)), "garbage"
            )
            last_status = resp.status_code
        self.assertEqual(last_status, 429)
