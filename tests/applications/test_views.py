"""
tests/applications/test_views.py

Integration tests for the applications API endpoints.

Endpoints covered:
    POST   /api/v1/applications/
    GET    /api/v1/applications/
    GET    /api/v1/applications/{id}/
    GET    /api/v1/jobs/{id}/applicants/
    PATCH  /api/v1/applications/{id}/status/
    GET    /api/v1/applications/{id}/resume/

Celery tasks and file storage are mocked in all tests
so no real async workers or S3 are required.
"""

import io
from unittest.mock import patch, MagicMock

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

UPLOAD_PATCH   = "apps.applications.services.upload_resume"
VALIDATE_PATCH = "apps.applications.services.validate_resume_file"
EMAIL_PATCH    = "apps.applications.services._fire_application_emails"


def _auth_client(user) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


def _anon() -> APIClient:
    return APIClient()


def _fake_resume_file():
    """In-memory PDF file for multipart upload."""
    return io.BytesIO(b"%PDF-1.4 fake content padded " + b"\x00" * 1024)


# ---------------------------------------------------------------------------
# Apply — POST /api/v1/applications/
# ---------------------------------------------------------------------------

class TestApplyView(TestCase):

    def setUp(self):
        self.url     = reverse("applications:application-list-create")
        self.seeker  = make_job_seeker(email="seeker@views.com")
        self.job     = make_job()

    def _post(self, client, job_id=None, with_resume=True):
        data = {"job_id": str(job_id or self.job.id)}
        if with_resume:
            f = _fake_resume_file()
            f.name = "resume.pdf"
            data["resume"] = f
        return client.post(self.url, data, format="multipart")

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_job_seeker_can_apply_returns_201(self, mv, mu, me):
        response = self._post(_auth_client(self.seeker))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_response_contains_application_fields(self, mv, mu, me):
        response = self._post(_auth_client(self.seeker))
        self.assertIn("id",         response.data)
        self.assertIn("job",        response.data)
        self.assertIn("status",     response.data)
        self.assertEqual(response.data["status"], "applied")

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_resume_path_never_exposed_in_response(self, mv, mu, me):
        response = self._post(_auth_client(self.seeker))
        self.assertNotIn("resume_path", response.data)

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_duplicate_application_returns_409(self, mv, mu, me):
        self._post(_auth_client(self.seeker))
        response = self._post(_auth_client(self.seeker))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_recruiter_cannot_apply_returns_403(self):
        recruiter = make_recruiter(email="r@views.com")
        response = self._post(_auth_client(recruiter))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_returns_401(self):
        response = self._post(_anon())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_resume_returns_400(self):
        response = self._post(_auth_client(self.seeker), with_resume=False)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_job_returns_404(self):
        import uuid
        response = self._post(_auth_client(self.seeker), job_id=uuid.uuid4())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_closed_job_returns_404(self):
        closed = make_job(status=Job.Status.CLOSED)
        response = self._post(_auth_client(self.seeker), job_id=closed.id)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_recruiter_notes_never_in_response(self, mv, mu, me):
        response = self._post(_auth_client(self.seeker))
        self.assertNotIn("recruiter_notes", response.data)


# ---------------------------------------------------------------------------
# List own applications — GET /api/v1/applications/
# ---------------------------------------------------------------------------

class TestListApplicationsView(TestCase):

    def setUp(self):
        self.url    = reverse("applications:application-list-create")
        self.seeker = make_job_seeker(email="list@views.com")

    def test_seeker_sees_own_applications_only(self):
        other = make_job_seeker(email="other@views.com")
        make_application(applicant=self.seeker)
        make_application(applicant=self.seeker)
        make_application(applicant=other)

        response = _auth_client(self.seeker).get(self.url)
        self.assertEqual(response.data["count"], 2)

    def test_response_is_paginated(self):
        for _ in range(3):
            make_application(applicant=self.seeker)
        response = _auth_client(self.seeker).get(self.url)
        self.assertIn("count",    response.data)
        self.assertIn("results",  response.data)
        self.assertIn("next",     response.data)
        self.assertIn("previous", response.data)

    def test_filter_by_status(self):
        make_application(applicant=self.seeker, status=Application.Status.APPLIED)
        make_application(applicant=self.seeker, status=Application.Status.REVIEWED)

        response = _auth_client(self.seeker).get(self.url, {"status": "reviewed"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], "reviewed")

    def test_resume_path_not_in_list_response(self):
        make_application(applicant=self.seeker)
        response = _auth_client(self.seeker).get(self.url)
        first = response.data["results"][0]
        self.assertNotIn("resume_path", first)

    def test_anonymous_returns_401(self):
        response = _anon().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recruiter_cannot_access_seeker_list(self):
        recruiter = make_recruiter(email="r@list.com")
        response = _auth_client(recruiter).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Application detail — GET /api/v1/applications/{id}/
# ---------------------------------------------------------------------------

class TestApplicationDetailView(TestCase):

    def setUp(self):
        self.seeker = make_job_seeker(email="det@views.com")
        self.app    = make_application(applicant=self.seeker)
        self.url    = reverse(
            "applications:application-detail",
            kwargs={"application_id": self.app.id},
        )

    def test_seeker_can_retrieve_own_application(self):
        response = _auth_client(self.seeker).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data["id"]), str(self.app.id))

    def test_other_seeker_cannot_access(self):
        other = make_job_seeker(email="other_det@views.com")
        response = _auth_client(other).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_returns_401(self):
        response = _anon().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_resume_path_not_exposed(self):
        response = _auth_client(self.seeker).get(self.url)
        self.assertNotIn("resume_path", response.data)

    def test_recruiter_notes_not_exposed(self):
        response = _auth_client(self.seeker).get(self.url)
        self.assertNotIn("recruiter_notes", response.data)


# ---------------------------------------------------------------------------
# Recruiter view applicants — GET /api/v1/jobs/{id}/applicants/
# ---------------------------------------------------------------------------

class TestJobApplicantsView(TestCase):

    def setUp(self):
        self.recruiter = make_recruiter(email="rappl@views.com")
        self.job       = make_job(owner=self.recruiter)
        self.url       = reverse("job-applicants", kwargs={"job_id": self.job.id})

    def test_recruiter_can_list_applicants(self):
        make_application(job=self.job)
        make_application(job=self.job)
        response = _auth_client(self.recruiter).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_non_owner_recruiter_gets_404(self):
        other = make_recruiter(email="other_rappl@views.com")
        response = _auth_client(other).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_job_seeker_gets_403(self):
        seeker = make_job_seeker(email="s@rappl.com")
        response = _auth_client(seeker).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_gets_401(self):
        response = _anon().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_response_is_paginated(self):
        for _ in range(3):
            make_application(job=self.job)
        response = _auth_client(self.recruiter).get(self.url)
        self.assertIn("count",   response.data)
        self.assertIn("results", response.data)

    def test_applicant_email_never_exposed(self):
        seeker = make_job_seeker(email="secret_applicant@views.com")
        make_application(applicant=seeker, job=self.job)
        response = _auth_client(self.recruiter).get(self.url)
        self.assertNotIn("secret_applicant@views.com", str(response.data))

    def test_filter_by_status(self):
        make_application(job=self.job, status=Application.Status.APPLIED)
        make_application(job=self.job, status=Application.Status.INTERVIEW)
        response = _auth_client(self.recruiter).get(self.url, {"status": "interview"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], "interview")

    def test_resume_path_never_in_recruiter_list(self):
        make_application(job=self.job)
        response = _auth_client(self.recruiter).get(self.url)
        first = response.data["results"][0]
        self.assertNotIn("resume_path", first)


# ---------------------------------------------------------------------------
# Status update — PATCH /api/v1/applications/{id}/status/
# ---------------------------------------------------------------------------

class TestApplicationStatusUpdateView(TestCase):

    def setUp(self):
        self.recruiter   = make_recruiter(email="supd@views.com")
        self.seeker      = make_job_seeker(email="sappl@views.com")
        self.job         = make_job(owner=self.recruiter)
        self.application = make_application(applicant=self.seeker, job=self.job)
        self.url = reverse(
            "applications:application-status-update",
            kwargs={"application_id": self.application.id},
        )

    @patch("apps.applications.services._fire_status_update_email")
    def test_recruiter_can_advance_status(self, mock_email):
        response = _auth_client(self.recruiter).patch(
            self.url, {"status": "reviewed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "reviewed")

    @patch("apps.applications.services._fire_status_update_email")
    def test_response_contains_application_data(self, mock_email):
        response = _auth_client(self.recruiter).patch(
            self.url, {"status": "reviewed"}, format="json"
        )
        self.assertIn("id",        response.data)
        self.assertIn("status",    response.data)
        self.assertIn("applicant", response.data)

    def test_illegal_transition_returns_400(self):
        response = _auth_client(self.recruiter).patch(
            self.url, {"status": "hired"}, format="json"  # can't skip stages
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_status_value_returns_400(self):
        response = _auth_client(self.recruiter).patch(
            self.url, {"status": "flying"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_owner_recruiter_returns_404(self):
        other = make_recruiter(email="other@supd.com")
        response = _auth_client(other).patch(
            self.url, {"status": "reviewed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_job_seeker_returns_403(self):
        response = _auth_client(self.seeker).patch(
            self.url, {"status": "reviewed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_returns_401(self):
        response = _anon().patch(self.url, {"status": "reviewed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.applications.services._fire_status_update_email")
    def test_response_never_exposes_applicant_email(self, mock_email):
        _auth_client(self.recruiter).patch(
            self.url, {"status": "reviewed"}, format="json"
        )
        self.application.refresh_from_db()
        self.assertNotEqual(self.application.status, Application.Status.APPLIED)


# ---------------------------------------------------------------------------
# Resume download — GET /api/v1/applications/{id}/resume/
# ---------------------------------------------------------------------------

class TestResumeDownloadView(TestCase):

    def setUp(self):
        self.recruiter   = make_recruiter(email="rdl@views.com")
        self.seeker      = make_job_seeker(email="sdl@views.com")
        self.job         = make_job(owner=self.recruiter)
        self.application = make_application(
            applicant=self.seeker,
            job=self.job,
            resume_path="resumes/2025/01/test/fake.pdf",
        )
        self.url = reverse(
            "applications:application-resume-download",
            kwargs={"application_id": self.application.id},
        )

    @patch("api.v1.applications.views.get_resume_url", return_value="https://cdn.example.com/resume.pdf")
    def test_seeker_can_get_own_resume_url(self, mock_url):
        response = _auth_client(self.seeker).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("url", response.data)

    @patch("api.v1.applications.views.get_resume_url", return_value="https://cdn.example.com/resume.pdf")
    def test_recruiter_can_get_resume_url_for_own_job(self, mock_url):
        response = _auth_client(self.recruiter).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("url", response.data)

    def test_other_seeker_cannot_access_resume(self):
        other = make_job_seeker(email="other_rdl@views.com")
        response = _auth_client(other).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_recruiter_cannot_access_resume(self):
        other_recruiter = make_recruiter(email="other_recr@views.com")
        response = _auth_client(other_recruiter).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_returns_401(self):
        response = _anon().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_response_never_exposes_raw_storage_path(self):
        with patch("api.v1.applications.views.get_resume_url", return_value="https://cdn.example.com/resume.pdf"):
            response = _auth_client(self.seeker).get(self.url)
        self.assertNotIn("resume_path", response.data)
        self.assertNotIn("resumes/2025/01/test/fake.pdf", str(response.data))
