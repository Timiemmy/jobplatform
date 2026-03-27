"""
tests/security/test_security_audit.py

End-to-end security audit test suite.

This module is the regression guard for the entire security surface.
Each test documents a specific security requirement and verifies it
holds across the full request/response cycle.

Categories:
    1. Authentication — unauthenticated access blocked
    2. Authorisation — role boundaries enforced
    3. Data exposure — sensitive fields never leak
    4. Input validation — malformed input rejected
    5. Security headers — response headers correct
    6. Token security — JWT expiry and blacklisting
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.applications.models import Application
from apps.jobs.models import Job
from tests.factories import (
    make_job_seeker,
    make_recruiter,
    make_admin,
    make_job,
    make_application,
)


def _auth_client(user) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


def _anon() -> APIClient:
    return APIClient()


# ---------------------------------------------------------------------------
# 1. Authentication — unauthenticated access
# ---------------------------------------------------------------------------

class TestUnauthenticatedBlocking(TestCase):
    """
    Every protected endpoint must return 401 for anonymous requests.
    No endpoint should silently degrade to 200 without authentication.
    """

    PROTECTED_ENDPOINTS = [
        ("GET",   "profiles:my-profile",      {}),
        ("PATCH", "profiles:my-profile",      {}),
        ("GET",   "applications:application-list-create", {}),
        ("POST",  "applications:application-list-create", {}),
        ("GET",   "jobs:my-jobs",             {}),
        ("POST",  "jobs:job-list-create",     {}),
        ("GET",   "accounts:user-detail",     {}),
        ("POST",  "accounts:logout",          {}),
    ]

    def test_all_protected_endpoints_block_anonymous(self):
        for method, url_name, kwargs in self.PROTECTED_ENDPOINTS:
            url      = reverse(url_name, kwargs=kwargs)
            response = getattr(_anon(), method.lower())(url, format="json")
            self.assertIn(
                response.status_code,
                [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                msg=f"{method} {url_name} returned {response.status_code} for anon — expected 401/403",
            )


class TestPublicEndpointsAccessible(TestCase):
    """
    Public endpoints must be reachable without a token.
    """

    def test_job_list_accessible_without_auth(self):
        make_job()
        response = _anon().get(reverse("jobs:job-list-create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_job_detail_accessible_without_auth(self):
        job      = make_job()
        response = _anon().get(reverse("jobs:job-detail", kwargs={"job_id": job.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_register_accessible_without_auth(self):
        response = _anon().post(reverse("accounts:register"), {}, format="json")
        # 400 (validation fail) not 401 — endpoint is reachable
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_accessible_without_auth(self):
        response = _anon().post(reverse("accounts:login"), {}, format="json")
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# 2. Authorisation — role boundary enforcement
# ---------------------------------------------------------------------------

class TestRoleBoundaryEnforcement(TestCase):
    """
    Critical cross-role access attempts must all be denied.
    """

    def setUp(self):
        self.seeker    = make_job_seeker(email="seeker@audit.com")
        self.recruiter = make_recruiter(email="recruiter@audit.com")
        self.other_rec = make_recruiter(email="other_rec@audit.com")
        self.job       = make_job(owner=self.recruiter)
        self.app       = make_application(applicant=self.seeker, job=self.job)

    # Seeker tries recruiter-only actions
    def test_seeker_cannot_create_job(self):
        response = _auth_client(self.seeker).post(
            reverse("jobs:job-list-create"),
            {"title": "x", "description": "y", "job_type": "full_time", "experience_level": "mid"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seeker_cannot_update_job(self):
        url      = reverse("jobs:job-detail", kwargs={"job_id": self.job.id})
        response = _auth_client(self.seeker).patch(url, {"title": "Hijack"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seeker_cannot_delete_job(self):
        url      = reverse("jobs:job-detail", kwargs={"job_id": self.job.id})
        response = _auth_client(self.seeker).delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seeker_cannot_update_application_status(self):
        url = reverse(
            "applications:application-status-update",
            kwargs={"application_id": self.app.id},
        )
        response = _auth_client(self.seeker).patch(url, {"status": "reviewed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_seeker_cannot_view_other_seekers_applications(self):
        other_seeker = make_job_seeker(email="other_seeker@audit.com")
        other_app    = make_application(applicant=other_seeker)
        url          = reverse(
            "applications:application-detail",
            kwargs={"application_id": other_app.id},
        )
        response = _auth_client(self.seeker).get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Recruiter tries seeker-only actions
    def test_recruiter_cannot_apply_to_job(self):
        import io
        f    = io.BytesIO(b"%PDF fake")
        f.name = "r.pdf"
        response = _auth_client(self.recruiter).post(
            reverse("applications:application-list-create"),
            {"job_id": str(self.job.id), "resume": f},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_recruiter_cannot_view_own_application_list(self):
        """Applications list is seeker-only."""
        response = _auth_client(self.recruiter).get(
            reverse("applications:application-list-create")
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # Non-owner recruiter tries to access another's resources
    def test_non_owner_cannot_update_job(self):
        url      = reverse("jobs:job-detail", kwargs={"job_id": self.job.id})
        response = _auth_client(self.other_rec).patch(url, {"title": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_cannot_view_applicants(self):
        url      = reverse("job-applicants", kwargs={"job_id": self.job.id})
        response = _auth_client(self.other_rec).get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_owner_cannot_update_application_status(self):
        url = reverse(
            "applications:application-status-update",
            kwargs={"application_id": self.app.id},
        )
        response = _auth_client(self.other_rec).patch(url, {"status": "reviewed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# 3. Data exposure — sensitive fields
# ---------------------------------------------------------------------------

class TestSensitiveFieldExposure(TestCase):
    """
    Passwords, resume paths, recruiter notes, and internal fields
    must NEVER appear in any API response.
    """

    NEVER_EXPOSE = [
        "password",
        "resume_path",
        "recruiter_notes",
        "is_superuser",
        "is_staff",
        "user_permissions",
        "groups",
    ]

    def _assert_no_sensitive_fields(self, response, context=""):
        payload_str = str(response.data)
        for field in self.NEVER_EXPOSE:
            self.assertNotIn(
                f'"{field}"',
                payload_str,
                msg=f"Sensitive field '{field}' found in response [{context}]",
            )

    def test_register_response_has_no_sensitive_fields(self):
        response = _anon().post(
            reverse("accounts:register"),
            {
                "email":            "reg_audit@test.com",
                "password":         "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "first_name":       "Test",
                "last_name":        "User",
                "role":             "job_seeker",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self._assert_no_sensitive_fields(response, "register")

    def test_login_response_has_no_sensitive_fields(self):
        make_job_seeker(email="login_audit@test.com", password="StrongPass123!")
        response = _anon().post(
            reverse("accounts:login"),
            {"email": "login_audit@test.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._assert_no_sensitive_fields(response, "login")

    def test_user_detail_response_has_no_sensitive_fields(self):
        user     = make_job_seeker(email="detail_audit@test.com")
        response = _auth_client(user).get(reverse("accounts:user-detail"))
        self._assert_no_sensitive_fields(response, "user-detail")

    def test_profile_response_has_no_sensitive_fields(self):
        user     = make_job_seeker(email="profile_audit@test.com")
        response = _auth_client(user).get(reverse("profiles:my-profile"))
        self._assert_no_sensitive_fields(response, "profile")

    def test_job_list_never_exposes_recruiter_email(self):
        recruiter = make_recruiter(email="secret_rec@audit.com")
        make_job(owner=recruiter)
        response  = _anon().get(reverse("jobs:job-list-create"))
        self.assertNotIn("secret_rec@audit.com", str(response.data))

    def test_job_detail_never_exposes_recruiter_email(self):
        recruiter = make_recruiter(email="secret_rec2@audit.com")
        job       = make_job(owner=recruiter)
        response  = _anon().get(reverse("jobs:job-detail", kwargs={"job_id": job.id}))
        self.assertNotIn("secret_rec2@audit.com", str(response.data))

    def test_applicant_list_never_exposes_applicant_email(self):
        recruiter = make_recruiter(email="r_audit@test.com")
        seeker    = make_job_seeker(email="hidden_applicant@audit.com")
        job       = make_job(owner=recruiter)
        make_application(applicant=seeker, job=job)

        response = _auth_client(recruiter).get(
            reverse("job-applicants", kwargs={"job_id": job.id})
        )
        self.assertNotIn("hidden_applicant@audit.com", str(response.data))

    def test_application_detail_never_exposes_resume_path(self):
        seeker = make_job_seeker(email="path_audit@test.com")
        app    = make_application(
            applicant=seeker,
            resume_path="resumes/private/secret/path.pdf",
        )
        url      = reverse("applications:application-detail", kwargs={"application_id": app.id})
        response = _auth_client(seeker).get(url)
        self.assertNotIn("resume_path", str(response.data))
        self.assertNotIn("secret/path.pdf", str(response.data))

    def test_seeker_cannot_see_recruiter_notes(self):
        recruiter = make_recruiter(email="notes_r@audit.com")
        seeker    = make_job_seeker(email="notes_s@audit.com")
        job       = make_job(owner=recruiter)
        app       = make_application(applicant=seeker, job=job)

        app.recruiter_notes = "Weak candidate — do not proceed."
        app.save(update_fields=["recruiter_notes"])

        url      = reverse("applications:application-detail", kwargs={"application_id": app.id})
        response = _auth_client(seeker).get(url)
        self.assertNotIn("recruiter_notes",               str(response.data))
        self.assertNotIn("Weak candidate",                str(response.data))


# ---------------------------------------------------------------------------
# 4. Input validation
# ---------------------------------------------------------------------------

class TestInputValidation(TestCase):
    """
    Malformed or dangerous input must be rejected with 400.
    """

    def test_registration_rejects_invalid_email(self):
        response = _anon().post(
            reverse("accounts:register"),
            {"email": "not-an-email", "password": "StrongPass123!", "role": "job_seeker"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_rejects_weak_password(self):
        response = _anon().post(
            reverse("accounts:register"),
            {"email": "weak@test.com", "password": "123", "password_confirm": "123",
             "first_name": "A", "last_name": "B", "role": "job_seeker"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_rejects_mismatched_passwords(self):
        response = _anon().post(
            reverse("accounts:register"),
            {"email": "mm@test.com", "password": "StrongPass123!",
             "password_confirm": "Different!", "first_name": "A", "last_name": "B",
             "role": "job_seeker"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_blocks_admin_self_assignment(self):
        response = _anon().post(
            reverse("accounts:register"),
            {"email": "admin@test.com", "password": "StrongPass123!",
             "password_confirm": "StrongPass123!", "first_name": "A",
             "last_name": "B", "role": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_job_create_rejects_short_description(self):
        recruiter = make_recruiter(email="short_desc@audit.com")
        response  = _auth_client(recruiter).post(
            reverse("jobs:job-list-create"),
            {"title": "Role", "description": "Too short.", "job_type": "full_time",
             "experience_level": "mid"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_job_create_rejects_inverted_salary(self):
        recruiter = make_recruiter(email="inv_sal@audit.com")
        response  = _auth_client(recruiter).post(
            reverse("jobs:job-list-create"),
            {"title": "Role",
             "description": "We are hiring a senior engineer to build scalable systems "
                            "and APIs. You will work on challenging distributed problems.",
             "job_type": "full_time", "experience_level": "mid",
             "salary_min": "100000", "salary_max": "50000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_application_status_rejects_unknown_value(self):
        recruiter = make_recruiter(email="stat_val@audit.com")
        seeker    = make_job_seeker(email="stat_s@audit.com")
        job       = make_job(owner=recruiter)
        app       = make_application(applicant=seeker, job=job)
        url       = reverse("applications:application-status-update",
                            kwargs={"application_id": app.id})
        response  = _auth_client(recruiter).patch(url, {"status": "flying"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_application_status_rejects_illegal_transition(self):
        recruiter = make_recruiter(email="ill_tran@audit.com")
        seeker    = make_job_seeker(email="ill_s@audit.com")
        job       = make_job(owner=recruiter)
        app       = make_application(applicant=seeker, job=job)
        # applied → hired is illegal (must go through reviewed → interview first)
        url       = reverse("applications:application-status-update",
                            kwargs={"application_id": app.id})
        response  = _auth_client(recruiter).patch(url, {"status": "hired"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_rejects_invalid_url(self):
        seeker   = make_job_seeker(email="url_val@audit.com")
        response = _auth_client(seeker).patch(
            reverse("profiles:my-profile"),
            {"avatar_url": "not-a-url"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 5. Security headers
# ---------------------------------------------------------------------------

class TestSecurityHeaders(TestCase):
    """
    Every response must carry the correct security headers.
    """

    def _get_response(self):
        make_job()
        return _anon().get(reverse("jobs:job-list-create"))

    def test_x_content_type_options_present(self):
        response = self._get_response()
        self.assertEqual(response.get("X-Content-Type-Options"), "nosniff")

    def test_x_request_id_present(self):
        response = self._get_response()
        self.assertIn("X-Request-ID", response)

    def test_x_request_id_is_valid_uuid(self):
        import uuid
        response = self._get_response()
        try:
            uuid.UUID(response["X-Request-ID"])
        except (ValueError, KeyError):
            self.fail("X-Request-ID is missing or not a valid UUID")

    def test_server_header_not_exposed(self):
        response = self._get_response()
        # Server header must not leak Django/Python version info
        server = response.get("Server", "")
        self.assertNotIn("Python", server)
        self.assertNotIn("Django", server)


# ---------------------------------------------------------------------------
# 6. JWT token security
# ---------------------------------------------------------------------------

class TestJWTSecurity(TestCase):
    """
    Access tokens must expire. Blacklisted refresh tokens must be rejected.
    """

    def test_invalid_access_token_returns_401(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.here")
        response = client.get(reverse("accounts:user-detail"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blacklisted_refresh_cannot_generate_new_access(self):
        user    = make_job_seeker(email="blacklist@audit.com")
        refresh = RefreshToken.for_user(user)
        client  = _auth_client(user)

        # Logout — blacklists the token
        client.post(
            reverse("accounts:logout"),
            {"refresh": str(refresh)},
            format="json",
        )

        # Attempt to get a new access token with the blacklisted refresh
        response = _anon().post(
            reverse("accounts:token-refresh"),
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tampered_token_returns_401(self):
        user    = make_job_seeker(email="tamper@audit.com")
        refresh = RefreshToken.for_user(user)
        # Tamper with last character of access token signature
        access       = str(refresh.access_token)
        tampered     = access[:-1] + ("X" if access[-1] != "X" else "Y")
        client       = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tampered}")
        response     = client.get(reverse("accounts:user-detail"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_error_response_has_consistent_shape(self):
        """All error responses — including auth failures — must use the standard envelope."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer bad.token")
        response = client.get(reverse("accounts:user-detail"))
        self.assertIn("error",   response.data)
        self.assertIn("message", response.data)
        self.assertIn("detail",  response.data)
        self.assertIn("code",    response.data)
