"""
core/middleware.py

Production-grade middleware stack.

RequestIDMiddleware     — stamps every request with a UUID, propagates to
                          logs and response headers for tracing.
SecurityHeadersMiddleware — strips server fingerprinting headers,
                            adds additional security headers beyond
                            what Django's SecurityMiddleware provides.
"""

import logging
import uuid

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    """
    Assigns a unique UUID to every inbound request.

    The ID is:
      - Stored on request.request_id for downstream use.
      - Injected into the log record via a custom filter so every log
        line emitted during that request carries the same ID.
      - Returned in the X-Request-ID response header.

    Clients can supply their own X-Request-ID and it will be honoured
    (useful for end-to-end tracing with an API gateway).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Honour client-supplied ID if present and looks like a UUID
        client_id = request.META.get("HTTP_X_REQUEST_ID", "").strip()
        try:
            request_id = str(uuid.UUID(client_id))
        except (ValueError, AttributeError):
            request_id = str(uuid.uuid4())

        request.request_id = request_id

        # Inject into logging context for this thread
        _request_id_filter.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class _RequestIDFilter(logging.Filter):
    """
    Logging filter that injects request_id into every LogRecord
    emitted during the current request.
    """

    def __init__(self):
        super().__init__()
        self.request_id = "-"

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self.request_id
        return True


# Singleton filter — registered once, mutated per request
_request_id_filter = _RequestIDFilter()

# Register the filter on the root logger so all loggers inherit it
logging.getLogger().addFilter(_request_id_filter)


class SecurityHeadersMiddleware:
    """
    Adds security headers that Django's built-in SecurityMiddleware
    does not cover, and strips server fingerprinting headers.

    Headers added:
        Permissions-Policy          Disables browser APIs not needed
        Cross-Origin-Opener-Policy  Isolates browsing context
        Cross-Origin-Resource-Policy  Restricts cross-origin reads
    """

    _REMOVE_HEADERS = frozenset(["Server", "X-Powered-By"])

    _ADD_HEADERS = {
        "Permissions-Policy":           "geolocation=(), microphone=(), camera=()",
        "Cross-Origin-Opener-Policy":   "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "X-Content-Type-Options":       "nosniff",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        for header in self._REMOVE_HEADERS:
            if header in response:
                del response[header]

        for header, value in self._ADD_HEADERS.items():
            response.setdefault(header, value)

        return response
