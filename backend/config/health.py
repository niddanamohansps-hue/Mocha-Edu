from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def health(request):
    """
    GET /api/health/ - for the load balancer and Docker. No login and no data: it only says whether this
    instance can reach its database and cache. 200 when both answer, 503 otherwise.
    """
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    try:
        cache.set("health:ping", 1, 10)
        checks["cache"] = "ok" if cache.get("health:ping") == 1 else "unavailable"
    except Exception:
        checks["cache"] = "unavailable"
    healthy = all(value == "ok" for value in checks.values())
    return JsonResponse({"status": "ok" if healthy else "degraded", **checks}, status=200 if healthy else 503)
