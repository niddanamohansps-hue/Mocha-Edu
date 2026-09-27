from django.db import connection
from django.test import TestCase, TransactionTestCase
from django_tenants.utils import tenant_context

from accounts.utils.crypto import encrypt_secret, decrypt_secret
from organizations.models import Organization, Domain
from .models import AuditLog
from .audit import log_action


class CryptoUtilTest(TestCase):
    def test_round_trip(self):
        token = encrypt_secret("Sup3rSecret!")
        self.assertNotEqual(token, "Sup3rSecret!")
        self.assertEqual(decrypt_secret(token), "Sup3rSecret!")

    def test_legacy_plaintext_falls_back_gracefully(self):
        # Simulates a row written before encryption was introduced (e.g. seeded
        # test data) - must not raise, must return the value unchanged.
        self.assertEqual(decrypt_secret("plain-old-password"), "plain-old-password")

    def test_none_and_empty_are_safe(self):
        self.assertIsNone(encrypt_secret(None))
        self.assertEqual(decrypt_secret(""), "")


class AuditLogTenantIsolationTest(TransactionTestCase):
    def setUp(self):
        connection.set_schema_to_public()
        self.school_a = Organization.objects.create(
            schema_name="audit_school_a", name="Audit School A"
        )
        Domain.objects.create(
            domain="auditA.localhost", tenant=self.school_a, is_primary=True
        )
        self.school_b = Organization.objects.create(
            schema_name="audit_school_b", name="Audit School B"
        )
        Domain.objects.create(
            domain="auditB.localhost", tenant=self.school_b, is_primary=True
        )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school_a.delete(force_drop=True)
        self.school_b.delete(force_drop=True)

    def test_audit_logs_are_isolated_per_tenant(self):
        with tenant_context(self.school_a):
            AuditLog.objects.create(
                actor_username="admin_a", action="role_created", model_name="Role"
            )

        with tenant_context(self.school_b):
            count_in_b = AuditLog.objects.count()
            self.assertEqual(
                count_in_b,
                0,
                "TENANT ISOLATION FAILURE: School B can see School A's audit log entries",
            )

        with tenant_context(self.school_a):
            count_in_a = AuditLog.objects.count()
            self.assertEqual(count_in_a, 1)

    def test_log_action_never_raises_on_failure(self):
        class FakeRequest:
            user = None
            META = {}

        # Passing an object with no real request attributes must not raise -
        # audit logging is best-effort and must never break the caller.
        try:
            log_action(FakeRequest(), action="test_action", model_name="Whatever")
        except Exception as exc:  # pragma: no cover - explicit failure signal
            self.fail(f"log_action raised unexpectedly: {exc}")
