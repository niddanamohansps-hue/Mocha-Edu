from pathlib import Path
from datetime import timedelta
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured
import os
import sys

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
    "dashboard",
)

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

TENANT_MODEL = "organizations.Organization"
TENANT_DOMAIN_MODEL = "organizations.Domain"

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
]

ROOT_URLCONF = "config.urls"

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
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "accounts.backends.TenantUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.authentication.JWTCookieAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Scoped rates for the narrow set of authentication-sensitive endpoints
    # that explicitly opt in via `throttle_classes`/`throttle_scope`. No
    # DEFAULT_THROTTLE_CLASSES is set, so normal authenticated API traffic
    # elsewhere is completely unaffected.
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
        "verify_account": "5/min",
        "token_refresh": "10/min",
        "register_organization": "3/hour",
        "forgot_password": "5/hour",
        "reset_password": "10/min",
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
    "recover-stale-outbox-events": {
        "task": "notifications.tasks.recover_stale_outbox_events",
        "schedule": timedelta(minutes=10),
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

# eSewa Payment Gateway
ESEWA_CLIENT_ID = config("ESEWA_CLIENT_ID", default="")
ESEWA_CLIENT_SECRET = config("ESEWA_CLIENT_SECRET", default="")
ESEWA_PRODUCT_CODE = config("ESEWA_PRODUCT_CODE", default="EPAYTEST")
ESEWA_URL = config(
    "ESEWA_URL", default="https://rc-epay.esewa.com.np/api/epay/main/v2/form"
)

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
