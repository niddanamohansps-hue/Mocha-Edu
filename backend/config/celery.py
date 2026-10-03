import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("edusekai")
# Reads every CELERY_* key out of Django settings (CELERY_BROKER_URL,
# CELERY_TASK_ALWAYS_EAGER, etc.) - no separate Celery config file.
app.config_from_object("django.conf:settings", namespace="CELERY")
# Finds tasks.py in every installed app (notifications/tasks.py) without
# each one needing to be imported/registered by hand.
app.autodiscover_tasks()
