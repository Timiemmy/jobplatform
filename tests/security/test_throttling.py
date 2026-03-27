"""
tests/security/test_throttling.py

Tests that rate limiting is applied and returns 429
when limits are exceeded.

Uses DRF's SimpleRateThrottle cache key mechanism — each
test resets throttle state by clearing the cache.
"""

from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import make_job_seeker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_throttle_cache():
    """Clear all throttle counters between tests."""
    from django.core.cache import cache
    cache.clear()


# ---------------------------------------------------------------------------
# Login throttle
# ---------------------------------------------------------------------------

@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestLoginThrottle(TestCase):
    """
    LoginRateThrottle limits to 5/minute.
    We override the rate to 3/minute for test speed.
    """

    def setUp(self):
        _clear_throttle_cache()
        self.url  = reverse("accounts:login")
        self.user = make_job_seeker(email="throttle@test.com", password="StrongPass123!")

    @override_settings(
        REST_FRAMEWORK={
            **__import__("django.conf", fromlist=["settings"]).settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {
                "login":            "3/minute",
                "job_applications": "10/hour",
                "anon":             "1000/day",
                "user":             "1000/day",
            },
        }
    )
    def test_login_throttle_returns_429_after_limit(self):
        payload = {"email": "throttle@test.com", "password": "WrongPassword"}

        responses = [
            APIClient().post(self.url, payload, format="json")
            for _ in range(4)  # 1 over the 3/minute limit
        ]
        status_codes = [r.status_code for r in responses]

        # At least one must be 429
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, status_codes)

    def test_login_throttle_class_is_applied_to_view(self):
        """Verify LoginRateThrottle is wired onto the login view."""
        from api.v1.accounts.views import LoginView
        from core.throttles import LoginRateThrottle

        throttle_classes = [c.__name__ for c in LoginView.throttle_classes]
        self.assertIn(LoginRateThrottle.__name__, throttle_classes)


# ---------------------------------------------------------------------------
# Application throttle
# ---------------------------------------------------------------------------

@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class TestApplicationThrottle(TestCase):
    """
    JobApplicationRateThrottle limits to 10/hour.
    We verify the throttle class is wired — not simulate 10 applications
    (that would require 10 valid file uploads and job creations).
    """

    def test_application_throttle_class_is_on_post_handler(self):
        """ApplicationListCreateView must use JobApplicationRateThrottle on POST."""
        from api.v1.applications.views import ApplicationListCreateView
        from core.throttles import JobApplicationRateThrottle

        view = ApplicationListCreateView()
        # Simulate a POST request to trigger get_throttles()
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.post("/")

        # Wrap in DRF Request
        from rest_framework.request import Request
        drf_request        = Request(request)
        drf_request.user   = make_job_seeker(email="thr_app@test.com")
        view.request       = drf_request
        view.kwargs        = {}

        throttle_classes = [t.__class__ for t in view.get_throttles()]
        self.assertIn(JobApplicationRateThrottle, throttle_classes)

    def test_throttle_scope_is_job_applications(self):
        from core.throttles import JobApplicationRateThrottle
        self.assertEqual(JobApplicationRateThrottle.scope, "job_applications")

    def test_login_throttle_scope_is_login(self):
        from core.throttles import LoginRateThrottle
        self.assertEqual(LoginRateThrottle.scope, "login")


# ---------------------------------------------------------------------------
# Register throttle
# ---------------------------------------------------------------------------

class TestRegisterThrottle(TestCase):

    def test_register_view_uses_anon_burst_throttle(self):
        from api.v1.accounts.views import RegisterView
        from core.throttles import AnonBurstThrottle
        throttle_classes = [c.__name__ for c in RegisterView.throttle_classes]
        self.assertIn(AnonBurstThrottle.__name__, throttle_classes)
