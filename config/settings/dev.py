"""
Development settings.
Never use these in production.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Looser throttling in dev so manual testing isn't blocked
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    "anon": "1000/day",
    "user": "10000/day",
    "login": "100/minute",
    "job_applications": "100/hour",
}

# Print emails to console in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Django Debug Toolbar (install separately if needed)
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]

# ---------------------------------------------------------------------------
# Logging — human-readable format for development
# ---------------------------------------------------------------------------

LOGGING = {
    "version":                  1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s %(name)s:%(lineno)d  %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "DEBUG"},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},   # suppress SQL noise
        "faker":              {"level": "WARNING"},
    },
}
