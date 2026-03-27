"""
core/exceptions.py

Custom exception handler that enforces a consistent error envelope
across the entire API. Every error — validation, permission, not found —
returns the same shape so clients never have to guess.

Error shape:
{
    "error": true,
    "message": "Human-readable summary",
    "detail": <original detail — string, list, or dict>,
    "code": "error_code_string"
}
"""

import logging
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """
    Wraps DRF's default exception handler to enforce a consistent
    error envelope shape.
    """

    # Let DRF handle the initial conversion (Http404, PermissionDenied → APIException)
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception — log and return 500
        logger.exception(
            "Unhandled exception in view %s",
            context.get("view").__class__.__name__ if context.get("view") else "unknown",
            exc_info=exc,
        )
        return Response(
            _build_error_payload(
                message="An unexpected error occurred. Please try again later.",
                detail="internal_server_error",
                code="server_error",
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Re-shape the response
    detail = response.data

    # DRF ValidationError detail can be a dict, list, or string
    message = _extract_message(detail, exc)
    code = _extract_code(exc)

    response.data = _build_error_payload(
        message=message,
        detail=detail,
        code=code,
    )

    return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_error_payload(message: str, detail, code: str) -> dict:
    return {
        "error": True,
        "message": message,
        "detail": detail,
        "code": code,
    }


def _extract_message(detail, exc: Exception) -> str:
    """Pull a human-readable top-level message."""
    if isinstance(exc, ValidationError):
        return "Validation failed. Please check your input."
    if isinstance(exc, PermissionDenied):
        return "You do not have permission to perform this action."
    if isinstance(exc, Http404):
        return "The requested resource was not found."
    if isinstance(detail, dict) and "detail" in detail:
        return str(detail["detail"])
    if isinstance(detail, list) and detail:
        return str(detail[0])
    return str(detail)


def _extract_code(exc: Exception) -> str:
    """Pull the DRF error code if available."""
    if hasattr(exc, "default_code"):
        return exc.default_code
    if hasattr(exc, "detail") and hasattr(exc.detail, "code"):
        return exc.detail.code
    return "error"


# ---------------------------------------------------------------------------
# Custom application exceptions
# ---------------------------------------------------------------------------

class ApplicationError(APIException):
    """
    Base exception for domain-level errors raised in services.
    Raise this (or subclasses) from services.py — never from views.
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A business logic error occurred."
    default_code = "application_error"


class ConflictError(ApplicationError):
    """Raised when an action conflicts with current state (e.g., duplicate apply)."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict with current resource state."
    default_code = "conflict"


class ForbiddenError(ApplicationError):
    """Raised when a user attempts an action outside their role."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You are not allowed to perform this action."
    default_code = "forbidden"


class NotFoundError(ApplicationError):
    """Raised when a domain entity cannot be located."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found."
    default_code = "not_found"
