"""Tenant-membership enforcement: the membership rule, the cookie-auth gate, the explicit
permission classes and the default-permission policy.

Two kinds of request are used on purpose:
- cookie-authenticated requests (a real ``access_token`` cookie) run ``JWTCookieAuthentication`` and
  therefore the membership gate (a non-member is anonymous -> 401);
- ``force_authenticate`` bypasses authentication, so it is only used where the *explicit*
  permission classes are under test (a non-member is authenticated but forbidden -> 403).

These tests need a disposable PostgreSQL database (they create tenant schemas). They are written to
be run only in an explicitly authorized isolated test stage.
"""

import uuid

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase
from django.urls import URLResolver, get_resolver
from django_tenants.utils import tenant_context
from rest_framework.request import Request
from rest_framework.routers import APIRootView
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.tenant_access import HasAnyPermission, IsTenantMember, is_tenant_member
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole

PASSWORD = "Pass1234!"


class TenantAccessFixtureMixin:
    SCHEMA_A = "tacc_school_a"
    DOMAIN_A = "tacc-a.localhost"
    SCHEMA_B = "tacc_school_b"
    DOMAIN_B = "tacc-b.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA_A, self.SCHEMA_B]):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="tacc_").delete()

    def _build_school(self, schema_name, domain, name):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _make_user(self, username, is_superuser=False):
        connection.set_schema_to_public()
        if is_superuser:
            return User.objects.create_superuser(
                username=username, email=f"{username}@tacc.test", password=PASSWORD
            )
        return User.objects.create_user(
            username=username, email=f"{username}@tacc.test", password=PASSWORD
        )

    def _give_role(self, school, user, codenames=(), slug=None):
        with tenant_context(school):
            slug = slug or f"tacc-{uuid.uuid4().hex[:10]}"
            role, _ = Role.objects.get_or_create(
                slug=slug, defaults={"name": slug, "is_system_role": slug == "owner"}
            )
            if codenames:
                role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.create(user=user, role=role)

    def _cookie_client(self, user):
        connection.set_schema_to_public()
        client = APIClient()
        client.cookies["access_token"] = str(RefreshToken.for_user(user).access_token)
        return client

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school_a = self._build_school(self.SCHEMA_A, self.DOMAIN_A, "Tenant Access A")
        self.school_b = self._build_school(self.SCHEMA_B, self.DOMAIN_B, "Tenant Access B")

        # Members of A, each by a different route.
        self.role_member = self._make_user("tacc_role_member")
        self._give_role(self.school_a, self.role_member, codenames=["add_role"])  # signal creates the Profile
        self.owner = self._make_user("tacc_owner")
        self._give_role(self.school_a, self.owner, slug="owner")
        self.profile_only = self._make_user("tacc_profile_only")
        with tenant_context(self.school_a):
            Profile.objects.create(user_id=self.profile_only.id, first_name="Pro", last_name="File")
        self.role_only = self._make_user("tacc_role_only")
        self._give_role(self.school_a, self.role_only)
        with tenant_context(self.school_a):
            Profile.objects.filter(user_id=self.role_only.id).delete()  # leave only the UserRole
        self.superuser = self._make_user("tacc_superuser", is_superuser=True)

        # Not members of A.
        self.member_of_b = self._make_user("tacc_member_b")
        self._give_role(self.school_b, self.member_of_b)
        self.nobody = self._make_user("tacc_nobody")

        self.members_of_a = [self.role_member, self.owner, self.profile_only, self.role_only, self.superuser]
        self.non_members_of_a = [self.member_of_b, self.nobody]


class MembershipRuleTests(TenantAccessFixtureMixin, TransactionTestCase):
    def test_membership_rule_and_its_equivalence_with_the_login_backend(self):
        with tenant_context(self.school_a):
            for user in self.members_of_a:
                self.assertTrue(is_tenant_member(user), user.username)
            for user in self.non_members_of_a:
                self.assertFalse(is_tenant_member(user), user.username)
            self.assertFalse(is_tenant_member(None))
            self.assertFalse(is_tenant_member(AnonymousUser()))

            # The gate must use exactly the rule that TenantUsernameBackend applies at login.
            for user in self.members_of_a + self.non_members_of_a:
                logs_in = authenticate(username=user.username, password=PASSWORD) is not None
                self.assertEqual(logs_in, is_tenant_member(user), f"login/gate mismatch for {user.username}")

    def test_permission_classes_for_members_and_non_members(self):
        factory = APIRequestFactory()

        def request_for(user, tenant):
            request = Request(factory.get("/"))
            request.user = user
            request.tenant = tenant
            return request

        with tenant_context(self.school_a):
            permission = IsTenantMember()
            for user in self.members_of_a:
                self.assertTrue(permission.has_permission(request_for(user, self.school_a), None), user.username)
            for user in self.non_members_of_a:
                self.assertFalse(permission.has_permission(request_for(user, self.school_a), None), user.username)
            self.assertFalse(permission.has_permission(request_for(AnonymousUser(), self.school_a), None))

            any_of = HasAnyPermission("view_role", "add_role")
            self.assertIs(any_of(), any_of)  # usable inside permission_classes / get_permissions
            self.assertTrue(any_of.has_permission(request_for(self.role_member, self.school_a), None))  # has add_role
            self.assertTrue(any_of.has_permission(request_for(self.owner, self.school_a), None))  # owner
            self.assertFalse(any_of.has_permission(request_for(self.role_only, self.school_a), None))  # no codename
            self.assertFalse(any_of.has_permission(request_for(self.nobody, self.school_a), None))  # not a member
            self.assertFalse(HasAnyPermission().has_permission(request_for(self.owner, self.school_a), None))


class CookieGateTests(TenantAccessFixtureMixin, TransactionTestCase):
    def test_non_members_are_unauthenticated_and_members_are_accepted(self):
        for user in self.non_members_of_a:
            resp = self._cookie_client(user).get("/api/auth/me/", HTTP_HOST=self.DOMAIN_A)
            self.assertEqual(resp.status_code, 401, f"{user.username} must be rejected on tenant A")
        for user in self.members_of_a:
            resp = self._cookie_client(user).get("/api/auth/me/", HTTP_HOST=self.DOMAIN_A)
            self.assertEqual(resp.status_code, 200, f"{user.username} must be accepted on tenant A")
            self.assertEqual(resp.data["username"], user.username)

        # Membership is per tenant: B's member works on B and is rejected on A.
        client = self._cookie_client(self.member_of_b)
        self.assertEqual(client.get("/api/auth/me/", HTTP_HOST=self.DOMAIN_B).status_code, 200)
        self.assertEqual(client.get("/api/auth/me/", HTTP_HOST=self.DOMAIN_A).status_code, 401)

    def test_existing_authentication_failures_are_unchanged(self):
        client = APIClient()
        client.cookies["access_token"] = "not-a-jwt"
        self.assertEqual(client.get("/api/auth/me/", HTTP_HOST=self.DOMAIN_A).status_code, 401)
        self.assertEqual(APIClient().get("/api/auth/me/", HTTP_HOST=self.DOMAIN_A).status_code, 401)

        self.role_member.is_active = False
        self.role_member.save(update_fields=["is_active"])
        resp = self._cookie_client(self.role_member).get("/api/auth/me/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp.status_code, 401)

    def test_public_endpoints_login_and_refresh_are_unaffected(self):
        cache.clear()  # the refresh endpoint is throttled and the cache is shared between tests

        # An AllowAny endpoint still answers, with a non-member cookie attached.
        resp = self._cookie_client(self.nobody).get(
            "/api/organizations/check-domain/", {"domain": "tacc-a"}, HTTP_HOST=self.DOMAIN_A
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["exists"])

        # Login: a member signs in, a non-member is still refused.
        resp = APIClient().post(
            "/api/auth/login/",
            {"username": self.role_member.username, "password": PASSWORD},
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(resp.status_code, 200)
        resp = APIClient().post(
            "/api/auth/login/",
            {"username": self.nobody.username, "password": PASSWORD},
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertIn(resp.status_code, (400, 401))

        # Refresh does not depend on the membership gate (it only reads the refresh cookie).
        client = APIClient()
        client.cookies["refresh_token"] = str(RefreshToken.for_user(self.role_member))
        self.assertEqual(client.post("/api/auth/refresh/", HTTP_HOST=self.DOMAIN_A).status_code, 200)


class PublicHostGateTests(TransactionTestCase):
    """On the public schema there are no tenant tables, so the gate must not query them."""

    def setUp(self):
        connection.set_schema_to_public()
        public_org, _ = Organization.objects.get_or_create(
            schema_name="public", defaults={"name": "Public Schema"}
        )
        Domain.objects.get_or_create(
            domain="testserver", tenant=public_org, defaults={"is_primary": True}
        )
        self.addCleanup(lambda: User.objects.filter(username__startswith="tacc_").delete())
        self.user = User.objects.create_user(
            username="tacc_public_user", email="tacc_public_user@tacc.test", password=PASSWORD
        )

    def test_public_schema_is_member_without_touching_tenant_tables(self):
        connection.set_schema_to_public()
        with self.assertNumQueries(0):
            self.assertTrue(is_tenant_member(self.user))
        self.assertFalse(is_tenant_member(None))
        self.assertFalse(is_tenant_member(AnonymousUser()))

    def test_public_host_request_is_not_subject_to_tenant_membership(self):
        client = APIClient()
        client.cookies["access_token"] = str(RefreshToken.for_user(self.user).access_token)
        self.assertEqual(client.get("/api/auth/me/").status_code, 200)  # default test host = public tenant
        self.assertEqual(APIClient().get("/api/organizations/check-domain/", {"domain": "x"}).status_code, 200)


class DefaultPermissionPolicyTests(SimpleTestCase):
    """A view must never fall back to DRF's allow-all default silently."""

    def test_default_permission_class_is_strict(self):
        self.assertEqual(
            tuple(settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]),
            ("accounts.tenant_access.IsTenantMember",),
        )

    @staticmethod
    def _view_classes(patterns):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                yield from DefaultPermissionPolicyTests._view_classes(pattern.url_patterns)
            else:
                view_class = getattr(pattern.callback, "cls", None)
                if view_class is not None:
                    yield view_class

    @staticmethod
    def _declares_permissions(view_class):
        if view_class.get_permissions is not APIView.get_permissions:
            return True
        return any(
            "permission_classes" in vars(klass)
            for klass in view_class.__mro__
            if issubclass(klass, APIView) and klass.__module__ != "rest_framework.views"
        )

    def test_every_drf_view_in_both_urlconfs_declares_its_permissions(self):
        missing = set()
        for urlconf in ("config.urls", "config.public_urls"):
            for view_class in self._view_classes(get_resolver(urlconf).url_patterns):
                # The router-generated API index page (rest_framework.routers.APIRootView) has no
                # permission_classes of its own, so it intentionally inherits the configured
                # DEFAULT_PERMISSION_CLASSES (IsTenantMember). Only this exact class is exempt.
                if view_class is APIRootView:
                    continue
                if issubclass(view_class, APIView) and not self._declares_permissions(view_class):
                    missing.add(f"{view_class.__module__}.{view_class.__name__}")
        self.assertEqual(sorted(missing), [], "views relying on the default permission policy")
