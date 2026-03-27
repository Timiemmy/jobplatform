"""
core/logging.py

Structured JSON log formatter for production.

Every log line is a valid JSON object, making it directly
ingestible by Datadog, CloudWatch, Loki, or any log aggregator.

Fields emitted per record:
    timestamp   ISO-8601 UTC timestamp
    level       DEBUG / INFO / WARNING / ERROR / CRITICAL
    logger      Logger name (e.g. "apps.jobs.services")
    message     Log message
    module      Python module name
    line        Line number
    request_id  X-Request-ID header if present (via middleware)
    exc_info    Exception traceback if applicable
"""

import json
import logging
import traceback
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Formats every log record as a single JSON line.
    Safe for high-throughput — no external dependencies.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level":    record.levelname,
            "logger":   record.name,
            "module":   record.module,
            "line":     record.lineno,
            "message":  record.getMessage(),
        }

        # Attach request_id if injected by RequestIDMiddleware
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        # Attach exception details if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str)
