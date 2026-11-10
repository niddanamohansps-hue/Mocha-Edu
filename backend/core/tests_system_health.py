from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Domain, Organization
from roles.models import Role, UserRole

from config.monitoring import MASK, _scrub

from . import request_metrics
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


class FakeRedis:
    """Just enough of a redis-py client for request_metrics, counting every command and every round trip."""

    def __init__(self):
        self.hashes, self.sets = {}, {}
        self.commands = 0
        self.round_trips = 0

    def _run(self, name, *args):
        self.commands += 1
        if name == "hincrby":
            key, field, amount = args
            h = self.hashes.setdefault(key, {})
            h[field.encode()] = str(int(h.get(field.encode(), b"0")) + amount).encode()
        elif name == "sadd":
            self.sets.setdefault(args[0], set()).add(args[1].encode())
        elif name == "expire":
            return True
        elif name == "smembers":
            return set(self.sets.get(args[0], set()))
        elif name == "hgetall":
            return dict(self.hashes.get(args[0], {}))

    # direct (one round trip each), as the reader before the change used them
    def smembers(self, key):
        self.round_trips += 1
        return self._run("smembers", key)

    def hgetall(self, key):
        self.round_trips += 1
        return self._run("hgetall", key)

    def pipeline(self, transaction=False):
        client = self

        class Pipe:
            def __init__(self):
                self.queued = []

            def __getattr__(self, name):
                return lambda *args: self.queued.append((name, args))

            def execute(self):
                client.round_trips += 1
                return [client._run(name, *args) for name, args in self.queued]

        return Pipe()


def legacy_summary_totals(schema, client, hours=24):
    """The reader as it was before batching (one smembers per hour, one hgetall per endpoint and hour)."""
    now = datetime.now(dt_timezone.utc)
    totals = {}
    for step in range(hours):
        base = f"{request_metrics._base(schema, request_metrics._hour(now - timedelta(hours=step)))}"
        for raw_name in client.smembers(f"{base}:endpoints"):
            name = raw_name.decode()
            fields = {k.decode(): int(v) for k, v in client.hgetall(f"{base}:{name}").items()}
            acc = totals.setdefault(name, {})
            for key, value in fields.items():
                acc[key] = acc.get(key, 0) + value
    return totals


class RedisTelemetryTests(SimpleTestCase):
    """The raw-Redis path the System Health page uses in every real deployment (the test cache is LocMem)."""

    def setUp(self):
        self.redis = FakeRedis()
        patcher = mock.patch.object(request_metrics, "_redis", return_value=self.redis)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fill(self, schema="school_x", endpoints=6, hours=24):
        now = datetime.now(dt_timezone.utc)
        for step in range(hours):
            moment = now - timedelta(hours=step)
            with mock.patch.object(request_metrics, "_hour", return_value=request_metrics._hour(moment)):
                for e in range(endpoints):
                    for i in range(step % 4 + 1):
                        record(schema, f"GET /api/e{e}/", 500 if (e + i) % 7 == 0 else 200, 20 * (e + 1) * (i + 1))

    def test_keys_carry_the_cache_prefix_environment_and_school(self):
        with override_settings(DEPLOYMENT_ENVIRONMENT="production"):
            record("school_x", "GET /api/things/", 200, 30)
        prefix = settings.CACHES["default"].get("KEY_PREFIX") or "-"
        key = next(iter(self.redis.hashes))
        self.assertTrue(key.startswith(f"apimetrics:{prefix}:production:school_x:"), key)

    def test_two_environments_sharing_redis_never_combine(self):
        with override_settings(DEPLOYMENT_ENVIRONMENT="production"):
            record("school_x", "GET /api/things/", 200, 30)
        with override_settings(DEPLOYMENT_ENVIRONMENT="staging"):
            for _ in range(5):
                record("school_x", "GET /api/things/", 500, 3000)
            self.assertEqual(summary("school_x")["requests"], 5)
            self.assertEqual(summary("school_x")["server_errors"], 5)
        with override_settings(DEPLOYMENT_ENVIRONMENT="production"):
            result = summary("school_x")
            self.assertEqual(result["requests"], 1)
            self.assertEqual(result["server_errors"], 0)

    def test_schools_stay_apart_within_one_environment(self):
        record("school_x", "GET /api/things/", 500, 30)
        record("school_y", "GET /api/other/", 200, 10)
        self.assertEqual([r["endpoint"] for r in summary("school_x")["endpoints"]], ["/api/things/"])
        self.assertEqual(summary("school_y")["server_errors"], 0)

    def test_batched_reader_matches_the_previous_reader_and_uses_two_round_trips(self):
        self._fill()
        before_trips, before_cmds = self.redis.round_trips, self.redis.commands
        legacy = legacy_summary_totals("school_x", self.redis)
        legacy_trips = self.redis.round_trips - before_trips
        legacy_cmds = self.redis.commands - before_cmds

        before_trips, before_cmds = self.redis.round_trips, self.redis.commands
        result = summary("school_x")
        new_trips = self.redis.round_trips - before_trips
        new_cmds = self.redis.commands - before_cmds

        by_endpoint = {f"{r['method']} {r['endpoint']}": r for r in result["endpoints"]}
        self.assertEqual(set(by_endpoint), set(legacy))
        for name, acc in legacy.items():
            row = by_endpoint[name]
            self.assertEqual(row["requests"], acc["n"])
            self.assertEqual(row["server_errors"], acc.get("e5", 0))
            self.assertEqual(row["avg_ms"], round(acc["ms"] / acc["n"]))
            buckets = [acc.get(f"b{i}", 0) for i in range(len(BUCKETS_MS) + 1)]
            self.assertEqual(row["p50_ms"], _percentile(buckets, 0.50))
            self.assertEqual(row["p95_ms"], _percentile(buckets, 0.95))
        self.assertEqual(result["requests"], sum(acc["n"] for acc in legacy.values()))
        # 24 hours x 6 endpoints: 24 + 144 = 168 round trips before, 2 now; the command count is unchanged
        self.assertEqual(legacy_trips, 168)
        self.assertEqual(new_trips, 2)
        self.assertEqual(new_cmds, legacy_cmds)

    def test_expired_hours_and_hashes_are_skipped_safely(self):
        self._fill(endpoints=2, hours=3)
        # an endpoint hash that expired before its hour's endpoint list
        expired = next(k for k in self.redis.hashes if k.endswith(":GET /api/e0/"))
        del self.redis.hashes[expired]
        result = summary("school_x")
        self.assertGreater(result["requests"], 0)
        self.assertTrue(all(r["requests"] > 0 for r in result["endpoints"]))
        self.assertEqual(summary("nobody")["requests"], 0)
        self.assertEqual(self.redis.round_trips >= 1, True)


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
        self.operator = User.objects.create_superuser(username="sh_operator", email="sh_operator@sh.test", password="Pass1234!")
        with tenant_context(self.school):
            owner_role, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            UserRole.objects.create(user=self.owner, role=owner_role)
            UserRole.objects.create(user=self.clerk, role=Role.objects.create(name="Clerk", slug="sh-clerk"))

    def tearDown(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name=self.SCHEMA):
            school.delete(force_drop=True)
        User.objects.filter(username__in=["sh_owner", "sh_clerk", "sh_operator"]).delete()
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
        # a school owner sees the school's own email queue and timings, never the shared infrastructure
        self.assertFalse(response.data["platform"])
        self.assertEqual(set(services), {"email_queue"})
        self.assertEqual(services["email_queue"]["waiting"], 0)
        endpoints = {row["endpoint"] for row in response.data["api"]["endpoints"]}
        self.assertIn("/api/auth/me/", endpoints)
        self.assertGreaterEqual(response.data["api"]["requests"], 1)

    def test_platform_operator_sees_the_shared_services(self):
        response = self._client("sh_operator").get("/api/system-health/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["platform"])
        services = response.data["services"]
        self.assertEqual(services["database"]["status"], "ok")
        self.assertEqual(services["cache"]["status"], "ok")
        self.assertEqual(services["background_jobs"]["status"], "down")  # no worker in tests
        self.assertIn("email_queue", services)

    def test_screens_see_what_the_server_grants(self):
        # a superuser with no role in this school passes every server check, so /me must say so ("*")
        me = self._client("sh_operator").get("/api/auth/me/", HTTP_HOST=self.DOMAIN).data
        self.assertEqual(me["permissions"], ["*"])
        self.assertEqual(me["roles"], [])
        # unchanged for everyone else: an owner gets "*", a role without grants gets nothing
        self.assertEqual(self._client("sh_owner").get("/api/auth/me/", HTTP_HOST=self.DOMAIN).data["permissions"], ["*"])
        self.assertEqual(self._client("sh_clerk").get("/api/auth/me/", HTTP_HOST=self.DOMAIN).data["permissions"], [])

    def test_background_jobs_are_ok_after_a_heartbeat(self):
        heartbeat()
        response = self._client("sh_operator").get("/api/system-health/", HTTP_HOST=self.DOMAIN)
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
