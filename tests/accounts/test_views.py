"""
tests/accounts/test_views.py

Integration tests for the accounts API endpoints.
Tests go through the full Django request/response cycle.

Endpoints covered:
    POST /api/v1/auth/register/
    POST /api/v1/auth/login/
    POST /api/v1/auth/logout/
    POST /api/v1/auth/token/refresh/
    GET  /api/v1/auth/user/
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from tests.factories import make_job_seeker, make_recruiter, make_user


class TestRegisterView(TestCase):
    """POST /api/v1/auth/register/"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:register")

    def _valid_payload(self, **overrides) -> dict:
        data = {
            "email": "newuser@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "first_name": "Jane",
            "last_name": "Doe",
            "role": User.Role.JOB_SEEKER,
        }
        data.update(overrides)
        return data

    def test_successful_registration_returns_201(self):
        response = self.client.post(self.url, self._valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_response_contains_access_and_refresh_tokens(self):
        response = self.client.post(self.url, self._valid_payload(), format="json")
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_response_contains_user_object(self):
        response = self.client.post(self.url, self._valid_payload(), format="json")
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], "newuser@example.com")
        self.assertEqual(response.data["user"]["role"], User.Role.JOB_SEEKER)

    def test_response_does_not_expose_password(self):
        response = self.client.post(self.url, self._valid_payload(), format="json")
        self.assertNotIn("password", response.data)
        self.assertNotIn("password", response.data.get("user", {}))

    def test_recruiter_registration_succeeds(self):
        payload = self._valid_payload(
            email="recruiter@example.com",
            role=User.Role.RECRUITER,
        )
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], User.Role.RECRUITER)

    def test_admin_role_is_rejected(self):
        payload = self._valid_payload(role=User.Role.ADMIN)
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_email_returns_400(self):
        make_user(email="newuser@example.com")
        response = self.client.post(self.url, self._valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mismatched_passwords_returns_400(self):
        payload = self._valid_payload(password_confirm="WrongPassword!")
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_email_returns_400(self):
        payload = self._valid_payload()
        del payload["email"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password_returns_400(self):
        payload = self._valid_payload(password="123", password_confirm="123")
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_email_format_returns_400(self):
        payload = self._valid_payload(email="not-an-email")
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_error_response_shape_is_consistent(self):
        """All error responses must use the standard error envelope."""
        payload = self._valid_payload(email="not-an-email")
        response = self.client.post(self.url, payload, format="json")
        self.assertIn("error", response.data)
        self.assertIn("message", response.data)
        self.assertIn("detail", response.data)
        self.assertIn("code", response.data)
        self.assertTrue(response.data["error"])


class TestLoginView(TestCase):
    """POST /api/v1/auth/login/"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:login")
        self.user = make_job_seeker(
            email="login@example.com",
            password="StrongPass123!",
        )

    def test_valid_credentials_return_200(self):
        response = self.client.post(
            self.url,
            {"email": "login@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_token_pair(self):
        response = self.client.post(
            self.url,
            {"email": "login@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_response_contains_user_data(self):
        response = self.client.post(
            self.url,
            {"email": "login@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], "login@example.com")

    def test_wrong_password_returns_400(self):
        response = self.client.post(
            self.url,
            {"email": "login@example.com", "password": "WrongPassword!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_email_returns_400(self):
        response = self.client.post(
            self.url,
            {"email": "nobody@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_user_cannot_login(self):
        inactive = make_user(
            email="inactive@example.com",
            password="StrongPass123!",
            is_active=False,
        )
        response = self.client.post(
            self.url,
            {"email": inactive.email, "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_email_returns_400(self):
        response = self.client.post(
            self.url,
            {"password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_does_not_expose_password(self):
        response = self.client.post(
            self.url,
            {"email": "login@example.com", "password": "StrongPass123!"},
            format="json",
        )
        response_str = str(response.data)
        self.assertNotIn("StrongPass123!", response_str)


class TestLogoutView(TestCase):
    """POST /api/v1/auth/logout/"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:logout")
        self.user = make_job_seeker(email="logout@example.com", password="StrongPass123!")
        self.refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(self.refresh.access_token)}"
        )

    def test_logout_with_valid_token_returns_204(self):
        response = self.client.post(
            self.url,
            {"refresh": str(self.refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_blacklisted_refresh_token_cannot_be_used_again(self):
        # Blacklist via logout
        self.client.post(
            self.url,
            {"refresh": str(self.refresh)},
            format="json",
        )

        # Attempt to refresh — must be rejected
        refresh_url = reverse("accounts:token-refresh")
        response = self.client.post(
            refresh_url,
            {"refresh": str(self.refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_request_returns_401(self):
        self.client.credentials()  # remove auth header
        response = self.client.post(
            self.url,
            {"refresh": str(self.refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_refresh_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_refresh_token_returns_401(self):
        response = self.client.post(
            self.url,
            {"refresh": "this.is.not.a.valid.token"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestTokenRefreshView(TestCase):
    """POST /api/v1/auth/token/refresh/"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:token-refresh")
        self.user = make_job_seeker(email="refresh@example.com", password="StrongPass123!")
        self.refresh = RefreshToken.for_user(self.user)

    def test_valid_refresh_token_returns_new_access_token(self):
        response = self.client.post(
            self.url,
            {"refresh": str(self.refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_rotated_refresh_token_is_returned(self):
        """ROTATE_REFRESH_TOKENS=True means a new refresh token is issued."""
        response = self.client.post(
            self.url,
            {"refresh": str(self.refresh)},
            format="json",
        )
        self.assertIn("refresh", response.data)
        # The new refresh token must differ from the original
        self.assertNotEqual(response.data["refresh"], str(self.refresh))

    def test_invalid_token_returns_401(self):
        response = self.client.post(
            self.url,
            {"refresh": "bad.token.here"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestUserDetailView(TestCase):
    """GET /api/v1/auth/user/"""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:user-detail")
        self.user = make_job_seeker(
            email="me@example.com",
            first_name="Alice",
            last_name="Smith",
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
        )

    def test_authenticated_user_gets_own_data(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "me@example.com")
        self.assertEqual(response.data["first_name"], "Alice")
        self.assertEqual(response.data["role"], User.Role.JOB_SEEKER)

    def test_response_contains_expected_fields(self):
        response = self.client.get(self.url)
        expected_fields = {"id", "email", "first_name", "last_name", "role", "is_active", "created_at"}
        self.assertEqual(set(response.data.keys()), expected_fields)

    def test_response_does_not_expose_password(self):
        response = self.client.get(self.url)
        self.assertNotIn("password", response.data)

    def test_response_does_not_expose_is_superuser(self):
        response = self.client.get(self.url)
        self.assertNotIn("is_superuser", response.data)

    def test_unauthenticated_request_returns_401(self):
        self.client.credentials()  # strip auth header
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_access_token_returns_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer expiredtoken.bad.sig")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
