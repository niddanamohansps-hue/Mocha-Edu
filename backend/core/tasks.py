from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

HEARTBEAT_KEY = "system:celery-heartbeat"


@shared_task(ignore_result=True)
def heartbeat():
    """Scheduled every minute by beat and run by a worker: a fresh timestamp proves both are alive."""
    cache.set(HEARTBEAT_KEY, timezone.now().isoformat(), 60 * 60)
