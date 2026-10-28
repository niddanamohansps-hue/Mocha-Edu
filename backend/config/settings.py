from pathlib import Path
from datetime import timedelta

from celery.schedules import crontab
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured
import os
import sys

from config.db_identity import build_application_name

BASE_DIR = Path(__file__).resolve().parent.parent

# Load secret key and debug
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)

_RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == "test"

# Key used to encrypt secrets at rest (see accounts/utils/crypto.py) -
# temporary account passwords shown once for distribution, and the
# signup password held by payments.Payment until a transaction completes.
# Kept independent of SECRET_KEY so it can be rotated on its own (rotating
# SECRET_KEY, e.g. after a leak, must not also silently break decryption
# of every already-encrypted password). Required whenever DEBUG=False;
# accounts.utils.crypto falls back to deriving a key from SECRET_KEY only
# for local/dev convenience when this is unset.
FIELD_ENCRYPTION_KEY = config("FIELD_ENCRYPTION_KEY", default=None)
if not DEBUG and not FIELD_ENCRYPTION_KEY and not _RUNNING_TESTS:
    raise ImproperlyConfigured(
        "FIELD_ENCRYPTION_KEY must be set when DEBUG=False. Generate one with: "
        "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
        "and set it in the environment - see .env.example."
    )

# Certificate integrity keys (certificates/services.py). A sealed certificate
# records the id of the key that sealed it, so keys can be rotated without
# invalidating issued certificates. Format: "id:secret,id:secret" (ids are
# short labels such as 1, 2; secrets are long random strings). Keep retired
# keys listed until no certificate still references them. Independent of
# SECRET_KEY on purpose. Required whenever DEBUG=False (the app refuses to
# start without it, like FIELD_ENCRYPTION_KEY); in local development a clearly
# labelled "dev" key derived from SECRET_KEY is used so nothing needs setup.
CERTIFICATE_INTEGRITY_KEYS = config("CERTIFICATE_INTEGRITY_KEYS", default="")
CERTIFICATE_INTEGRITY_ACTIVE_KEY = config("CERTIFICATE_INTEGRITY_ACTIVE_KEY", default="")
if not DEBUG and not _RUNNING_TESTS:
    if not CERTIFICATE_INTEGRITY_KEYS or not CERTIFICATE_INTEGRITY_ACTIVE_KEY:
        raise ImproperlyConfigured(
            "CERTIFICATE_INTEGRITY_KEYS and CERTIFICATE_INTEGRITY_ACTIVE_KEY must be set when DEBUG=False "
            "(see .env.example)."
        )
# Certificates sealed before key versioning carry an unversioned digest made
# with SECRET_KEY. They stay verifiable while this is True; set it to False
# once they have been re-sealed or retired. Old, unversioned digests are never
# accepted for NEW seals either way.
CERTIFICATE_ACCEPT_LEGACY_SEALS = config("CERTIFICATE_ACCEPT_LEGACY_SEALS", default=True, cast=bool)
# ID cards printed before opaque tokens carry a signed token that embeds the
# record UUID and schema name. They keep verifying while this is True; new
# cards never use that format. Retire it once old cards are reprinted.
ID_CARD_ACCEPT_LEGACY_TOKENS = config("ID_CARD_ACCEPT_LEGACY_TOKENS", default=True, cast=bool)

# JWT cookie security: forces the `Secure` flag on JWT cookies. Defaults to
# True whenever DEBUG=False so production is secure by default, while local
# HTTP development (DEBUG=True) keeps working without any .env change.
COOKIE_SECURE = config("COOKIE_SECURE", default=not DEBUG, cast=bool)

# Allowed hosts
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS", default="localhost,127.0.0.1,.localhost", cast=Csv()
)

# Application definition

SHARED_APPS = (
    "django_tenants",  # mandatory
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "accounts",
    "organizations",
    "payments",
    "billing",  # schools paying the platform (plans, subscriptions, invoices)
)

TENANT_APPS = (
    "core",  # Core utilities and management commands
    "roles",
    "profiles",
    "students",
    "staff",
    "families",
    "academics",
    "course_content",
    "attendance",
    "timetable",
    "examinations",
    "parent_portal",
    "fees",
    "notifications",
    "announcements",
    "certificates",
    "inventory",
    "payroll",
    "transport",
    "library",
    "question_bank",
    "dashboard",
)

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

TENANT_MODEL = "organizations.Organization"
TENANT_DOMAIN_MODEL = "organizations.Domain"

# Faster tests (opt-in): create each test school by copying one migrated base schema instead of running
# every migration again. Only while running tests and only with EDUSEKAI_TEST_CLONE_TENANTS=1; real schools
# are always created by running the migrations. See config/test_runner.py.
if _RUNNING_TESTS and config("EDUSEKAI_TEST_CLONE_TENANTS", default=False, cast=bool):
    TEST_RUNNER = "config.test_runner.CloneBaseSchemaRunner"
    TENANT_CREATION_FAKES_MIGRATIONS = True
    TENANT_BASE_SCHEMA = "tenant_base"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django_tenants.middleware.main.TenantMainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Times /api/ requests for the System Health page (counters only, kept in Redis for 26 hours).
    "core.request_metrics.RequestMetricsMiddleware",
    # An unpaid school is read-only (billing/enforcement.py).
    "billing.enforcement.SubscriptionWriteGuard",
]

ROOT_URLCONF = "config.urls"
PUBLIC_SCHEMA_URLCONF = "config.public_urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Environment identity (migration safety, Stage 2). Both are optional and only
# drive a startup warning (core/checks.py) and the database application_name;
# nothing is blocked. EDUSEKAI_ENV is a free label such as "development".
# EDUSEKAI_EXPECTED_DATABASE is "name@host:port" and is compared literally with
# DB_NAME / DB_HOST / DB_PORT (see config/db_identity.py).
EDUSEKAI_ENV = config("EDUSEKAI_ENV", default="")
EDUSEKAI_EXPECTED_DATABASE = config("EDUSEKAI_EXPECTED_DATABASE", default="")

# Test-only exception for config/db_guard.py: lets the identity guard accept the Django
# test database "test_<expected name>" (same host and port). Deliberately NOT read from
# the environment or .env, so no deployment setting can turn it on. It is True only when
# this process was started as `manage.py test` (argv based), and config/db_guard.py also
# requires Django's test environment to be active before it honours it.
EDUSEKAI_ALLOW_DERIVED_TEST_DB = _RUNNING_TESTS

# Database
DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": config(
            "DB_NAME",
        ),
        "USER": config(
            "DB_USER",
        ),
        "PASSWORD": config(
            "DB_PASSWORD",
        ),
        "HOST": config(
            "DB_HOST",
        ),
        "PORT": config(
            "DB_PORT",
        ),
        # Shown in pg_stat_activity and (with %a in log_line_prefix) in the
        # PostgreSQL log, so a session can be traced to this project.
        "OPTIONS": {"application_name": build_application_name(EDUSEKAI_ENV)},
        # Reuse a connection across requests (seconds) instead of opening one per request.
        # 0 restores the old behaviour. Health checks replace a connection the server dropped.
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        "CONN_HEALTH_CHECKS": True,
    }
}

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
# School calendar used by automated alerts to decide what "today" is (fee reminders). Stage 2 uses
# one zone for every school; a per-school zone is a later change.
ALERT_TIME_ZONE = config("ALERT_TIME_ZONE", default="Asia/Kathmandu")
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "accounts.backends.TenantUsernameBackend",
]

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.authentication.JWTCookieAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Strict fallback for any view that forgets to declare its own permissions: the caller must be
    # authenticated and belong to the current tenant. Public endpoints (signup, login, refresh,
    # public admissions, payment return URLs, ...) all declare AllowAny explicitly.
    "DEFAULT_PERMISSION_CLASSES": ("accounts.tenant_access.IsTenantMember",),
    # Scoped rates for the narrow set of authentication-sensitive endpoints
    # that explicitly opt in via `throttle_classes`/`throttle_scope`. No
    # DEFAULT_THROTTLE_CLASSES is set, so normal authenticated API traffic
    # elsewhere is completely unaffected.
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
        "verify_account": "5/min",
        "token_refresh": "10/min",
        "forgot_password": "5/hour",
        "reset_password": "10/min",
        "public_admissions_apply": "15/hour",
        "public_admissions_enquiry": "15/hour",
        "public_admissions_status": "60/min",
        "public_admissions_upload": "30/hour",
        "public_admissions_info": "60/min",
        "public_admissions_rotate": "10/hour",
        "public_certificate_verify": "60/min",
        # Public eSewa return/verify endpoints (fees.views.OnlinePaymentVerifyView and its
        # callback subclass). Provisional engineering value. NUM_PROXIES must be set in
        # production, otherwise DRF keys throttles on a client-suppliable X-Forwarded-For.
        "online_payment_verify": "30/min",
        # Public signup payment (payments app). Provisional engineering values; the same
        # NUM_PROXIES requirement applies.
        "signup_payment_init": "20/hour",
        "signup_payment_verify": "30/min",
    },
}

# Test-run-only accommodation. The backend's test suite performs many
# incidental logins scattered across unrelated apps' fixtures (e.g.
# timetable/tests.py alone calls the login endpoint ~39 times) that all
# share DRF's in-process throttle cache for the lifetime of one
# `manage.py test` run. That incidental volume trips the real 5/min
# "login" ceiling and produces false failures unrelated to any actual
# security behavior. Only the ambient "login" rate is raised here, and
# only when Django's test command is the active command - a deployed
# server never takes this branch. accounts.tests.SecurityHardeningTest
# explicitly restores the real "5/min" rate for the duration of its own
# throttle assertion, so the actual production threshold is still
# genuinely proven, not just assumed.
if len(sys.argv) > 1 and sys.argv[1] == "test":
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["public_admissions_apply"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["public_admissions_enquiry"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["public_admissions_status"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["public_admissions_upload"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["public_admissions_info"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["public_admissions_rotate"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["public_certificate_verify"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["online_payment_verify"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["signup_payment_init"] = "1000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["signup_payment_verify"] = "1000/min"

SPECTACULAR_SETTINGS = {
    "TITLE": "EduSekai API",
    "DESCRIPTION": "EduSekai backend REST API",
    "VERSION": "1.0.0",
    "SECURITY": [{"bearerAuth": []}],
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api",
}


# Email (password reset, etc.). Defaults to printing to the console so
# password-reset links are immediately visible in dev without any SMTP
# setup; set EMAIL_BACKEND/EMAIL_HOST/etc. via .env for real delivery.
EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@edusekai.local")

# JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("ACCESS_TOKEN_LIFETIME_MINUTES", cast=int, default=15)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config("REFRESH_TOKEN_LIFETIME_DAYS", cast=int, default=1)
    ),
}

# Password reset. PASSWORD_RESET_TIMEOUT is a built-in Django setting (in
# seconds) consumed automatically by PasswordResetTokenGenerator.check_token()
# - no other code needs to reference it. Defaults to 1 hour, deliberately
# much shorter than Django's own built-in default (3 days), since a reset
# link is a standing credential-reset capability sent over email.
PASSWORD_RESET_TIMEOUT = config(
    "PASSWORD_RESET_TIMEOUT_SECONDS", default=3600, cast=int
)

# Protocol/port for the password-reset email link. The hostname itself is
# NOT configured here - it's taken from the incoming request (the tenant's
# own subdomain, e.g. spsghy.localhost), since this is a multi-tenant app
# and a single fixed frontend URL would send every school's reset email to
# the wrong tenant. Only the protocol/port differ between dev and prod.
PASSWORD_RESET_FRONTEND_PROTOCOL = config(
    "PASSWORD_RESET_FRONTEND_PROTOCOL", default="http" if DEBUG else "https"
)
PASSWORD_RESET_FRONTEND_PORT = config("PASSWORD_RESET_FRONTEND_PORT", default="3555")

# Celery (async email outbox - see notifications/tasks.py). Redis doubles as
# broker and result backend - no RabbitMQ/separate result store needed for
# this project's scale.
#
# DB index 3 (not the default 0) and a dedicated queue name are both
# deliberate: this machine's local Redis is shared with at least one other,
# unrelated project (discovered empirically - starting a worker against the
# default db/queue immediately drained a backlog of a different app's
# recruitment-system tasks, e.g. "send_interview_email_task"). Two
# independent layers of isolation (db index + queue name) so a future app
# defaulting to either the same db OR the same queue name alone still can't
# cross-contaminate with this one.
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/3")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://localhost:6379/3")
CELERY_TASK_DEFAULT_QUEUE = config("CELERY_TASK_DEFAULT_QUEUE", default="edusekai")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TIME_LIMIT = 30
# Tests run tasks synchronously in-process - no real worker/broker needed
# to exercise the full outbox pipeline. Same sys.argv test-detection
# already used for the login-throttle test-only accommodation above.
CELERY_TASK_ALWAYS_EAGER = len(sys.argv) > 1 and sys.argv[1] == "test"
CELERY_TASK_EAGER_PROPAGATES = True

# Shared Redis Cache Configuration
# In production and staging, multi-worker setups (Gunicorn/Uvicorn) share DRF throttling
# counters and cached states via Redis DB 4 (isolated from Celery DB 3).
# During automated test runs (`manage.py test`), LocMemCache is used so test isolation
# is maintained without requiring an external running Redis instance.
# How long a user's role permissions stay cached (seconds); 0 turns the shared cache off. Tests read the
# database every time unless a test enables it, because the in-memory test cache outlives each test.
PERMISSION_CACHE_SECONDS = 0 if _RUNNING_TESTS else config("PERMISSION_CACHE_SECONDS", default=300, cast=int)

REDIS_CACHE_URL = config("REDIS_CACHE_URL", default=config("CACHE_URL", default="redis://localhost:6379/4"))

if _RUNNING_TESTS:
    # Django's test runner forces DEBUG=False, so the local-dev "dev" integrity
    # key would not apply; give the test run explicit, obviously fake keys
    # (only if none were supplied). Never used outside `manage.py test`.
    if not CERTIFICATE_INTEGRITY_KEYS:
        CERTIFICATE_INTEGRITY_KEYS = "1:test-only-integrity-key-not-a-secret"
        CERTIFICATE_INTEGRITY_ACTIVE_KEY = "1"
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "edusekai-test-cache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_CACHE_URL,
            "KEY_PREFIX": "edusekai",
            "TIMEOUT": 300,
        }
    }

# Beat schedule: periodic tasks only, no per-run business logic lives here.
# recover_stale_outbox_events (notifications/tasks.py) re-dispatches any
# EmailOutboxEvent stuck in PENDING/RETRYING for longer than that module's
# own STALE_THRESHOLD_MINUTES (15) - the task's docstring already called
# for "every 10 minutes" before Beat was wired up; kept as-is here so a
# stuck event waits at most ~25 minutes (15 to go stale + up to 10 for the
# next tick) before being retried, without re-scanning every tenant schema
# more often than that. No explicit "queue" override is set here - Beat
# sends tasks through the same apply_async() path as .delay(), so this
# inherits CELERY_TASK_DEFAULT_QUEUE ("edusekai") exactly like every other
# task in this project, none of which set a queue explicitly either.
#
# Operational requirement: exactly ONE `celery -A config beat` process may
# run against this broker at a time. A second concurrent Beat instance
# (e.g. one left running on an old deploy) would re-trigger this same
# schedule independently, causing duplicate recovery runs - not harmful by
# itself (send_outbox_email is idempotent against SENT/FAILED events), but
# wasted work and confusing logs. Supervise Beat as a single long-running
# process (one instance per environment), separate from, and in addition
# to, the `celery -A config worker` process(es) that actually execute tasks.
CELERY_BEAT_SCHEDULE = {
    # Trials and unpaid subscriptions move to grace, then read-only.
    "refresh-subscriptions": {
        "task": "billing.tasks.refresh_subscriptions",
        "schedule": crontab(hour=0, minute=30),
    },
    # Proves the scheduler and a worker are alive (shown on the System Health page).
    "system-heartbeat": {
        "task": "core.tasks.heartbeat",
        "schedule": timedelta(minutes=1),
    },
    "recover-stale-outbox-events": {
        "task": "notifications.tasks.recover_stale_outbox_events",
        "schedule": timedelta(minutes=10),
    },
    # Publishes due scheduled announcements; an announcement goes out at most
    # this long after its scheduled time. Safe to overlap (row-locked publish).
    "publish-due-announcements": {
        "task": "announcements.tasks.publish_due_announcements",
        "schedule": timedelta(minutes=5),
    },
    # Reconciles pending online payment orders across active tenant schemas.
    "reconcile-pending-online-payments": {
        "task": "fees.tasks.reconcile_pending_online_payments",
        "schedule": timedelta(minutes=5),
    },
    # Paid-signup flow (public schema): asks eSewa about unpaid-looking signups, queues institution
    # setup for paid ones, expires stale reservations and announces signups that need a person.
    "reconcile-signup-payments": {
        "task": "payments.tasks.reconcile_signup_payments",
        "schedule": timedelta(minutes=5),
    },
    # Fee due-soon / overdue reminders, once a day at 02:30 UTC = 08:15 in Nepal. Which day counts
    # as "today" is decided by ALERT_TIME_ZONE; a missed run is caught up on the next one.
    "send-fee-reminders": {
        "task": "fees.tasks.send_fee_reminders",
        "schedule": crontab(hour=2, minute=30),
    },
}

# CORS
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://localhost:3000$",
    r"^https?://localhost:3555$",
    r"^https?://([a-zA-Z0-9-]+\.)+localhost:3000$",
    r"^https?://([a-zA-Z0-9-]+\.)+localhost:3555$",
]
CORS_ALLOW_CREDENTIALS = True

# =====================================================================
# Production TLS & Security Headers (Gate 3 Remediations)
# =====================================================================

# HTTPS enforcement: redirects all HTTP traffic to HTTPS in staging/production.
# Disabled in local development (DEBUG=True) and during test runs.
SECURE_SSL_REDIRECT = config(
    "SECURE_SSL_REDIRECT", default=False if (DEBUG or _RUNNING_TESTS) else True, cast=bool
)

# Trusted reverse-proxy HTTPS protocol header.
# Enabled only when explicitly behind a reverse proxy terminating SSL.
# Fails closed (disabled) in local/test to prevent trusting spoofed headers.
USE_SECURE_PROXY_SSL_HEADER = config(
    "USE_SECURE_PROXY_SSL_HEADER", default=not DEBUG and not _RUNNING_TESTS, cast=bool
)
if USE_SECURE_PROXY_SSL_HEADER:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    SECURE_PROXY_SSL_HEADER = None

# Session & CSRF cookie security
SESSION_COOKIE_SECURE = config(
    "SESSION_COOKIE_SECURE", default=not DEBUG and not _RUNNING_TESTS, cast=bool
)
CSRF_COOKIE_SECURE = config(
    "CSRF_COOKIE_SECURE", default=not DEBUG and not _RUNNING_TESTS, cast=bool
)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# HTTP Strict Transport Security (HSTS)
# In accordance with pre-production security policy, HSTS defaults to 0 (disabled)
# until HTTPS is confirmed operational in production to prevent lockout.
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False, cast=bool
)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=False, cast=bool)

# Content Security & Frame Protection
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = config("X_FRAME_OPTIONS", default="DENY")
SECURE_REFERRER_POLICY = config("SECURE_REFERRER_POLICY", default="same-origin")

# CSRF Trusted Origins
_csrf_raw = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in _csrf_raw if origin.strip()]
if not CSRF_TRUSTED_ORIGINS and DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:3555",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3555",
    ]

# =====================================================================
# Private Media Delivery (BLK-01)
# =====================================================================
USE_X_ACCEL_REDIRECT = config("USE_X_ACCEL_REDIRECT", default=False, cast=bool)
X_ACCEL_PREFIX = config("X_ACCEL_PREFIX", default="/protected_media/")

# =====================================================================
# Antivirus Scanning (BLK-04)
# =====================================================================
CLAMAV_ENABLED = config("CLAMAV_ENABLED", default=False if (DEBUG or _RUNNING_TESTS) else True, cast=bool)
CLAMAV_HOST = config("CLAMAV_HOST", default="localhost")
CLAMAV_PORT = config("CLAMAV_PORT", default=3310, cast=int)
CLAMAV_TIMEOUT_SECONDS = config("CLAMAV_TIMEOUT_SECONDS", default=10, cast=int)
CLAMAV_FAIL_CLOSED = config("CLAMAV_FAIL_CLOSED", default=True, cast=bool)


# eSewa Payment Gateway. ESEWA_CLIENT_SECRET has no default: payments.utils
# refuses to sign or verify without it, so an unset value must stay None.
ESEWA_CLIENT_ID = config("ESEWA_CLIENT_ID", default="")
ESEWA_CLIENT_SECRET = config("ESEWA_CLIENT_SECRET", default=None)
ESEWA_PRODUCT_CODE = config("ESEWA_PRODUCT_CODE", default="EPAYTEST")
# Signup payment amount in NPR (plain decimal, max 2 places). Validated by
# payments.utils.get_signup_payment_amount(); an invalid value fails closed.
ESEWA_SIGNUP_PAYMENT_AMOUNT = config("ESEWA_SIGNUP_PAYMENT_AMOUNT", default="500")
# How long an unpaid signup keeps its subdomain reserved (minutes). Provisional engineering value.
SIGNUP_PAYMENT_TTL_MINUTES = config("SIGNUP_PAYMENT_TTL_MINUTES", default=60, cast=int)
# Reconciliation of paid signups. Provisional engineering values, not eSewa requirements.
# How long an unpaid signup's stored password is kept so a late payment can still be honoured.
SIGNUP_PAYMENT_DATA_RETENTION_DAYS = config("SIGNUP_PAYMENT_DATA_RETENTION_DAYS", default=7, cast=int)
# A PENDING signup is first checked with eSewa after this many minutes.
SIGNUP_RECONCILE_GRACE_MINUTES = config("SIGNUP_RECONCILE_GRACE_MINUTES", default=10, cast=int)
# Automatic attempts to create the institution of a paid signup before a person is alerted.
SIGNUP_PROVISIONING_MAX_ATTEMPTS = config("SIGNUP_PROVISIONING_MAX_ATTEMPTS", default=3, cast=int)
# Comma-separated addresses told about paid signups that need a person. Empty: logged only.
SIGNUP_PAYMENT_ALERT_EMAILS = config("SIGNUP_PAYMENT_ALERT_EMAILS", default="")
ESEWA_URL = config(
    "ESEWA_URL", default="https://rc-epay.esewa.com.np/api/epay/main/v2/form"
)
ESEWA_STATUS_URL = config(
    "ESEWA_STATUS_URL", default="https://rc.esewa.com.np/api/epay/transaction/status/"
)
# The platform's own Razorpay account: schools pay their EduSekai subscription here (school fees go to
# each school's own account instead, see fees/gateway_views.py). Test keys start rzp_test_.
PLATFORM_RAZORPAY_KEY_ID = config("PLATFORM_RAZORPAY_KEY_ID", default="")
PLATFORM_RAZORPAY_KEY_SECRET = config("PLATFORM_RAZORPAY_KEY_SECRET", default="")
PLATFORM_RAZORPAY_WEBHOOK_SECRET = config("PLATFORM_RAZORPAY_WEBHOOK_SECRET", default="")
PLATFORM_NAME = config("PLATFORM_NAME", default="EduSekai")
# Printed on invoices. Without a GSTIN they are plain invoices, not GST tax invoices.
PLATFORM_LEGAL_NAME = config("PLATFORM_LEGAL_NAME", default="")
PLATFORM_GSTIN = config("PLATFORM_GSTIN", default="")
PLATFORM_ADDRESS = config("PLATFORM_ADDRESS", default="")
BILLING_INVOICE_PREFIX = config("BILLING_INVOICE_PREFIX", default="ES")
BILLING_GRACE_DAYS = config("BILLING_GRACE_DAYS", default=7, cast=int)

FEES_ALLOW_GLOBAL_GATEWAY_FALLBACK = config(
    "FEES_ALLOW_GLOBAL_GATEWAY_FALLBACK", default=True, cast=bool
)

# Online-payment reconciliation timing. PROVISIONAL ENGINEERING DEFAULTS, NOT eSewa REQUIREMENTS
# (the official contract could not be verified when these were chosen):
# - grace: how long after an order's expires_at an authoritative NOT_FOUND may expire it;
# - horizon: how long after expires_at an order with no authoritative answer (pending,
#   ambiguous, errors) is escalated to staff reconciliation. It is never auto-failed.
FEES_GATEWAY_GRACE_MINUTES = config("FEES_GATEWAY_GRACE_MINUTES", default=15, cast=int)
FEES_RECONCILE_HORIZON_HOURS = config("FEES_RECONCILE_HORIZON_HOURS", default=24, cast=int)

# Jazzmin Settings
JAZZMIN_SETTINGS = {
    "site_title": "EDU Sekai Admin",
    "site_header": "EDU Sekai",
    "site_brand": "EDU Sekai",
    "welcome_sign": "Welcome to EDU Sekai Management System",
    "show_sidebar": True,
    # 🔑 IMPORTANT
    "navigation_expanded": False,  # allow collapse
    "search_model": ["accounts.User", "organizations.Organization"],
    "icons": {
        "accounts.User": "fas fa-users",
        "accounts.Group": "fas fa-users-cog",
        "organizations.Organization": "fas fa-university",
        "organizations.Domain": "fas fa-globe",
        "payments.Payment": "fas fa-credit-card",
        "profiles.Profile": "fas fa-user-circle",
        "students.Student": "fas fa-user-graduate",
        "staff.StaffMember": "fas fa-user-tie",
        "staff.Instructor": "fas fa-chalkboard-teacher",
        "families.Parent": "fas fa-users",
        "profiles.InstitutionProfile": "fas fa-school",
        "roles.Role": "fas fa-user-shield",
        "roles.UserRole": "fas fa-user-tag",
    },
    "order_with_respect_to": [
        "organizations",
        "accounts",
        "profiles",
        "payments",
        "roles",
    ],
}

JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "navbar": "navbar-dark",
    "navbar_fixed": True,
    "layout_fixed": True,
}

# Media Files (User Uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Error and performance reporting (config/monitoring.py). Off unless SENTRY_DSN is set; never in tests.
# SENTRY_TRACES_SAMPLE_RATE is the share of requests timed (0.05 = 5%): enough to see slow endpoints.
SENTRY_DSN = "" if _RUNNING_TESTS else config("SENTRY_DSN", default="")
if SENTRY_DSN:
    from config.monitoring import init_sentry

    init_sentry(
        SENTRY_DSN,
        environment=EDUSEKAI_ENV,
        traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", default=0.05, cast=float),
        release=config("SENTRY_RELEASE", default=""),
    )
