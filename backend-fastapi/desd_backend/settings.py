import os
import sys
from pathlib import Path

from dotenv import load_dotenv

TESTING = "test" in sys.argv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

ROOT_ENV_PATH = ROOT_DIR / ".env"
ROOT_ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"
load_dotenv(ROOT_ENV_PATH if ROOT_ENV_PATH.exists() else ROOT_ENV_EXAMPLE_PATH)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "desd-dev-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    # Daphne must be first for ASGI + static files to work
    "daphne",
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "channels",
    "django_celery_beat",
    # Project apps
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "desd_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "api.context_processors.cart_context",
                "api.context_processors.session_context",
                "api.context_processors.recurring_order_notifications_context",
            ],
        },
    },
]

WSGI_APPLICATION = "desd_backend.wsgi.application"
ASGI_APPLICATION = "desd_backend.asgi.application"

if TESTING:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "desd"),
            "USER": os.getenv("DB_USER", "desd_user"),
            "PASSWORD": os.getenv("DB_PASSWORD", "desd_password"),
            "HOST": os.getenv("DB_HOST", "db"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

AUTH_USER_MODEL = "api.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

# Auth redirect settings (used by LoginRequiredMixin / @login_required)
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# ── Session security (TC-022) ─────────────────────────────────────────────────
# Sessions expire after 1 hour of inactivity and on browser close.
SESSION_COOKIE_AGE = 3600          # seconds (1 hour)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# Keep SESSION_COOKIE_SECURE as False in dev (no HTTPS); set True in production
SESSION_COOKIE_SECURE = not DEBUG
# Required so session_context can persist _session_last_activity on every
# request even when nothing else in the session has changed.
SESSION_SAVE_EVERY_REQUEST = True

# Custom error handlers
handler403 = "api.views_web.view_403"
handler404 = "api.views_web.view_404"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# ── Django Channels ───────────────────────────────────────────────────────────
# Tests use the in-memory layer so they don't need a running Redis.
if TESTING:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# CORS setup from .env
_frontend_urls = os.getenv(
    "FRONTEND_URLS",
    "http://localhost:5173,http://127.0.0.1:5173,http://frontend:5173",
)
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _frontend_urls.split(",") if origin.strip()]
legacy_origin = os.getenv("FRONTEND_URL")
if legacy_origin and legacy_origin not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append(legacy_origin)

CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS.copy()

REST_FRAMEWORK = {
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Fix 4: global handler — all unhandled DRF errors return {error, message}
    "EXCEPTION_HANDLER": "api.exceptions.custom_exception_handler",
}
