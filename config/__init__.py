"""
config/__init__.py

Ensures the Celery app is always imported when Django starts
so that shared_task decorators use this app instance.
"""

from infrastructure.tasks.celery import app as celery_app

__all__ = ("celery_app",)
