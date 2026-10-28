"""
Production web server settings (used by docker-compose.prod.yml):

    gunicorn config.wsgi -c gunicorn.conf.py

Each value can be overridden with an environment variable.
"""
import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# Processes x threads = requests handled at once. Threads suit this app: most of a request is spent
# waiting on PostgreSQL. Keep workers x threads under PostgreSQL's max_connections (default 100).
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 4))

timeout = int(os.environ.get("GUNICORN_TIMEOUT", 60))
graceful_timeout = 30
keepalive = 5

# Recycle each worker after a while so slow memory growth can never build up.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
