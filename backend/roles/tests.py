from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Organization, Domain
from core.models import AuditLog
from .models import Role, UserRole


class RoleAuditLogTest(TransactionTestCase):
    """
    Verifies that creating/updating/deleting a Role produces an AuditLog
    entry in the tenant's own schema (Phase 0 + AuditLog milestone).
    """

    def setUp(self):
        connection.set_schema_to_public()
        self.school = Organization.objects.create(
            schema_name="role_audit_school", name="Role Audit School"
        )
        Domain.objects.create(
            domain="roleaudit.localhost", tenant=self.school, is_primary=True
        )
        self.password = "OwnerPass123!"
        self.user = User.objects.create_user(
            username="roleaudit_owner", email="owner@roleaudit.com", password=self.password
        )
        with tenant_context(self.school):
            owner_role, _ = Role.objects.get_or_create(
                slug="owner", defaults={"name": "Owner", "is_system_role": True}
            )
            UserRole.objects.create(user=self.user, role=owner_role)

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)

    def _login(self):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/",
            {"username": "roleaudit_owner", "password": self.password},
            HTTP_HOST="roleaudit.localhost",
        )
        self.assertEqual(resp.status_code, 200)
        return client

    def test_role_create_update_delete_are_audited(self):
        client = self._login()

        create_resp = client.post(
            "/api/roles/",
            {"name": "Homeroom Teacher", "permissions": []},
            HTTP_HOST="roleaudit.localhost",
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
        role_id = create_resp.data["id"]

        update_resp = client.patch(
            f"/api/roles/{role_id}/",
            {"name": "Homeroom Teacher (Updated)"},
            HTTP_HOST="roleaudit.localhost",
            content_type="application/json",
        )
        self.assertEqual(update_resp.status_code, 200, update_resp.data)

        delete_resp = client.delete(
            f"/api/roles/{role_id}/", HTTP_HOST="roleaudit.localhost"
        )
        self.assertEqual(delete_resp.status_code, 204)

        with tenant_context(self.school):
            actions = list(
                AuditLog.objects.filter(model_name="Role").values_list(
                    "action", flat=True
                )
            )
        self.assertIn("role_created", actions)
        self.assertIn("role_updated", actions)
        self.assertIn("role_deleted", actions)
