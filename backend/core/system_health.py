"""
GET /api/system-health/ - what the System Health page shows: this school's email queue and its API timings for
the last 24 hours and, for platform operators only, whether the shared services answer (database, cache,
background workers). Read-only; needs view_system_health.
"""
import time
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from roles.permissions import HasPermission

from .request_metrics import summary
from .tasks import heartbeat_key

# The heartbeat runs every minute; older than this means the worker or the scheduler has stopped.
HEARTBEAT_STALE_AFTER = timedelta(minutes=3)


def _timed(check):
    started = time.perf_counter()
    try:
        detail = check()
        return {"status": "ok", "ms": round((time.perf_counter() - started) * 1000, 1), **(detail or {})}
    except Exception:
        return {"status": "down", "ms": None}


def _database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def _cache():
    cache.set("system:ping", 1, 10)
    if cache.get("system:ping") != 1:
        raise RuntimeError("cache did not answer")


def _background_jobs():
    raw = cache.get(heartbeat_key())
    if not raw:
        return {"status": "down", "last_seen": None}
    seen = datetime.fromisoformat(raw)
    age = timezone.now() - seen
    return {"status": "ok" if age <= HEARTBEAT_STALE_AFTER else "down", "last_seen": raw}


def _email_queue():
    from notifications.models import EmailOutboxEvent

    since = timezone.now() - timedelta(hours=24)
    rows = EmailOutboxEvent.objects
    waiting = rows.filter(status__in=["pending", "retrying"]).count()
    failed = rows.filter(status="failed", updated_at__gte=since).count()
    sent = rows.filter(status="sent", updated_at__gte=since).count()
    status = "ok" if waiting < 100 and failed == 0 else "warning"
    return {"status": status, "waiting": waiting, "failed_24h": failed, "sent_24h": sent}


class SystemHealthView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_system_health")]

    def get(self, request):
        # Shared infrastructure (the database server, Redis, the Celery workers) belongs to the platform, not to
        # one school: only platform operators (superusers, as for the billing dashboard) see it. A school sees its
        # own email queue and its own API timings.
        platform = bool(getattr(request.user, "is_superuser", False))
        services = {}
        if platform:
            services["database"] = _timed(_database)
            services["cache"] = _timed(_cache)
            try:
                services["background_jobs"] = _background_jobs()
            except Exception:
                services["background_jobs"] = {"status": "down", "last_seen": None}
        try:
            services["email_queue"] = _email_queue()
        except Exception:
            services["email_queue"] = {"status": "down"}
        try:
            api = summary(connection.schema_name)
        except Exception:
            api = None
        return Response(
            {"checked_at": timezone.now().isoformat(), "platform": platform, "services": services, "api": api}
        )
