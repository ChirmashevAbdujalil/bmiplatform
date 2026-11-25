"""
BMI Platforma — bitiruv malakaviy ishlari va ilmiy faoliyatni raqamlashtirish tizimi.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-key-change-me-in-production-0f8a7c6b5d4e3f2a1",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
    "accounts",
    "theses",
    "research",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.platform",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MESSAGE_TAGS = {40: "danger"}

# --- Platforma sozlamalari -------------------------------------------------
UNIVERSITY_NAME = os.environ.get("BMI_UNIVERSITY_NAME", "Oliy ta’lim muassasasi")
PLATFORM_NAME = "BMI Platforma"
# Hujjatlardagi QR-kod shu manzil orqali tekshiriladi (masalan: https://bmi.univ.uz)
SITE_URL = os.environ.get("BMI_SITE_URL", "http://127.0.0.1:8000")
# Import qilinganda yangi foydalanuvchilarga beriladigan parol uzunligi
GENERATED_PASSWORD_LENGTH = 8
