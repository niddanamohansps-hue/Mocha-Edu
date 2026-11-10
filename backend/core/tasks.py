from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

_HEARTBEAT_BASE = "system:celery-heartbeat"


def heartbeat_key():
    """Per deployment: a worker in one environment sharing Redis must never make another look healthy."""
    return f"{_HEARTBEAT_BASE}:{getattr(settings, 'DEPLOYMENT_ENVIRONMENT', '') or '-'}"


@shared_task(ignore_result=True)
def heartbeat():
    """Scheduled every minute by beat and run by a worker: a fresh timestamp proves both are alive."""
    cache.set(heartbeat_key(), timezone.now().isoformat(), 60 * 60)
