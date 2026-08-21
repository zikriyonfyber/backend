"""
ZEAIPC / Zikriyon Fyber ISP Backend — Django settings.

Company (hub/identity): ZEAIPC
Product (routers/cards/app): Zikriyon Fyber
"""
import os
from datetime import timedelta
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="change-me-in-production")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
    "django_celery_beat",
    "drf_spectacular",

    "apps.accounts",
    "apps.billing",
    "apps.voip",
    "apps.weather",
    "apps.routerapi",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="zeaipc"),
        "USER": config("DB_USER", default="zeaipc"),
        "PASSWORD": config("DB_PASSWORD", default="zeaipc"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    },
    # Kamailio's own DB schema (subscriber/location tables), created by
    # kamailio-db-modules' kamdbctl. Django never migrates this alias —
    # see DATABASE_ROUTERS below, which excludes all Django apps from it.
    "kamailio": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("KAMAILIO_DB_NAME", default="kamailio"),
        "USER": config("KAMAILIO_DB_USER", default="kamailio"),
        "PASSWORD": config("KAMAILIO_DB_PASSWORD", default="kamailio"),
        "HOST": config("KAMAILIO_DB_HOST", default="localhost"),
        "PORT": config("KAMAILIO_DB_PORT", default="5432"),
    },
}

DATABASE_ROUTERS = ["config.db_routers.KamailioRouter"]

AUTH_USER_MODEL = "accounts.Subscriber"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# REST Framework / AAA
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "apps.routerapi.auth.RouterAPIKeyAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "chip-auth": "30/min",
        "accounting": "120/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=6),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
}

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000",
    cast=Csv(),
)

# ---------------------------------------------------------------------------
# Celery (billing expiry sweeps, usage aggregation, weather polling)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = TIME_ZONE

# ---------------------------------------------------------------------------
# ZEAIPC / Zikriyon Fyber domain settings
# ---------------------------------------------------------------------------
ZEAIPC = {
    "COMPANY_NAME": "ZEAIPC",
    "PRODUCT_BRAND": "Zikriyon Fyber",
    # Shared-secret used by RouterAPIKeyAuthentication as a fallback layer
    # in front of per-router API keys (defense in depth, not the only check).
    "ROUTER_SHARED_SECRET": config("ROUTER_SHARED_SECRET", default="change-me"),
    # SIP realm that Kamailio/FreeSWITCH is configured for.
    "SIP_DOMAIN": config("SIP_DOMAIN", default="sip.zikriyonfyber.net"),
    "SIP_NUMBER_PREFIX": config("SIP_NUMBER_PREFIX", default="92700"),
    "SIP_SERVER_SECRET": config("SIP_SERVER_SECRET", default="change-me"),
    # Free on-network calling: SIP numbers under this ISP always route,
    # even if the subscriber's data plan / balance has expired.
    "OFFLINE_VOIP_ALWAYS_ON": True,
    "WEATHER_PROVIDER_API_KEY": config("WEATHER_PROVIDER_API_KEY", default=""),
    "WEATHER_POLL_INTERVAL_MINUTES": 30,
}
