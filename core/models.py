"""
core/models.py

Abstract base model inherited by every domain model in the system.
Provides UUID primary keys, created_at/updated_at timestamps.
"""

import uuid
from django.db import models


class BaseModel(models.Model):
    """
    Abstract base for all domain models.

    - UUID primary key prevents enumeration attacks.
    - created_at / updated_at auto-managed.
    - Never instantiate directly.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
