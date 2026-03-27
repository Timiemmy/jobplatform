"""
tests/jobs/test_permissions.py

Permission matrix tests for Phase 2 endpoints.

Every endpoint tested against:
    Anonymous  →  expected HTTP status
    Job seeker →  expected HTTP status
    Recruiter  →  expected HTTP status
    Admin      →  expected HTTP status

This is the regression guard for role-based access control.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.jobs.models import Job
from tests.factories import make_job_seeker, make_recruiter, make_admin, make_job


def _auth_client(user) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


def _anon() -> APIClient:
    return APIClient()


# ---------------------------------------------------------------------------
# Jobs endpoints
# ---------------------------------------------------------------------------

class TestJobListPermissions(TestCase):
    """GET /api/v1/jobs/ — public, no auth required."""

    def setUp(self):
        self.url = reverse("jobs:job-list-create")
        make_job()

    def test_anonymous_can_list(self):
        self.assertEqual(_anon().get(self.url).status_code, status.HTTP_200_OK)

    def test_job_seeker_can_list(self):
        self.assertEqual(
            _auth_client(make_job_seeker(email="s@perm.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )

    def test_recruiter_can_list(self):
        self.assertEqual(
            _auth_client(make_recruiter(email="r@perm.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )

    def test_admin_can_list(self):
        self.assertEqual(
            _auth_client(make_admin(email="a@perm.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )


class TestJobCreatePermissions(TestCase):
    """POST /api/v1/jobs/ — recruiter only."""

    def setUp(self):
        self.url = reverse("jobs:job-list-create")
        self.payload = {
            "title": "Perm Test Job",
            "description": (
                "This is a test job for permission matrix validation. "
                "We need a skilled engineer with backend experience and "
                "a passion for clean architecture and scalable systems."
            ),
            "job_type": Job.JobType.FULL_TIME,
            "experience_level": Job.ExperienceLevel.MID,
        }

    def test_anonymous_gets_401(self):
        self.assertEqual(
            _anon().post(self.url, self.payload, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_job_seeker_gets_403(self):
        self.assertEqual(
            _auth_client(make_job_seeker(email="s@create.com"))
            .post(self.url, self.payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_recruiter_gets_201(self):
        self.assertEqual(
            _auth_client(make_recruiter(email="r@create.com"))
            .post(self.url, self.payload, format="json").status_code,
            status.HTTP_201_CREATED,
        )

    def test_admin_gets_403(self):
        """Admins manage the platform but do not post jobs."""
        self.assertEqual(
            _auth_client(make_admin(email="a@create.com"))
            .post(self.url, self.payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )


class TestJobRetrievePermissions(TestCase):
    """GET /api/v1/jobs/{id}/ — public."""

    def setUp(self):
        self.job = make_job()
        self.url = reverse("jobs:job-detail", kwargs={"job_id": self.job.id})

    def test_anonymous_can_retrieve(self):
        self.assertEqual(_anon().get(self.url).status_code, status.HTTP_200_OK)

    def test_job_seeker_can_retrieve(self):
        self.assertEqual(
            _auth_client(make_job_seeker(email="s@ret.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )

    def test_recruiter_can_retrieve(self):
        self.assertEqual(
            _auth_client(make_recruiter(email="r@ret.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )


class TestJobUpdatePermissions(TestCase):
    """PATCH /api/v1/jobs/{id}/ — owner recruiter or admin only."""

    def setUp(self):
        self.owner = make_recruiter(email="owner@upd.com")
        self.job   = make_job(owner=self.owner)
        self.url   = reverse("jobs:job-detail", kwargs={"job_id": self.job.id})

    def test_anonymous_gets_401(self):
        self.assertEqual(
            _anon().patch(self.url, {"title": "x"}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_job_seeker_gets_403(self):
        self.assertEqual(
            _auth_client(make_job_seeker(email="s@upd.com"))
            .patch(self.url, {"title": "x"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_owner_recruiter_gets_403(self):
        self.assertEqual(
            _auth_client(make_recruiter(email="other@upd.com"))
            .patch(self.url, {"title": "x"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_owner_recruiter_gets_200(self):
        self.assertEqual(
            _auth_client(self.owner)
            .patch(self.url, {"title": "Updated"}, format="json").status_code,
            status.HTTP_200_OK,
        )

    def test_admin_gets_200(self):
        self.assertEqual(
            _auth_client(make_admin(email="a@upd.com"))
            .patch(self.url, {"title": "Admin Updated"}, format="json").status_code,
            status.HTTP_200_OK,
        )


class TestJobDeletePermissions(TestCase):
    """DELETE /api/v1/jobs/{id}/ — owner recruiter or admin only."""

    def _make_job_and_url(self, owner):
        job = make_job(owner=owner)
        return job, reverse("jobs:job-detail", kwargs={"job_id": job.id})

    def test_anonymous_gets_401(self):
        owner = make_recruiter(email="del_owner@perm.com")
        _, url = self._make_job_and_url(owner)
        self.assertEqual(_anon().delete(url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_job_seeker_gets_403(self):
        owner = make_recruiter(email="del_owner2@perm.com")
        _, url = self._make_job_and_url(owner)
        self.assertEqual(
            _auth_client(make_job_seeker(email="s@del.com")).delete(url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_owner_recruiter_gets_403(self):
        owner = make_recruiter(email="del_owner3@perm.com")
        _, url = self._make_job_and_url(owner)
        self.assertEqual(
            _auth_client(make_recruiter(email="intruder@del.com")).delete(url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_owner_gets_204(self):
        owner = make_recruiter(email="del_owner4@perm.com")
        _, url = self._make_job_and_url(owner)
        self.assertEqual(_auth_client(owner).delete(url).status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_gets_204(self):
        owner = make_recruiter(email="del_owner5@perm.com")
        _, url = self._make_job_and_url(owner)
        self.assertEqual(
            _auth_client(make_admin(email="a@del.com")).delete(url).status_code,
            status.HTTP_204_NO_CONTENT,
        )


class TestMyJobsPermissions(TestCase):
    """GET /api/v1/jobs/mine/ — recruiter only."""

    def setUp(self):
        self.url = reverse("jobs:my-jobs")

    def test_anonymous_gets_401(self):
        self.assertEqual(_anon().get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_job_seeker_gets_403(self):
        self.assertEqual(
            _auth_client(make_job_seeker(email="s@mine.com")).get(self.url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_recruiter_gets_200(self):
        self.assertEqual(
            _auth_client(make_recruiter(email="r@mine.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )

    def test_admin_gets_403(self):
        """Admin is not a recruiter — should not see job mine view."""
        self.assertEqual(
            _auth_client(make_admin(email="a@mine.com")).get(self.url).status_code,
            status.HTTP_403_FORBIDDEN,
        )


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------

class TestProfilePermissions(TestCase):
    """
    GET/PATCH /api/v1/profiles/me/ — requires authentication, any role.
    """

    def setUp(self):
        self.url = reverse("profiles:my-profile")

    def test_anonymous_gets_401(self):
        self.assertEqual(_anon().get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anonymous_patch_gets_401(self):
        self.assertEqual(
            _anon().patch(self.url, {"bio": "x"}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_job_seeker_can_get_profile(self):
        self.assertEqual(
            _auth_client(make_job_seeker(email="s@prof.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )

    def test_recruiter_can_get_profile(self):
        self.assertEqual(
            _auth_client(make_recruiter(email="r@prof.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )

    def test_admin_can_get_profile(self):
        self.assertEqual(
            _auth_client(make_admin(email="a@prof.com")).get(self.url).status_code,
            status.HTTP_200_OK,
        )

    def test_job_seeker_can_patch_profile(self):
        self.assertEqual(
            _auth_client(make_job_seeker(email="sp@prof.com"))
            .patch(self.url, {"bio": "Hello"}, format="json").status_code,
            status.HTTP_200_OK,
        )

    def test_recruiter_can_patch_profile(self):
        self.assertEqual(
            _auth_client(make_recruiter(email="rp@prof.com"))
            .patch(self.url, {"bio": "We hire."}, format="json").status_code,
            status.HTTP_200_OK,
        )

    def test_profile_response_never_exposes_password(self):
        seeker = make_job_seeker(email="nopw@prof.com")
        response = _auth_client(seeker).get(self.url)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password", str(response.data))
