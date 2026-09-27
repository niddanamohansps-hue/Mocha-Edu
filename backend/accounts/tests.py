from django.test import TransactionTestCase
from django.core.management import call_command
from django.contrib.auth import authenticate
from django.db import connection
from io import StringIO
import uuid
from accounts.models import User
from organizations.models import Organization, Domain
from profiles.models import Profile
from django_tenants.utils import tenant_context
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
