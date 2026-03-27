"""
tests/accounts/test_permissions.py

Permission matrix tests for Phase 1 endpoints.

For every endpoint, we test:
  - Anonymous user     → expected status
  - Job seeker         → expected status
  - Recruiter          → expected status
  - Admin              → expected status

This is the canonical place to catch permission regressions.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import make_job_seeker, make_recruiter, make_admin


def _auth_client(user) -> APIClient:
    """Return an APIClient with a valid JWT for the given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


def _anon_client() -> APIClient:
    """Return an unauthenticated APIClient."""
    return APIClient()


class TestRegisterEndpointPermissions(TestCase):
    """POST /api/v1/auth/register/ — open to all, no auth required."""

    def setUp(self):
        self.url = reverse("accounts:register")
        self.valid_payload = {
            "email": "matrix@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "job_seeker",
        }

    def test_anonymous_user_can_register(self):
        response = _anon_client().post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TestLoginEndpointPermissions(TestCase):
    """POST /api/v1/auth/login/ — open to all."""

    def setUp(self):
        self.url = reverse("accounts:login")
        self.user = make_job_seeker(email="loginperm@example.com", password="StrongPass123!")

    def test_anonymous_user_can_login(self):
        response = _anon_client().post(
            self.url,
            {"email": "loginperm@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_already_authenticated_user_can_also_call_login(self):
        """Login endpoint is AllowAny — authenticated users aren't blocked."""
        client = _auth_client(self.user)
        response = client.post(
            self.url,
            {"email": "loginperm@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestLogoutEndpointPermissions(TestCase):
    """POST /api/v1/auth/logout/ — requires authentication."""

    def setUp(self):
        self.url = reverse("accounts:logout")

    def test_anonymous_cannot_logout(self):
        response = _anon_client().post(self.url, {"refresh": "fake"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_job_seeker_can_logout(self):
        user = make_job_seeker(email="seeker_logout@example.com")
        refresh = RefreshToken.for_user(user)
        client = _auth_client(user)
        response = client.post(self.url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_recruiter_can_logout(self):
        user = make_recruiter(email="recruiter_logout@example.com")
        refresh = RefreshToken.for_user(user)
        client = _auth_client(user)
        response = client.post(self.url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_can_logout(self):
        user = make_admin(email="admin_logout@example.com")
        refresh = RefreshToken.for_user(user)
        client = _auth_client(user)
        response = client.post(self.url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestUserDetailEndpointPermissions(TestCase):
    """GET /api/v1/auth/user/ — requires authentication, any role."""

    def setUp(self):
        self.url = reverse("accounts:user-detail")

    def test_anonymous_cannot_access(self):
        response = _anon_client().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_job_seeker_can_access_own_data(self):
        user = make_job_seeker(email="seeker_detail@example.com")
        response = _auth_client(user).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], user.email)

    def test_recruiter_can_access_own_data(self):
        user = make_recruiter(email="recruiter_detail@example.com")
        response = _auth_client(user).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_access_own_data(self):
        user = make_admin(email="admin_detail@example.com")
        response = _auth_client(user).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_detail_view_returns_only_own_data(self):
        """
        Critical: a user must only see their own data from this endpoint.
        The response must always reflect request.user, never another user.
        """
        user_a = make_job_seeker(email="user_a@example.com")
        user_b = make_job_seeker(email="user_b@example.com")

        # user_a's client
        response = _auth_client(user_a).get(self.url)
        self.assertEqual(response.data["email"], user_a.email)
        self.assertNotEqual(response.data["email"], user_b.email)


class TestTokenRefreshEndpointPermissions(TestCase):
    """POST /api/v1/auth/token/refresh/ — open, requires a valid refresh token."""

    def setUp(self):
        self.url = reverse("accounts:token-refresh")

    def test_anonymous_with_valid_refresh_token_succeeds(self):
        user = make_job_seeker(email="refresh_perm@example.com")
        refresh = RefreshToken.for_user(user)
        response = _anon_client().post(
            self.url, {"refresh": str(refresh)}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_no_token_returns_401(self):
        response = _anon_client().post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
