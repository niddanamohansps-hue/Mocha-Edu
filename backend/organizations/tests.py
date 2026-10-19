from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import User
from accounts.serializers import OrganizationRegisterSerializer
from organizations.models import Domain, Organization

CHECK_URL = "/api/organizations/check-domain/"


class OrganizationDomainTests(TransactionTestCase):
    """
    Tenant lookup and registration validation. No new tenant schema is created here:
    Domain rows attach to the existing public organization, and registration
    validation rejects duplicates before any tenant provisioning runs.
    """

    def setUp(self):
        connection.set_schema_to_public()
        self.public_org, _ = Organization.objects.get_or_create(
            schema_name="public", defaults={"name": "Public Schema"}
        )
        self.addCleanup(self._cleanup)
        Domain.objects.get_or_create(domain="testserver", tenant=self.public_org, defaults={"is_primary": True})
        Domain.objects.create(domain="orgp04.localhost", tenant=self.public_org)
        User.objects.create_user(username="org_taken", email="taken@p04.test", password="Pass1234!")

    def _cleanup(self):
        connection.set_schema_to_public()
        Domain.objects.filter(domain__in=["orgp04.localhost"]).delete()
        User.objects.filter(username__in=["org_taken", "org_new"]).delete()

    def _check(self, **params):
        return APIClient().get(CHECK_URL, params, HTTP_HOST="testserver")

    # --- check-domain: lookup behavior --------------------------------------

    def test_missing_domain_parameter_is_rejected(self):
        resp = self._check()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.data)

    def test_full_hostname_is_found(self):
        resp = self._check(domain="orgp04.localhost")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["exists"])

    def test_bare_subdomain_is_found_via_localhost_suffix(self):
        resp = self._check(domain="orgp04")
        self.assertTrue(resp.data["exists"])

    def test_lookup_is_case_insensitive(self):
        resp = self._check(domain="ORGP04.LOCALHOST")
        self.assertTrue(resp.data["exists"])

    def test_unknown_domain_is_not_found(self):
        resp = self._check(domain="no-such-school-p04")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["exists"])

    def test_check_domain_is_public_and_needs_no_login(self):
        resp = APIClient().get(CHECK_URL, {"domain": "orgp04"}, HTTP_HOST="testserver")
        self.assertEqual(resp.status_code, 200)

    # --- Domain integrity ------------------------------------------------------

    def test_a_hostname_cannot_map_to_two_tenants(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Domain.objects.create(domain="orgp04.localhost", tenant=self.public_org)

    # --- Registration validation (rejected before any tenant is created) -------

    def _register_payload(self, **overrides):
        payload = {
            "organization_name": "P04 Registry School",
            "subdomain": "org-new-p04",
            "username": "org_new",
            "email": "org_new@p04.test",
            "password": "Pass1234!",
        }
        payload.update(overrides)
        return payload

    def test_registration_rejects_existing_subdomain(self):
        serializer = OrganizationRegisterSerializer(data=self._register_payload(subdomain="public"))
        self.assertFalse(serializer.is_valid())
        self.assertIn("subdomain", serializer.errors)

    def test_registration_rejects_taken_username(self):
        serializer = OrganizationRegisterSerializer(data=self._register_payload(username="org_taken"))
        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)

    def test_registration_rejects_short_password(self):
        serializer = OrganizationRegisterSerializer(data=self._register_payload(password="short"))
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_public_schema_returns_404_for_tenant_only_endpoints(self):
        # 1. Anonymous on public host
        client = APIClient()
        resp = client.get("/api/students/", HTTP_HOST="testserver")
        self.assertEqual(resp.status_code, 404)

        # 2. Regular user on public host
        user = User.objects.get(username="org_taken")
        client.force_authenticate(user=user)
        resp = client.get("/api/students/", HTTP_HOST="testserver")
        self.assertEqual(resp.status_code, 404)
        resp = client.get("/api/academics/programs/", HTTP_HOST="testserver")
        self.assertEqual(resp.status_code, 404)
        resp = client.get("/api/notifications/", HTTP_HOST="testserver")
        self.assertEqual(resp.status_code, 404)

        # 3. Superuser on public host must also get 404 instead of unhandled 500
        super_user = User.objects.create_superuser(
            username="org_super", email="super@p04.test", password="SuperPassword123!"
        )
        try:
            client.force_authenticate(user=super_user)
            resp = client.get("/api/students/", HTTP_HOST="testserver")
            self.assertEqual(resp.status_code, 404)
            resp = client.get("/api/academics/programs/", HTTP_HOST="testserver")
            self.assertEqual(resp.status_code, 404)
            resp = client.get("/api/staff/", HTTP_HOST="testserver")
            self.assertEqual(resp.status_code, 404)
        finally:
            super_user.delete()

    def test_public_schema_allows_public_endpoints(self):
        client = APIClient()
        # Check domain is accessible on public host
        resp = client.get(CHECK_URL, {"domain": "orgp04"}, HTTP_HOST="testserver")
        self.assertEqual(resp.status_code, 200)

        # Auth login is accessible on public host (POST with empty body returns 400 validation error, not 404)
        resp = client.post("/api/auth/login/", {}, HTTP_HOST="testserver")
        self.assertEqual(resp.status_code, 400)

        # Payments verify is accessible on public host (returns 400 for missing data parameter, not 404)
        resp = client.get("/api/payments/verify/", HTTP_HOST="testserver")
        self.assertEqual(resp.status_code, 400)
