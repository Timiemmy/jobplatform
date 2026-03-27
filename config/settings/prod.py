"""
config/settings/prod.py

Production settings — all security hardening enforced here.
Never run DEBUG=True in production.
All secrets come from environment variables — never hardcoded.
"""

from .base import *  # noqa: F401, F403
import environ

env = environ.Env()

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# ---------------------------------------------------------------------------
# HTTPS / Security headers
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT             = True
SECURE_HSTS_SECONDS             = 31536000   # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
SECURE_HSTS_PRELOAD             = True
SECURE_BROWSER_XSS_FILTER       = True
SECURE_CONTENT_TYPE_NOSNIFF     = True
SECURE_REFERRER_POLICY          = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS                 = "DENY"
SECURE_PROXY_SSL_HEADER         = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------

SESSION_COOKIE_SECURE   = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE      = True
CSRF_COOKIE_HTTPONLY    = True
CSRF_COOKIE_SAMESITE    = "Strict"

# ---------------------------------------------------------------------------
# CORS — explicit allowlist only
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS   = env.list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Email — mandatory verification in production
# ---------------------------------------------------------------------------

ACCOUNT_EMAIL_VERIFICATION = "mandatory"

# ---------------------------------------------------------------------------
# Tighter throttle rates for production
# ---------------------------------------------------------------------------

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    "anon":             "60/day",
    "user":             "1000/day",
    "login":            "5/minute",
    "job_applications": "10/hour",
    "register":         "10/hour",
}

# ---------------------------------------------------------------------------
# Cloud storage — S3-compatible via django-storages
# ---------------------------------------------------------------------------

DEFAULT_FILE_STORAGE  = "infrastructure.storage.s3.ResumeStorage"
STATICFILES_STORAGE   = "storages.backends.s3boto3.S3StaticStorage"

AWS_ACCESS_KEY_ID       = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY   = env("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME      = env("AWS_S3_REGION_NAME", default="us-east-1")
AWS_S3_FILE_OVERWRITE   = False          # never overwrite — UUIDs prevent collisions
AWS_DEFAULT_ACL         = None           # rely on bucket policy, not object ACL
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}
# Pre-signed URL TTL — resumes are short-lived links
AWS_QUERYSTRING_EXPIRE  = 300            # 5 minutes
AWS_S3_SIGNATURE_VERSION = "s3v4"

# ---------------------------------------------------------------------------
# Cache — tighter TTLs in production
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND":  "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS":  "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT":         5,
            "RETRY_ON_TIMEOUT":       True,
            "IGNORE_EXCEPTIONS":      True,
        },
        "KEY_PREFIX": "jobboard_prod",
        "TIMEOUT":    300,
    }
}

# ---------------------------------------------------------------------------
# Logging — structured, production-grade
# ---------------------------------------------------------------------------

LOGGING = {
    "version":                  1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()":         "core.logging.JSONFormatter",
            "format":     "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s %(name)s:%(lineno)d %(message)s",
        },
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "json",
        },
        "mail_admins": {
            "level":    "ERROR",
            "class":    "django.utils.log.AdminEmailHandler",
            "filters":  ["require_debug_false"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level":    "INFO",
    },
    "loggers": {
        "django":                   {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security":          {"handlers": ["console", "mail_admins"], "level": "ERROR", "propagate": False},
        "apps":                     {"handlers": ["console"], "level": "INFO",    "propagate": False},
        "api":                      {"handlers": ["console"], "level": "INFO",    "propagate": False},
        "infrastructure":           {"handlers": ["console"], "level": "INFO",    "propagate": False},
        "celery":                   {"handlers": ["console"], "level": "INFO",    "propagate": False},
    },
}
