import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

ROOT_ENV_PATH = ROOT_DIR / ".env"
ROOT_ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"
load_dotenv(ROOT_ENV_PATH if ROOT_ENV_PATH.exists() else ROOT_ENV_EXAMPLE_PATH)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "desd-dev-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "desd_backend.urls"

TEMPLATES = []
WSGI_APPLICATION = "desd_backend.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


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
}
