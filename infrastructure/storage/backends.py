"""
infrastructure/storage/backends.py

Storage backend abstraction.

Provides a single upload function that works with both:
  - Django's default FileSystemStorage (development)
  - django-storages S3 backend (production)

The calling code (services.py) never imports boto3 or touches
cloud-specific APIs — it just calls upload_resume().
"""

import logging
import os
import uuid
from datetime import date

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Upload path helpers
# ---------------------------------------------------------------------------

def _resume_upload_path(user_id: str, filename: str) -> str:
    """
    Build a deterministic, collision-resistant storage path.

    Pattern: resumes/{year}/{month}/{user_id}/{uuid}_{filename}

    Examples:
        resumes/2025/07/a3f2.../8b4c..._resume.pdf
    """
    today = date.today()
    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return f"resumes/{today.year}/{today.month:02d}/{user_id}/{unique_name}"


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def upload_resume(*, file, user_id: str) -> str:
    """
    Save a resume file to the configured storage backend.

    Returns the storage path (relative key) of the uploaded file.
    In production (S3), this is the S3 object key.
    In development (filesystem), it's a relative path under MEDIA_ROOT.

    The path is what gets stored in Application.resume_path.
    URLs are generated on-demand via get_resume_url().

    Args:
        file:     The validated InMemoryUploadedFile / TemporaryUploadedFile.
        user_id:  UUID string of the applicant — used to namespace the path.

    Returns:
        str: Storage path of the saved file.
    """
    path = _resume_upload_path(user_id=user_id, filename=file.name)

    # Read content and save via default_storage
    # default_storage is swapped to S3 in prod via DEFAULT_FILE_STORAGE setting
    saved_path = default_storage.save(path, ContentFile(file.read()))

    logger.info("Resume uploaded: path=%s user_id=%s", saved_path, user_id)
    return saved_path


def get_resume_url(*, path: str) -> str:
    """
    Generate a URL for a stored resume file.

    In production with S3 + django-storages, this returns a
    pre-signed URL with a short TTL (configured in settings).
    In development, it returns the local media URL.

    Args:
        path: The storage path returned by upload_resume().

    Returns:
        str: Accessible URL for the file.
    """
    return default_storage.url(path)


def delete_resume(*, path: str) -> None:
    """
    Delete a resume file from storage.
    Called when an application is withdrawn (Phase 4).

    Args:
        path: The storage path returned by upload_resume().
    """
    if default_storage.exists(path):
        default_storage.delete(path)
        logger.info("Resume deleted: path=%s", path)
    else:
        logger.warning("Attempted to delete non-existent file: path=%s", path)
