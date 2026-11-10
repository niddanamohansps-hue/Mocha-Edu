"""
Lightweight API timing for the System Health page.

RequestMetricsMiddleware times every /api/ request and adds it to an hourly summary per school and
endpoint: a request count, server errors, client errors, total time, and a histogram of durations
(from which p50 and p95 are estimated). Only counters are kept: no user, no URL values, no request data.
Summaries live in the cache (Redis) for 26 hours. If the cache is down nothing is recorded and the
request is unaffected.
"""
import logging
import re
import time
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)

# Upper bounds (ms) of the histogram buckets; the last bucket is "slower than 3.2 s".
BUCKETS_MS = (25, 50, 100, 200, 400, 800, 1600, 3200)
KEEP_SECONDS = 26 * 3600
SKIP_PREFIXES = ("/api/health/",)


_NAMED_GROUP = re.compile(r"\(\?P<(\w+)>[^)]*\)")


def readable_route(route):
    """DRF routers register regex patterns: '^students/(?P<pk>[^/.]+)/$' becomes 'students/<pk>/'."""
    route = _NAMED_GROUP.sub(r"<\1>", route)
    return route.replace("^", "").replace("$", "").replace("\\Z", "").replace("\\.", ".").replace("/?", "/")


def _hour(moment=None):
    return (moment or datetime.now(timezone.utc)).strftime("%Y%m%d%H")


def _bucket(ms):
    for index, bound in enumerate(BUCKETS_MS):
        if ms <= bound:
            return index
    return len(BUCKETS_MS)


def _redis():
    """The raw Redis client behind Django's cache, or None (tests use an in-memory cache)."""
    try:
        return cache._cache.get_client(write=True)
    except Exception:
        return None


def _namespace():
    """What keeps one deployment's counters apart from another's in a shared Redis.

    The raw Redis client used below bypasses the cache's KEY_PREFIX, so it is added here explicitly, together
    with DEPLOYMENT_ENVIRONMENT: two environments that share one Redis (a test server next to a development one,
    staging next to production) then never add to, or read, each other's numbers even for a school with the
    same schema name.
    """
    prefix = (settings.CACHES.get("default") or {}).get("KEY_PREFIX") or "-"
    return f"{prefix}:{getattr(settings, 'DEPLOYMENT_ENVIRONMENT', '') or '-'}"


def _base(schema, hour):
    return f"apimetrics:{_namespace()}:{schema}:{hour}"


def record(schema, endpoint, status_code, ms):
    hour = _hour()
    base = _base(schema, hour)
    fields = {"n": 1, f"b{_bucket(ms)}": 1, "ms": int(round(ms))}
    if status_code >= 500:
        fields["e5"] = 1
    elif status_code >= 400:
        fields["e4"] = 1
    client = _redis()
    if client is not None:
        pipe = client.pipeline(transaction=False)
        for field, amount in fields.items():
            pipe.hincrby(f"{base}:{endpoint}", field, amount)
        pipe.expire(f"{base}:{endpoint}", KEEP_SECONDS)
        pipe.sadd(f"{base}:endpoints", endpoint)
        pipe.expire(f"{base}:endpoints", KEEP_SECONDS)
        pipe.execute()
        return
    # Generic cache (tests, local memory): one key per counter.
    endpoints = cache.get(f"{base}:endpoints") or []
    if endpoint not in endpoints:
        cache.set(f"{base}:endpoints", endpoints + [endpoint], KEEP_SECONDS)
    for field, amount in fields.items():
        key = f"{base}:{endpoint}:{field}"
        if not cache.add(key, amount, KEEP_SECONDS):
            cache.incr(key, amount)


def _decode(value):
    return value.decode() if isinstance(value, bytes) else value


def _read_hour(schema, hour):
    """One hour of one school: {endpoint: {field: count}}."""
    return _read_hours(schema, [hour])[hour]


def _read_hours(schema, hours):
    """Several hours of one school in two Redis round trips, whatever the number of hours and endpoints.

    The first pipeline fetches every hour's endpoint list, the second every (hour, endpoint) hash. An hour
    whose keys have expired simply has no endpoints, and a hash that expired before its endpoint list reads
    as empty: both add nothing to the totals.
    """
    out = {hour: {} for hour in hours}
    client = _redis()
    if client is not None:
        pipe = client.pipeline(transaction=False)
        for hour in hours:
            pipe.smembers(f"{_base(schema, hour)}:endpoints")
        members = pipe.execute()
        wanted = [(hour, _decode(name)) for hour, names in zip(hours, members) for name in (names or ())]
        if not wanted:
            return out
        pipe = client.pipeline(transaction=False)
        for hour, name in wanted:
            pipe.hgetall(f"{_base(schema, hour)}:{name}")
        for (hour, name), raw in zip(wanted, pipe.execute()):
            out[hour][name] = {_decode(k): int(v) for k, v in (raw or {}).items()}
        return out
    fields = ["n", "ms", "e4", "e5"] + [f"b{i}" for i in range(len(BUCKETS_MS) + 1)]
    for hour in hours:
        base = _base(schema, hour)
        for name in cache.get(f"{base}:endpoints") or []:
            values = cache.get_many([f"{base}:{name}:{f}" for f in fields])
            out[hour][name] = {f: int(values.get(f"{base}:{name}:{f}", 0)) for f in fields}
    return out


def _percentile(counts, share):
    """Upper bound (ms) of the bucket holding the given share of requests; None past the last bound."""
    total = sum(counts)
    if not total:
        return 0
    running = 0
    for index, count in enumerate(counts):
        running += count
        if running >= share * total:
            return BUCKETS_MS[index] if index < len(BUCKETS_MS) else None
    return None


def summary(schema, hours=24):
    """Per-endpoint and overall timings for the last `hours` hours of this school."""
    now = datetime.now(timezone.utc)
    totals = {}
    by_hour = _read_hours(schema, [_hour(now - timedelta(hours=step)) for step in range(hours)])
    for hour_data in by_hour.values():
        for name, fields in hour_data.items():
            acc = totals.setdefault(name, {"n": 0, "ms": 0, "e4": 0, "e5": 0, "buckets": [0] * (len(BUCKETS_MS) + 1)})
            for key in ("n", "ms", "e4", "e5"):
                acc[key] += fields.get(key, 0)
            for i in range(len(BUCKETS_MS) + 1):
                acc["buckets"][i] += fields.get(f"b{i}", 0)

    def describe(name, acc):
        method, _, path = name.partition(" ")
        return {
            "endpoint": path,
            "method": method,
            "requests": acc["n"],
            "avg_ms": round(acc["ms"] / acc["n"]) if acc["n"] else 0,
            "p50_ms": _percentile(acc["buckets"], 0.50),
            "p95_ms": _percentile(acc["buckets"], 0.95),
            "server_errors": acc["e5"],
            "client_errors": acc["e4"],
        }

    endpoints = sorted(
        (describe(name, acc) for name, acc in totals.items() if acc["n"]),
        key=lambda row: (row["p95_ms"] is None, row["p95_ms"] or 0, row["avg_ms"]),
        reverse=True,
    )
    overall = {"n": 0, "ms": 0, "e4": 0, "e5": 0, "buckets": [0] * (len(BUCKETS_MS) + 1)}
    for acc in totals.values():
        for key in ("n", "ms", "e4", "e5"):
            overall[key] += acc[key]
        overall["buckets"] = [a + b for a, b in zip(overall["buckets"], acc["buckets"])]
    return {
        "hours": hours,
        "requests": overall["n"],
        "avg_ms": round(overall["ms"] / overall["n"]) if overall["n"] else 0,
        "p50_ms": _percentile(overall["buckets"], 0.50),
        "p95_ms": _percentile(overall["buckets"], 0.95),
        "server_errors": overall["e5"],
        "client_errors": overall["e4"],
        "endpoints": endpoints,
    }


class RequestMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, "REQUEST_METRICS_ENABLED", True)
        # The first call to an endpoint in a fresh process loads code and warms caches, so it is slow
        # in a way users of a running server never see; it is not counted (once per endpoint per process).
        self.warmed_up = set()

    def __call__(self, request):
        if not self.enabled or not request.path.startswith("/api/") or request.path.startswith(SKIP_PREFIXES):
            return self.get_response(request)
        started = time.perf_counter()
        response = self.get_response(request)
        try:
            match = getattr(request, "resolver_match", None)
            route = getattr(match, "route", None) if match else None
            # The URL pattern (students/<uuid:pk>/), never the actual values in the URL.
            endpoint = f"{request.method} /{readable_route(route)}" if route else f"{request.method} (unmatched)"
            if endpoint not in self.warmed_up:
                self.warmed_up.add(endpoint)
                return response
            record(connection.schema_name, endpoint, response.status_code, (time.perf_counter() - started) * 1000)
        except Exception:
            logger.debug("Could not record request timing.", exc_info=True)
        return response
