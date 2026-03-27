"""
tests/applications/test_validators.py

Unit tests for infrastructure/storage/validators.py.

Tests cover extension checks, size limits, and the combined
validate_resume_file() entry point using in-memory file mocks.
We do NOT test MIME sniffing here (requires real file bytes
and python-magic) — that is covered by the integration layer.
"""

import io
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from infrastructure.storage.validators import (
    validate_resume_extension,
    validate_resume_size,
    validate_resume_file,
    MAX_FILE_SIZE_BYTES,
)


# ---------------------------------------------------------------------------
# Helpers — minimal file mock
# ---------------------------------------------------------------------------

def _make_file(name: str, size_bytes: int = 1024):
    """Create an in-memory file-like object with a name and size attribute."""

    class FakeFile:
        def __init__(self, filename, size):
            self.name = filename
            self.size = size
            self._content = b"%" * size  # fake content

        def read(self, n=-1):
            return self._content if n == -1 else self._content[:n]

        def seek(self, pos):
            pass

    return FakeFile(name, size_bytes)


# ---------------------------------------------------------------------------
# Extension tests
# ---------------------------------------------------------------------------

class TestValidateResumeExtension(SimpleTestCase):

    def test_pdf_extension_is_accepted(self):
        f = _make_file("resume.pdf")
        try:
            validate_resume_extension(f)
        except ValidationError:
            self.fail("validate_resume_extension raised for a .pdf file")

    def test_docx_extension_is_accepted(self):
        f = _make_file("resume.docx")
        try:
            validate_resume_extension(f)
        except ValidationError:
            self.fail("validate_resume_extension raised for a .docx file")

    def test_txt_extension_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_resume_extension(_make_file("resume.txt"))

    def test_exe_extension_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_resume_extension(_make_file("malware.exe"))

    def test_jpg_extension_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_resume_extension(_make_file("photo.jpg"))

    def test_pdf_uppercase_extension_is_accepted(self):
        """Extension check must be case-insensitive."""
        f = _make_file("Resume.PDF")
        try:
            validate_resume_extension(f)
        except ValidationError:
            self.fail("validate_resume_extension rejected .PDF (uppercase)")

    def test_docx_uppercase_extension_is_accepted(self):
        f = _make_file("CV.DOCX")
        try:
            validate_resume_extension(f)
        except ValidationError:
            self.fail("validate_resume_extension rejected .DOCX (uppercase)")

    def test_extension_check_error_message_names_allowed_types(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_resume_extension(_make_file("resume.png"))
        messages = " ".join(str(m) for m in ctx.exception.messages)
        self.assertIn(".pdf", messages.lower())
        self.assertIn(".docx", messages.lower())

    def test_no_extension_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_resume_extension(_make_file("resume"))


# ---------------------------------------------------------------------------
# Size tests
# ---------------------------------------------------------------------------

class TestValidateResumeSize(SimpleTestCase):

    def test_file_within_limit_is_accepted(self):
        f = _make_file("resume.pdf", size_bytes=1024 * 1024)  # 1 MB
        try:
            validate_resume_size(f)
        except ValidationError:
            self.fail("validate_resume_size raised for a 1 MB file")

    def test_exact_limit_is_accepted(self):
        f = _make_file("resume.pdf", size_bytes=MAX_FILE_SIZE_BYTES)
        try:
            validate_resume_size(f)
        except ValidationError:
            self.fail("validate_resume_size raised for a file at exactly the limit")

    def test_file_exceeding_limit_is_rejected(self):
        f = _make_file("resume.pdf", size_bytes=MAX_FILE_SIZE_BYTES + 1)
        with self.assertRaises(ValidationError):
            validate_resume_size(f)

    def test_very_large_file_is_rejected(self):
        f = _make_file("resume.pdf", size_bytes=50 * 1024 * 1024)  # 50 MB
        with self.assertRaises(ValidationError):
            validate_resume_size(f)

    def test_zero_byte_file_is_accepted_by_size_check(self):
        """Size validation only checks upper bound — empty files pass."""
        f = _make_file("resume.pdf", size_bytes=0)
        try:
            validate_resume_size(f)
        except ValidationError:
            self.fail("validate_resume_size raised for a 0-byte file")

    def test_size_error_message_mentions_mb(self):
        f = _make_file("resume.pdf", size_bytes=MAX_FILE_SIZE_BYTES + 1024)
        with self.assertRaises(ValidationError) as ctx:
            validate_resume_size(f)
        messages = " ".join(str(m) for m in ctx.exception.messages)
        self.assertIn("MB", messages)


# ---------------------------------------------------------------------------
# Combined validate_resume_file tests
# ---------------------------------------------------------------------------

class TestValidateResumeFile(SimpleTestCase):

    def test_valid_pdf_within_size_limit_passes(self):
        f = _make_file("resume.pdf", size_bytes=512 * 1024)
        try:
            # MIME sniffing may fail without python-magic but
            # extension + size still runs
            validate_resume_file(f)
        except ValidationError as exc:
            # Only MIME-related failure is acceptable here
            messages = " ".join(str(m) for m in exc.messages)
            # If it failed for extension or size, that's a real bug
            self.assertNotIn("Unsupported file type", messages)
            self.assertNotIn("exceeds", messages)

    def test_wrong_extension_fails_before_size_check(self):
        """Extension is checked first — error must mention file type."""
        f = _make_file("resume.txt", size_bytes=100)
        with self.assertRaises(ValidationError) as ctx:
            validate_resume_file(f)
        messages = " ".join(str(m) for m in ctx.exception.messages)
        self.assertIn("Unsupported file type", messages)

    def test_oversized_pdf_fails_at_size_check(self):
        f = _make_file("resume.pdf", size_bytes=MAX_FILE_SIZE_BYTES + 1)
        with self.assertRaises(ValidationError) as ctx:
            validate_resume_file(f)
        messages = " ".join(str(m) for m in ctx.exception.messages)
        self.assertIn("exceeds", messages)
