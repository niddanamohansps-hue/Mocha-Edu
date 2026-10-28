from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Domain, Organization
from roles.models import Role, UserRole

from config.monitoring import MASK, _scrub

from .request_metrics import BUCKETS_MS, _bucket, _percentile, readable_route, record, summary
from .tasks import HEARTBEAT_KEY, heartbeat


class PercentileTests(SimpleTestCase):
    def test_buckets_and_percentiles(self):
        self.assertEqual(_bucket(10), 0)
        self.assertEqual(_bucket(25), 0)
        self.assertEqual(_bucket(26), 1)
        self.assertEqual(_bucket(99999), len(BUCKETS_MS))
        counts = [0] * (len(BUCKETS_MS) + 1)
        counts[_bucket(20)] = 90  # 90 fast requests
        counts[_bucket(700)] = 10  # 10 slow ones
        self.assertEqual(_percentile(counts, 0.5), 25)
        self.assertEqual(_percentile(counts, 0.95), 800)
        self.assertEqual(_percentile([0] * len(counts), 0.95), 0)


class ReadableRouteTests(SimpleTestCase):
    def test_router_regex_is_shown_as_a_plain_path(self):
        self.assertEqual(readable_route("api/academics/^academic-years/$"), "api/academics/academic-years/")
        self.assertEqual(readable_route("api/families/^parents/(?P<pk>[^/.]+)/$"), "api/families/parents/<pk>/")
        self.assertEqual(readable_route("api/students/detail/<uuid:pk>/"), "api/students/detail/<uuid:pk>/")


class SystemHealthApiTests(TransactionTestCase):
    SCHEMA, DOMAIN = "sys_health_school", "sys-health.localhost"

    def setUp(self):
        cache.clear()
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Health School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.owner = User.objects.create_user(username="sh_owner", email="sh_owner@sh.test", password="Pass1234!")
        self.clerk = User.objects.create_user(username="sh_clerk", email="sh_clerk@sh.test", password="Pass1234!")
        with tenant_context(self.school):
            owner_role, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            UserRole.objects.create(user=self.owner, role=owner_role)
            UserRole.objects.create(user=self.clerk, role=Role.objects.create(name="Clerk", slug="sh-clerk"))

    def tearDown(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name=self.SCHEMA):
            school.delete(force_drop=True)
        User.objects.filter(username__in=["sh_owner", "sh_clerk"]).delete()
        cache.clear()

    def _client(self, username):
        client = APIClient()
        response = client.post("/api/auth/login/", {"username": username, "password": "Pass1234!"}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 200)
        return client

    def test_owner_sees_services_and_timings(self):
        client = self._client("sh_owner")
        for _ in range(2):  # the first call per endpoint in a process is a warm-up and is not counted
            client.get("/api/auth/me/", HTTP_HOST=self.DOMAIN)
        response = client.get("/api/system-health/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 200, response.data)
        services = response.data["services"]
        self.assertEqual(services["database"]["status"], "ok")
        self.assertEqual(services["cache"]["status"], "ok")
        self.assertEqual(services["background_jobs"]["status"], "down")  # no worker in tests
        self.assertEqual(services["email_queue"]["waiting"], 0)
        endpoints = {row["endpoint"] for row in response.data["api"]["endpoints"]}
        self.assertIn("/api/auth/me/", endpoints)
        self.assertGreaterEqual(response.data["api"]["requests"], 1)

    def test_background_jobs_are_ok_after_a_heartbeat(self):
        heartbeat()
        response = self._client("sh_owner").get("/api/system-health/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.data["services"]["background_jobs"]["status"], "ok")
        self.assertIsNotNone(cache.get(HEARTBEAT_KEY))

    def test_needs_the_permission(self):
        response = self._client("sh_clerk").get("/api/system-health/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 403)

    def test_timings_are_kept_per_school_and_count_errors(self):
        record("school_x", "GET /api/things/", 200, 30)
        record("school_x", "GET /api/things/", 500, 900)
        record("school_y", "GET /api/other/", 200, 10)
        result = summary("school_x")
        self.assertEqual(result["requests"], 2)
        self.assertEqual(result["server_errors"], 1)
        self.assertEqual([row["endpoint"] for row in result["endpoints"]], ["/api/things/"])
        self.assertEqual(summary("school_y")["requests"], 1)


# Kept here (not in a module of its own): a module with only database-free tests trips the
# tenant test runner's database set-up.
class SentryScrubTests(SimpleTestCase):
    def test_personal_and_secret_data_never_leaves(self):
        event = {
            "user": {"id": "u1", "email": "parent@example.test"},
            "request": {
                "data": {"username": "svp_admin", "password": "secret"},
                "cookies": {"access_token": "abc"},
                "headers": {"Authorization": "Bearer abc", "Cookie": "x", "Host": "school.localhost"},
                "query_string": "token=abc",
            },
            "exception": {"values": [{"stacktrace": {"frames": [
                {"vars": {"password": "secret", "student_id": "42", "nested": {"api_key": "k"}}},
            ]}}]},
        }
        out = _scrub(event, None)
        self.assertNotIn("user", out)
        self.assertNotIn("data", out["request"])
        self.assertNotIn("cookies", out["request"])
        self.assertEqual(out["request"]["headers"]["Authorization"], MASK)
        self.assertEqual(out["request"]["headers"]["Cookie"], MASK)
        self.assertEqual(out["request"]["headers"]["Host"], "school.localhost")
        self.assertEqual(out["request"]["query_string"], MASK)
        frame = out["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
        self.assertEqual(frame["password"], MASK)
        self.assertEqual(frame["nested"]["api_key"], MASK)
        self.assertEqual(frame["student_id"], "42")
