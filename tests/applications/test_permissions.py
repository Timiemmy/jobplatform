"""
tests/applications/test_permissions.py

Permission matrix for all Phase 3 endpoints.

Every endpoint tested against all four actor types:
    Anonymous  → expected HTTP status
    Job seeker → expected HTTP status
    Recruiter  → expected HTTP status (owner and non-owner)
    Admin      → expected HTTP status

Also covers the critical data isolation guarantees:
    - Seeker never sees another seeker's applications
    - Recruiter never sees applicant emails
    - Resume paths never leak in any response
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.applications.models import Application
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
# POST /api/v1/applications/  — job seeker only
# ---------------------------------------------------------------------------

class TestApplyPermissions(TestCase):

    def setUp(self):
        self.url = reverse("applications:application-list-create")
        self.job = make_job()

    def _payload(self, job_id=None):
        import io
        f = io.BytesIO(b"%PDF fake")
        f.name = "resume.pdf"
        return {"job_id": str(job_id or self.job.id), "resume": f}

    def test_anonymous_gets_401(self):
        response = _anon().post(self.url, self._payload(), format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recruiter_gets_403(self):
        response = _auth_client(make_recruiter(email="r@perm.com")).post(
            self.url, self._payload(), format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_gets_403(self):
        response = _auth_client(make_admin(email="a@perm.com")).post(
            self.url, self._payload(), format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.applications.services._fire_application_emails")
    @patch("apps.applications.services.upload_resume", return_value="resumes/test.pdf")
    @patch("apps.applications.services.validate_resume_file")
    def test_job_seeker_gets_201(self, mv, mu, me):
        response = _auth_client(make_job_seeker(email="s@perm.com")).post(
            self.url, self._payload(), format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# GET /api/v1/applications/  — job seeker only
# ---------------------------------------------------------------------------

class TestListApplicationsPermissions(TestCase):

    def setUp(self):
        self.url = reverse("applications:application-list-create")

    def test_anonymous_gets_401(self):
        self.assertEqual(_anon().get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recruiter_gets_403(self):
        self.assertEqual(
            _auth_client(make_recruiter(email="rl@perm.com")).get(self.url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_gets_403(self):
        self.assertEqual(
            _auth_client(make_admin(email="al@perm.com")).get(self.url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_job_seeker_gets_200(self):
        self.assertEqual(
            _auth_client(make_job_seeker(email="sl@perm.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/applications/{id}/  — own seeker only
# ---------------------------------------------------------------------------

class TestApplicationDetailPermissions(TestCase):

    def setUp(self):
        self.owner = make_job_seeker(email="owner@det.com")
        self.app   = make_application(applicant=self.owner)
        self.url   = reverse(
            "applications:application-detail",
            kwargs={"application_id": self.app.id},
        )

    def test_anonymous_gets_401(self):
        self.assertEqual(_anon().get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recruiter_gets_403(self):
        self.assertEqual(
            _auth_client(make_recruiter(email="r@det.com")).get(self.url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_different_seeker_gets_404(self):
        """Non-owner seeker must not know the application exists."""
        other = make_job_seeker(email="other@det.com")
        self.assertEqual(
            _auth_client(other).get(self.url).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_owner_seeker_gets_200(self):
        self.assertEqual(
            _auth_client(self.owner).get(self.url).status_code,
            status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{id}/applicants/  — owner recruiter only
# ---------------------------------------------------------------------------

class TestApplicantsListPermissions(TestCase):

    def setUp(self):
        self.recruiter = make_recruiter(email="owner@appl.com")
        self.job       = make_job(owner=self.recruiter)
        self.url       = reverse("job-applicants", kwargs={"job_id": self.job.id})

    def test_anonymous_gets_401(self):
        self.assertEqual(_anon().get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_job_seeker_gets_403(self):
        self.assertEqual(
            _auth_client(make_job_seeker(email="s@appl.com")).get(self.url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_owner_recruiter_gets_404(self):
        other = make_recruiter(email="other@appl.com")
        self.assertEqual(
            _auth_client(other).get(self.url).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_owner_recruiter_gets_200(self):
        self.assertEqual(
            _auth_client(self.recruiter).get(self.url).status_code,
            status.HTTP_200_OK,
        )

    def test_admin_gets_403(self):
        self.assertEqual(
            _auth_client(make_admin(email="a@appl.com")).get(self.url).status_code,
            status.HTTP_403_FORBIDDEN,
        )


# ---------------------------------------------------------------------------
# PATCH /api/v1/applications/{id}/status/  — owner recruiter only
# ---------------------------------------------------------------------------

class TestStatusUpdatePermissions(TestCase):

    def setUp(self):
        self.recruiter   = make_recruiter(email="owner@stat.com")
        self.seeker      = make_job_seeker(email="appl@stat.com")
        self.job         = make_job(owner=self.recruiter)
        self.application = make_application(applicant=self.seeker, job=self.job)
        self.url = reverse(
            "applications:application-status-update",
            kwargs={"application_id": self.application.id},
        )

    def _patch(self, client):
        return client.patch(self.url, {"status": "reviewed"}, format="json")

    def test_anonymous_gets_401(self):
        self.assertEqual(_anon().patch(self.url, {"status": "reviewed"}, format="json").status_code,
                         status.HTTP_401_UNAUTHORIZED)

    def test_job_seeker_gets_403(self):
        self.assertEqual(
            _auth_client(self.seeker).patch(self.url, {"status": "reviewed"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_owner_recruiter_gets_404(self):
        other = make_recruiter(email="other@stat.com")
        self.assertEqual(
            _auth_client(other).patch(self.url, {"status": "reviewed"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    @patch("apps.applications.services._fire_status_update_email")
    def test_owner_recruiter_gets_200(self, mock_email):
        self.assertEqual(
            _auth_client(self.recruiter).patch(self.url, {"status": "reviewed"}, format="json").status_code,
            status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Data isolation guarantees
# ---------------------------------------------------------------------------

class TestDataIsolationGuarantees(TestCase):
    """
    Critical: verify that sensitive data never leaks across role boundaries.
    """

    def test_seeker_cannot_see_other_seekers_applications(self):
        seeker_a = make_job_seeker(email="iso_a@views.com")
        seeker_b = make_job_seeker(email="iso_b@views.com")
        make_application(applicant=seeker_a)
        make_application(applicant=seeker_b)

        url      = reverse("applications:application-list-create")
        response = _auth_client(seeker_a).get(url)

        # seeker_a sees only their own 1 application
        self.assertEqual(response.data["count"], 1)

    def test_applicant_email_never_in_recruiter_response(self):
        recruiter = make_recruiter(email="iso_r@views.com")
        seeker    = make_job_seeker(email="iso_secret@views.com")
        job       = make_job(owner=recruiter)
        make_application(applicant=seeker, job=job)

        url      = reverse("job-applicants", kwargs={"job_id": job.id})
        response = _auth_client(recruiter).get(url)

        self.assertNotIn("iso_secret@views.com", str(response.data))

    def test_resume_path_absent_from_all_list_responses(self):
        seeker = make_job_seeker(email="iso_path@views.com")
        make_application(applicant=seeker, resume_path="resumes/private/path.pdf")

        url      = reverse("applications:application-list-create")
        response = _auth_client(seeker).get(url)

        self.assertNotIn("resume_path",                 str(response.data))
        self.assertNotIn("resumes/private/path.pdf",    str(response.data))

    def test_recruiter_notes_absent_from_seeker_response(self):
        recruiter = make_recruiter(email="iso_notes_r@views.com")
        seeker    = make_job_seeker(email="iso_notes_s@views.com")
        job       = make_job(owner=recruiter)
        app       = make_application(applicant=seeker, job=job)

        # Inject internal note directly
        app.recruiter_notes = "Candidate seems weak on systems design."
        app.save(update_fields=["recruiter_notes"])

        url      = reverse("applications:application-detail",
                           kwargs={"application_id": app.id})
        response = _auth_client(seeker).get(url)

        self.assertNotIn("recruiter_notes",                        str(response.data))
        self.assertNotIn("Candidate seems weak on systems design.", str(response.data))
