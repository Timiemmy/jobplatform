"""
config/urls.py

Root URL configuration.

All API traffic routes through /api/v1/.
Future versions add /api/v2/ here — nothing in v1 changes.
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from core.health import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Health check — no auth, used by load balancers
    path("health/", HealthCheckView.as_view(), name="health-check"),

    # Versioned API
    path("api/v1/", include("api.v1.urls")),

    # OpenAPI schema + docs
    path("api/schema/",  SpectacularAPIView.as_view(),                        name="schema"),
    path("api/docs/",    SpectacularSwaggerView.as_view(url_name="schema"),   name="swagger-ui"),
    path("api/redoc/",   SpectacularRedocView.as_view(url_name="schema"),     name="redoc"),
]
