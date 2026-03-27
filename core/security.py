"""
core/security.py

Security utilities used across the platform.

sanitize_string()       Strip null bytes and control characters from
                        user-supplied strings before they reach the DB.
                        DRF serializers call this on text fields.

mask_email()            One-way mask for logging — never log raw emails.

assert_no_sensitive_fields()
                        Dev-time assertion that a serializer's fields
                        don't include names from the SENSITIVE_FIELDS set.
                        Called from serializer __init__ in debug mode.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Fields that must never appear in any outbound API response
SENSITIVE_FIELDS = frozenset({
    "password",
    "password_hash",
    "resume_path",
    "recruiter_notes",
    "is_superuser",
    "is_staff",
    "user_permissions",
    "groups",
    "aws_access_key",
    "aws_secret_key",
})

# Control characters except TAB, LF, CR
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_string(value: str) -> str:
    """
    Remove null bytes and dangerous control characters from a string.

    Protects against:
      - Null byte injection (PostgreSQL truncation attacks)
      - Control character injection in log output

    Safe to call on any user-supplied text. Does not HTML-encode —
    DRF + Django ORM handle SQL injection; this handles byte-level attacks.
    """
    if not isinstance(value, str):
        return value
    return _CONTROL_CHAR_RE.sub("", value)


def mask_email(email: str) -> str:
    """
    Partially mask an email for safe logging.
    e.g. "alice@example.com" → "al***@example.com"

    Never log a raw email address — use this in all log statements
    that reference user identity.
    """
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    visible = local[:2] if len(local) >= 2 else local[:1]
    return f"{visible}***@{domain}"


def assert_no_sensitive_fields(field_names: list[str], serializer_name: str) -> None:
    """
    Assert that a serializer's field list contains no sensitive fields.

    Called during development to catch accidental data exposure before
    it reaches production. No-op in production (guard with DEBUG check).

    Usage in a serializer:
        from django.conf import settings
        if settings.DEBUG:
            assert_no_sensitive_fields(list(self.fields), self.__class__.__name__)
    """
    leaked = SENSITIVE_FIELDS & set(field_names)
    if leaked:
        raise AssertionError(
            f"Serializer '{serializer_name}' exposes sensitive fields: {sorted(leaked)}. "
            "Remove them from the fields list."
        )
