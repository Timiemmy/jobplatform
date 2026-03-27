"""
Health check endpoint for load balancers, Kubernetes probes,
and uptime monitors.

GET /health/

Returns 200 when all critical dependencies are reachable.
Returns 503 when any dependency is down.

Response shape:
{
    "status":   "healthy" | "degraded",
    "checks": {
        "database": "ok" | "error: <msg>",
        "redis":    "ok" | "error: <msg>",
        "celery":   "ok" | "error: <msg>"
    }
}

Never exposes internal error details in production.
"""

import logging
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    System health probe.

    Safe to call without authentication.
    Used by load balancers to route traffic away from unhealthy pods.
    """

    permission_classes  = [AllowAny]
    authentication_classes = []   # no auth overhead on health checks

    @extend_schema(
        responses={
            200: {"type": "object", "properties": {
                "status":  {"type": "string"},
                "checks":  {"type": "object"},
            }},
            503: {"type": "object"},
        },
        summary="System health check",
        tags=["Health"],
    )
    def get(self, request):
        checks   = {}
        healthy  = True

        # --- Database ---
        try:
            from django.db import connection
            connection.ensure_connection()
            checks["database"] = "ok"
        except Exception as exc:
            logger.error("Health check DB failure: %s", exc)
            checks["database"] = "error"
            healthy = False

        # --- Redis ---
        try:
            from django.core.cache import cache
            cache.set("health:ping", "pong", timeout=5)
            result = cache.get("health:ping")
            if result == "pong":
                checks["redis"] = "ok"
            else:
                checks["redis"] = "error"
                healthy = False
        except Exception as exc:
            logger.error("Health check Redis failure: %s", exc)
            checks["redis"] = "error"
            healthy = False

        # --- Celery (broker reachability) ---
        try:
            from infrastructure.tasks.celery import app as celery_app
            celery_app.control.ping(timeout=1)
            checks["celery"] = "ok"
        except Exception as exc:
            # Celery being down is degraded, not critical
            logger.warning("Health check Celery unreachable: %s", exc)
            checks["celery"] = "degraded"
            # Don't mark fully unhealthy — app can still serve reads

        http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(
            {
                "status": "healthy" if healthy else "degraded",
                "checks": checks,
            },
            status=http_status,
        )
