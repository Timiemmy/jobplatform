"""
infrastructure/tasks/celery.py

Celery application instance.
Imported in config/__init__.py to ensure tasks are discovered at startup.

Usage:
    Start worker: celery -A config worker --loglevel=info
    Start beat:   celery -A config beat --loglevel=info
"""

import os
from celery import Celery

# Set default settings module for Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("jobboard")

# Pull Celery config from Django settings, namespaced with CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all INSTALLED_APPS
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Utility task for verifying the Celery worker is running."""
    print(f"Celery worker is alive. Request: {self.request!r}")
