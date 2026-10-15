import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me-before-deploy")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_REQUIRED = env_bool("RECAPTCHA_REQUIRED", not DEBUG)
SMS_PROVIDER_URL = os.getenv("SMS_PROVIDER_URL", "")
SMS_PROVIDER_TOKEN = os.getenv("SMS_PROVIDER_TOKEN", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "properties",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "properties.middleware.AdminLoginRateLimitMiddleware",
    "properties.middleware.AdminOTPMiddleware",
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
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    parsed = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname,
            "PORT": parsed.port or 5432,
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "prefer")},
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "properties.User"
AUTHENTICATION_BACKENDS = ["properties.backends.EmailOrPhoneBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if os.getenv("AWS_STORAGE_BUCKET_NAME"):
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {"bucket_name": os.getenv("AWS_STORAGE_BUCKET_NAME"), "region_name": os.getenv("AWS_S3_REGION_NAME")},
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["properties.authentication.ExpiringTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("API_ANON_RATE", "120/hour"),
        "user": os.getenv("API_USER_RATE", "1200/hour"),
        "otp": os.getenv("OTP_RATE", "5/hour"),
        "lead": os.getenv("LEAD_RATE", "10/hour"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
}
API_TOKEN_TTL_HOURS = int(os.getenv("API_TOKEN_TTL_HOURS", "12"))
if API_TOKEN_TTL_HOURS < 1:
    raise ImproperlyConfigured("API_TOKEN_TTL_HOURS must be at least 1.")
SPECTACULAR_SETTINGS = {
    "TITLE": "Estate North API",
    "DESCRIPTION": "Property catalogue, staff authentication, media, floor plans and inquiry endpoints.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", PUBLIC_BASE_URL).split(",") if origin.strip()]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if os.getenv("EMAIL_HOST") else "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")
ADMINS = [
    (email.strip(), email.strip())
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
]
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", DEBUG)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.locmem.LocMemCache"
            if DEBUG
            else "django.core.cache.backends.redis.RedisCache"
        ),
        "LOCATION": (
            "estate-north-local"
            if DEBUG
            else os.getenv("REDIS_CACHE_URL", CELERY_BROKER_URL)
        ),
    }
}

if not DEBUG:
    if len(SECRET_KEY) < 50 or SECRET_KEY in {
        "dev-only-change-me-before-deploy",
        "replace-with-a-long-random-secret",
    }:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a unique random value of at least 50 characters.")
    if RECAPTCHA_REQUIRED and (not RECAPTCHA_SECRET_KEY or not RECAPTCHA_SITE_KEY):
        raise ImproperlyConfigured("Both reCAPTCHA keys are required when verification is enabled.")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_AGE = 60 * 60 * 12
