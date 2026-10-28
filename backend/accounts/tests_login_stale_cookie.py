import uuid

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from organizations.models import Domain, Organization
from roles.models import Role, UserRole

from .models import User


class StaleCookieLoginTests(TransactionTestCase):
    """An old access cookie (e.g. for a user deleted by a re-seed) must not block a fresh sign-in."""

    SCHEMA, DOMAIN = "stale_cookie_school", "stale-cookie.localhost"

    def setUp(self):
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Stale Cookie School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.user = User.objects.create_user(username="stale_owner", email="stale@sc.test", password="Pass1234!")
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            UserRole.objects.create(user=self.user, role=role)

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        User.objects.filter(username="stale_owner").delete()

    def test_login_works_with_a_cookie_for_a_user_that_no_longer_exists(self):
        ghost = User(id=uuid.uuid4(), username="ghost")
        client = APIClient()
        client.cookies["access_token"] = str(AccessToken.for_user(ghost))
        response = client.post("/api/auth/login/", {"username": "stale_owner", "password": "Pass1234!"},
                               HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 200, getattr(response, "data", response.content))

    def test_wrong_password_is_still_refused(self):
        response = APIClient().post("/api/auth/login/", {"username": "stale_owner", "password": "wrong"},
                                    HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 401)
