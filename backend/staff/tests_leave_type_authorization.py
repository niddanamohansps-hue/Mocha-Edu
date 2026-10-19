"""Authorization tests for the leave-type endpoints (``/api/staff/leaves/types/``).

Reading needs tenant membership plus one of apply_staff_leave, manage_leave_types,
manage_staff_leaves, view_all_leaves; only manage_leave_types holders see inactive types; PUT is
not supported. ``force_authenticate`` exercises the explicit permission classes (a non-member is
403); a real access-token cookie exercises the membership gate (a non-member is 401).

These tests create tenant schemas and need a disposable PostgreSQL database; they are written to be
run only in an explicitly authorized isolated test stage.
"""

import uuid
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from organizations.models import Domain, Organization
from roles.models import Permission, Role, UserRole
from staff.models import LeaveType

PASSWORD = "Pass1234!"
TYPES = "/api/staff/leaves/types/"


class LeaveTypeAuthorizationTests(TransactionTestCase):
    SCHEMA = "lt_authz_school"
    DOMAIN = "ltauthz.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name=self.SCHEMA):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="ltaz_").delete()

    def _user(self, username, codenames=None, superuser=False, slug=None):
        """codenames=None -> not a member at all; a list (possibly empty) -> member with that role."""
        connection.set_schema_to_public()
        if superuser:
            return User.objects.create_superuser(
                username=username, email=f"{username}@ltaz.test", password=PASSWORD
            )
        user = User.objects.create_user(username=username, email=f"{username}@ltaz.test", password=PASSWORD)
        if codenames is not None or slug:
            with tenant_context(self.school):
                slug = slug or f"ltaz-{uuid.uuid4().hex[:10]}"
                role, _ = Role.objects.get_or_create(
                    slug=slug, defaults={"name": slug, "is_system_role": slug == "owner"}
                )
                if codenames:
                    role.permissions.set(Permission.objects.filter(codename__in=codenames))
                UserRole.objects.create(user=user, role=role)
        return user

    def _as(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _cookie(self, user):
        connection.set_schema_to_public()
        client = APIClient()
        client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        return client

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="LT Authz School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)

        self.owner = self._user("ltaz_owner", slug="owner")
        self.superuser = self._user("ltaz_superuser", superuser=True)
        self.type_manager = self._user("ltaz_type_manager", ["manage_leave_types"])
        self.approver = self._user("ltaz_approver", ["manage_staff_leaves"])
        self.viewer_all = self._user("ltaz_viewer_all", ["view_all_leaves"])
        self.applicant = self._user("ltaz_applicant", ["apply_staff_leave"])
        self.own_viewer = self._user("ltaz_own_viewer", ["view_own_leaves", "cancel_own_leave"])
        self.plain_member = self._user("ltaz_plain_member", [])
        self.student = self._user("ltaz_student", ["view_course_content", "submit_assignment"])
        self.parent = self._user("ltaz_parent", ["view_own_children"])
        self.outsider = self._user("ltaz_outsider")  # no membership in this tenant

        with tenant_context(self.school):
            self.active_type = LeaveType.objects.create(
                name="Casual Leave", code="CL", annual_allocation_days=Decimal("12.0"), is_paid=True
            )
            self.inactive_type = LeaveType.objects.create(
                name="Legacy Leave", code="LG", annual_allocation_days=Decimal("5.0"), is_paid=True, is_active=False
            )

    def _get(self, client, path=TYPES):
        return client.get(path, HTTP_HOST=self.DOMAIN)

    @staticmethod
    def _ids(response):
        data = response.data["results"] if isinstance(response.data, dict) and "results" in response.data else response.data
        return {str(item["id"]) for item in data}

    def test_read_access_by_permission(self):
        active = {str(self.active_type.id)}
        both = active | {str(self.inactive_type.id)}

        # Readers by permission: active types only (they cannot manage types).
        for user in (self.approver, self.viewer_all, self.applicant):
            resp = self._get(self._as(user))
            self.assertEqual(resp.status_code, 200, user.username)
            self.assertEqual(self._ids(resp), active, user.username)

        # Only manage_leave_types (and owner / superuser) also see the inactive type.
        for user in (self.type_manager, self.owner, self.superuser):
            resp = self._get(self._as(user))
            self.assertEqual(resp.status_code, 200, user.username)
            self.assertEqual(self._ids(resp), both, user.username)

        # view_own_leaves / cancel_own_leave do not unlock leave-type reads; neither do unrelated roles.
        for user in (self.own_viewer, self.plain_member, self.student, self.parent, self.outsider):
            self.assertEqual(self._get(self._as(user)).status_code, 403, user.username)

        # Retrieve follows the same rules, including hiding the inactive type from non-managers.
        inactive_detail = f"{TYPES}{self.inactive_type.id}/"
        active_detail = f"{TYPES}{self.active_type.id}/"
        self.assertEqual(self._get(self._as(self.applicant), active_detail).status_code, 200)
        self.assertEqual(self._get(self._as(self.applicant), inactive_detail).status_code, 404)
        self.assertEqual(self._get(self._as(self.type_manager), inactive_detail).status_code, 200)
        self.assertEqual(self._get(self._as(self.student), active_detail).status_code, 403)
        self.assertEqual(self._get(self._as(self.outsider), active_detail).status_code, 403)

    def test_mutations_and_unsupported_put(self):
        payload = {"name": "Study Leave", "code": "ST", "annual_allocation_days": "6.0", "is_paid": True}

        # Create / edit / delete need manage_leave_types.
        for user in (self.approver, self.viewer_all, self.applicant, self.own_viewer, self.student, self.outsider):
            client = self._as(user)
            self.assertEqual(client.post(TYPES, payload, format="json", HTTP_HOST=self.DOMAIN).status_code, 403, user.username)
            self.assertEqual(
                client.patch(f"{TYPES}{self.active_type.id}/", {"description": "x"}, format="json", HTTP_HOST=self.DOMAIN).status_code,
                403, user.username,
            )
            self.assertEqual(client.delete(f"{TYPES}{self.active_type.id}/", HTTP_HOST=self.DOMAIN).status_code, 403, user.username)

        manager = self._as(self.type_manager)
        resp = manager.post(TYPES, payload, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 201, resp.data)
        created_id = resp.data["id"]
        resp = manager.patch(f"{TYPES}{created_id}/", {"description": "Policy"}, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["description"], "Policy")
        self.assertEqual(manager.delete(f"{TYPES}{created_id}/", HTTP_HOST=self.DOMAIN).status_code, 204)

        # PUT is not supported for anyone, even the owner and a superuser.
        full_update = {"name": "Casual Leave", "code": "CL", "annual_allocation_days": "12.0", "is_paid": True}
        for user in (self.type_manager, self.owner, self.superuser):
            resp = self._as(user).put(f"{TYPES}{self.active_type.id}/", full_update, format="json", HTTP_HOST=self.DOMAIN)
            self.assertEqual(resp.status_code, 405, user.username)

    def test_cookie_gate_rejects_non_members(self):
        # A real cookie: the non-member is anonymous (401), a permitted member still reads.
        self.assertEqual(self._get(self._cookie(self.outsider)).status_code, 401)
        self.assertEqual(self._get(self._cookie(self.applicant)).status_code, 200)
        self.assertEqual(self._get(self._cookie(self.superuser)).status_code, 200)
