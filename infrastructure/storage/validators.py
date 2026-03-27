"""
infrastructure/storage/validators.py

File upload validation.

Enforced rules:
  - Allowed MIME types: application/pdf, application/vnd.openxmlformats...
  - Allowed extensions: .pdf, .docx
  - Max file size: 5 MB

Validation happens at TWO layers:
  1. Serializer layer  — fast reject on extension/size before hitting disk
  2. This module       — MIME sniffing via python-magic (content-based, not extension)

Why both? Extensions can be spoofed. MIME sniffing reads the actual file bytes.
"""

import logging
import os

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

ALLOWED_EXTENSIONS = {".pdf", ".docx"}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

EXTENSION_TO_MIME = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_resume_extension(file) -> None:
    """
    Validate file extension is .pdf or .docx.
    Fast check — runs before any I/O.

    Raises:
        ValidationError: if extension is not allowed.
    """
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. "
            f"Only {', '.join(sorted(ALLOWED_EXTENSIONS))} files are accepted."
        )


def validate_resume_size(file) -> None:
    """
    Validate file does not exceed MAX_FILE_SIZE_BYTES.

    Raises:
        ValidationError: if file exceeds the size limit.
    """
    if file.size > MAX_FILE_SIZE_BYTES:
        size_mb = file.size / (1024 * 1024)
        raise ValidationError(
            f"File size {size_mb:.1f} MB exceeds the 5 MB limit."
        )


def validate_resume_mime_type(file) -> None:
    """
    Validate MIME type by reading the actual file bytes (not trusting extension).
    Uses python-magic for content-based detection.

    Falls back to extension-based check if python-magic is unavailable.

    Raises:
        ValidationError: if MIME type is not in the allowed set.
    """
    try:
        import magic
        # Read first 2048 bytes — enough for MIME detection
        header = file.read(2048)
        file.seek(0)  # Reset pointer after reading
        detected_mime = magic.from_buffer(header, mime=True)

        if detected_mime not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                f"File content type '{detected_mime}' is not allowed. "
                f"Upload a valid PDF or DOCX file."
            )
    except ImportError:
        # python-magic not available — fall back to extension check
        logger.warning(
            "python-magic not installed. Falling back to extension-based MIME check."
        )
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in EXTENSION_TO_MIME:
            raise ValidationError(
                "Could not verify file type. Please upload a PDF or DOCX file."
            )


def validate_resume_file(file) -> None:
    """
    Run all resume validations in order:
      1. Extension check (fast)
      2. Size check (fast)
      3. MIME sniffing (reads file bytes)

    This is the single entry point called from serializers and services.

    Raises:
        ValidationError: on first failing check.
    """
    validate_resume_extension(file)
    validate_resume_size(file)
    validate_resume_mime_type(file)
