"""
HasPermission answers from roles.cache: same decisions as before, no queries on a cache hit, and any
change to roles or grants takes effect on the very next request.
"""
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django_tenants.utils import tenant_context

from accounts.models import User
from organizations.models import Domain, Organization

from .models import Permission, Role, UserRole
from .permissions import HasPermission


@override_settings(PERMISSION_CACHE_SECONDS=300)
class PermissionCacheTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name="perm_cache_a", name="Cache School A")
        Domain.objects.create(domain="perm-cache-a.localhost", tenant=self.school, is_primary=True)
        self.other = Organization.objects.create(schema_name="perm_cache_b", name="Cache School B")
        Domain.objects.create(domain="perm-cache-b.localhost", tenant=self.other, is_primary=True)
        self.user = User.objects.create_user(username="pc_user", email="pc_user@pc.test", password="Pass1234!")
        with tenant_context(self.school):
            self.teacher = Role.objects.create(name="Teacher X", slug="teacher-x")
            self.clerk = Role.objects.create(name="Clerk X", slug="clerk-x")
            self.teacher.permissions.set(Permission.objects.filter(codename__in=["view_student"]))
            self.clerk.permissions.set(Permission.objects.filter(codename__in=["view_fees"]))
            UserRole.objects.create(user=self.user, role=self.teacher)
            UserRole.objects.create(user=self.user, role=self.clerk)

    def tearDown(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=["perm_cache_a", "perm_cache_b"]):
            school.delete(force_drop=True)
        User.objects.filter(username="pc_user").delete()
        cache.clear()

    def _allowed(self, codename, school=None, active_role=None):
        """One fresh request, as the API would see it."""
        school = school or self.school
        url = "/x/" + (f"?active_role={active_role}" if active_role else "")
        request = RequestFactory().get(url)
        request.user = self.user
        request.tenant = school
        request.query_params = request.GET
        with tenant_context(school):
            return HasPermission(codename).has_permission(request, None)

    def test_decisions_match_the_roles(self):
        self.assertTrue(self._allowed("view_student"))
        self.assertTrue(self._allowed("view_fees"))  # granted by the other role
        self.assertFalse(self._allowed("change_student"))
        self.assertTrue(self._allowed("view_student", active_role="teacher-x"))
        self.assertFalse(self._allowed("view_fees", active_role="teacher-x"))  # a named role is checked alone

    def test_owner_passes_everything(self):
        with tenant_context(self.school):
            owner, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            UserRole.objects.create(user=self.user, role=owner)
        self.assertTrue(self._allowed("delete_anything"))

    def test_no_role_in_this_school_means_no_access(self):
        self.assertFalse(self._allowed("view_student", school=self.other))

    def test_a_cache_hit_needs_no_query(self):
        self.assertTrue(self._allowed("view_student"))
        with CaptureQueriesContext(connection) as ctx:
            self.assertTrue(self._allowed("view_fees"))
        self.assertEqual(len(ctx.captured_queries), 0, [q["sql"] for q in ctx.captured_queries])

    def _queries_for_checks(self, codes):
        """Queries one fresh request needs for these checks (cold cache)."""
        request = RequestFactory().get("/x/")
        request.user, request.tenant, request.query_params = self.user, self.school, {}
        cache.clear()
        with tenant_context(self.school), CaptureQueriesContext(connection) as ctx:
            for code in codes:
                HasPermission(code).has_permission(request, None)
        return len(ctx.captured_queries)

    def test_one_request_reads_roles_once(self):
        # Four checks in one request cost what one check costs: the roles are read once per request.
        one = self._queries_for_checks(["view_student"])
        four = self._queries_for_checks(["view_student", "view_fees", "change_student", "view_student"])
        self.assertEqual(four, one)

    def test_revoking_a_grant_applies_on_the_next_request(self):
        self.assertTrue(self._allowed("view_student"))
        with tenant_context(self.school):
            self.teacher.permissions.remove(Permission.objects.get(codename="view_student"))
        self.assertFalse(self._allowed("view_student"))

    def test_adding_a_grant_applies_on_the_next_request(self):
        self.assertFalse(self._allowed("change_student"))
        with tenant_context(self.school):
            self.clerk.permissions.add(Permission.objects.get(codename="change_student"))
        self.assertTrue(self._allowed("change_student"))

    def test_removing_a_role_applies_on_the_next_request(self):
        self.assertTrue(self._allowed("view_fees"))
        with tenant_context(self.school):
            UserRole.objects.filter(user=self.user, role=self.clerk).delete()
        self.assertFalse(self._allowed("view_fees"))

    def test_a_broken_cache_still_decides_from_the_database(self):
        with mock.patch("roles.cache.cache.get", side_effect=ConnectionError("cache down")), \
                mock.patch("roles.cache.cache.set", side_effect=ConnectionError("cache down")):
            self.assertTrue(self._allowed("view_student"))
            self.assertFalse(self._allowed("change_student"))

    def test_schools_do_not_share_answers(self):
        with tenant_context(self.other):
            role = Role.objects.create(name="Other", slug="other-x")
            UserRole.objects.create(user=self.user, role=role)
        self.assertTrue(self._allowed("view_student"))
        self.assertFalse(self._allowed("view_student", school=self.other))
