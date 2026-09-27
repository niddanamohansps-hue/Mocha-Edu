from pathlib import Path
from datetime import timedelta
from decouple import config, Csv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Load secret key and debug
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)

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
}

SPECTACULAR_SETTINGS = {
    "TITLE": "EduSekai API",
    "DESCRIPTION": "EduSekai backend REST API",
    "VERSION": "1.0.0",
    "SECURITY": [{"bearerAuth": []}],
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api",
}


# JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("ACCESS_TOKEN_LIFETIME_MINUTES", cast=int, default=15)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config("REFRESH_TOKEN_LIFETIME_DAYS", cast=int, default=1)
    ),
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
