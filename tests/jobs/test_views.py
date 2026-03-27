"""
tests/jobs/test_views.py

Integration tests for the jobs API endpoints.

Endpoints covered:
    GET    /api/v1/jobs/
    POST   /api/v1/jobs/
    GET    /api/v1/jobs/{id}/
    PATCH  /api/v1/jobs/{id}/
    DELETE /api/v1/jobs/{id}/
    GET    /api/v1/jobs/mine/
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.jobs.models import Job
from tests.factories import make_recruiter, make_job_seeker, make_admin, make_job


def _auth_client(user) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


def _anon_client() -> APIClient:
    return APIClient()


class TestJobListView(TestCase):
    """GET /api/v1/jobs/"""

    def setUp(self):
        self.url = reverse("jobs:job-list-create")

    def test_anonymous_can_list_jobs(self):
        make_job()
        response = _anon_client().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_uses_pagination_envelope(self):
        make_job()
        response = _anon_client().get(self.url)
        self.assertIn("count",    response.data)
        self.assertIn("next",     response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results",  response.data)

    def test_only_published_jobs_returned(self):
        make_job(title="Published",  status=Job.Status.PUBLISHED)
        make_job(title="Draft",      status=Job.Status.DRAFT)
        make_job(title="Soft Deleted", is_active=False)

        response = _anon_client().get(self.url)
        titles = [j["title"] for j in response.data["results"]]

        self.assertIn("Published", titles)
        self.assertNotIn("Draft",        titles)
        self.assertNotIn("Soft Deleted", titles)

    def test_search_by_title(self):
        make_job(title="Python Expert Needed")
        make_job(title="Java Developer Role")

        response = _anon_client().get(self.url, {"search": "Python"})
        titles = [j["title"] for j in response.data["results"]]

        self.assertTrue(any("Python" in t for t in titles))
        self.assertFalse(any("Java" in t for t in titles))

    def test_filter_by_job_type(self):
        make_job(title="Remote Job",   job_type=Job.JobType.REMOTE)
        make_job(title="Contract Job", job_type=Job.JobType.CONTRACT)

        response = _anon_client().get(self.url, {"job_type": "remote"})
        titles = [j["title"] for j in response.data["results"]]

        self.assertIn("Remote Job",    titles)
        self.assertNotIn("Contract Job", titles)

    def test_filter_by_experience_level(self):
        make_job(title="Senior Role", experience_level=Job.ExperienceLevel.SENIOR)
        make_job(title="Entry Role",  experience_level=Job.ExperienceLevel.ENTRY)

        response = _anon_client().get(self.url, {"experience_level": "senior"})
        titles = [j["title"] for j in response.data["results"]]

        self.assertIn("Senior Role", titles)
        self.assertNotIn("Entry Role", titles)

    def test_filter_by_salary_min(self):
        make_job(title="High Salary", salary_min=Decimal("100000"), salary_max=Decimal("150000"))
        make_job(title="Low Salary",  salary_min=Decimal("20000"),  salary_max=Decimal("35000"))

        response = _anon_client().get(self.url, {"salary_min": 80000})
        titles = [j["title"] for j in response.data["results"]]

        self.assertIn("High Salary", titles)
        self.assertNotIn("Low Salary", titles)

    def test_page_size_is_respected(self):
        for _ in range(15):
            make_job()
        response = _anon_client().get(self.url, {"page_size": 5})
        self.assertEqual(len(response.data["results"]), 5)

    def test_default_page_size_is_ten(self):
        for _ in range(15):
            make_job()
        response = _anon_client().get(self.url)
        self.assertLessEqual(len(response.data["results"]), 10)

    def test_results_do_not_include_description_field(self):
        """List serializer must omit description to keep payloads small."""
        make_job()
        response = _anon_client().get(self.url)
        first = response.data["results"][0]
        self.assertNotIn("description", first)

    def test_results_do_not_expose_owner_email(self):
        """Owner email must never appear on the public job list."""
        recruiter = make_recruiter(email="secret@recruiter.com")
        make_job(owner=recruiter)
        response = _anon_client().get(self.url)
        response_str = str(response.data)
        self.assertNotIn("secret@recruiter.com", response_str)


class TestJobCreateView(TestCase):
    """POST /api/v1/jobs/"""

    def setUp(self):
        self.url = reverse("jobs:job-list-create")
        self.recruiter = make_recruiter(email="creator@jobs.com")

    def _valid_payload(self, **overrides) -> dict:
        data = {
            "title": "Backend Engineer",
            "description": (
                "We are looking for a skilled backend engineer to build "
                "robust REST APIs and data pipelines. Strong Python skills "
                "required. Remote-friendly team with competitive pay."
            ),
            "location": "Lagos",
            "job_type": Job.JobType.FULL_TIME,
            "experience_level": Job.ExperienceLevel.MID,
            "salary_min": "50000.00",
            "salary_max": "80000.00",
        }
        data.update(overrides)
        return data

    def test_recruiter_can_create_job(self):
        response = _auth_client(self.recruiter).post(
            self.url, self._valid_payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_response_contains_job_detail(self):
        response = _auth_client(self.recruiter).post(
            self.url, self._valid_payload(), format="json"
        )
        self.assertIn("id", response.data)
        self.assertIn("title", response.data)
        self.assertIn("description", response.data)

    def test_job_seeker_cannot_create_job(self):
        seeker = make_job_seeker(email="seeker@create.com")
        response = _auth_client(seeker).post(
            self.url, self._valid_payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_create_job(self):
        response = _anon_client().post(
            self.url, self._valid_payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_title_returns_400(self):
        payload = self._valid_payload()
        del payload["title"]
        response = _auth_client(self.recruiter).post(
            self.url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_short_description_returns_400(self):
        payload = self._valid_payload(description="Too short.")
        response = _auth_client(self.recruiter).post(
            self.url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_salary_max_less_than_min_returns_400(self):
        payload = self._valid_payload(salary_min="100000", salary_max="50000")
        response = _auth_client(self.recruiter).post(
            self.url, payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_is_set_to_requesting_recruiter(self):
        response = _auth_client(self.recruiter).post(
            self.url, self._valid_payload(), format="json"
        )
        job = Job.objects.get(id=response.data["id"])
        self.assertEqual(job.owner, self.recruiter)


class TestJobDetailView(TestCase):
    """GET /api/v1/jobs/{id}/"""

    def setUp(self):
        self.recruiter = make_recruiter(email="detail_owner@jobs.com")
        self.job = make_job(owner=self.recruiter)
        self.url = reverse("jobs:job-detail", kwargs={"job_id": self.job.id})

    def test_anonymous_can_retrieve_published_job(self):
        response = _anon_client().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_description(self):
        response = _anon_client().get(self.url)
        self.assertIn("description", response.data)
        self.assertEqual(response.data["title"], self.job.title)

    def test_soft_deleted_job_returns_404(self):
        self.job.is_active = False
        self.job.save(update_fields=["is_active"])
        response = _anon_client().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_id_returns_404(self):
        import uuid
        url = reverse("jobs:job-detail", kwargs={"job_id": uuid.uuid4()})
        response = _anon_client().get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_email_not_exposed(self):
        response = _anon_client().get(self.url)
        self.assertNotIn("detail_owner@jobs.com", str(response.data))


class TestJobUpdateView(TestCase):
    """PATCH /api/v1/jobs/{id}/"""

    def setUp(self):
        self.recruiter = make_recruiter(email="patch_owner@jobs.com")
        self.job = make_job(owner=self.recruiter)
        self.url = reverse("jobs:job-detail", kwargs={"job_id": self.job.id})

    def test_owner_can_update_job(self):
        response = _auth_client(self.recruiter).patch(
            self.url, {"title": "Updated Title"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Title")

    def test_non_owner_recruiter_returns_403(self):
        other = make_recruiter(email="intruder@jobs.com")
        response = _auth_client(other).patch(
            self.url, {"title": "Hijacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_job_seeker_returns_403(self):
        seeker = make_job_seeker(email="seeker_patch@jobs.com")
        response = _auth_client(seeker).patch(
            self.url, {"title": "Hijacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_returns_401(self):
        response = _anon_client().patch(self.url, {"title": "Hijacked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_update_any_job(self):
        admin = make_admin(email="admin_patch@jobs.com")
        response = _auth_client(admin).patch(
            self.url, {"title": "Admin Updated"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_salary_range_returns_400(self):
        response = _auth_client(self.recruiter).patch(
            self.url,
            {"salary_min": "200000", "salary_max": "1000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestJobDeleteView(TestCase):
    """DELETE /api/v1/jobs/{id}/"""

    def setUp(self):
        self.recruiter = make_recruiter(email="delete_owner@jobs.com")
        self.job = make_job(owner=self.recruiter)
        self.url = reverse("jobs:job-detail", kwargs={"job_id": self.job.id})

    def test_owner_can_delete_job(self):
        response = _auth_client(self.recruiter).delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_deleted_job_no_longer_appears_in_list(self):
        _auth_client(self.recruiter).delete(self.url)
        list_response = _anon_client().get(reverse("jobs:job-list-create"))
        titles = [j["title"] for j in list_response.data["results"]]
        self.assertNotIn(self.job.title, titles)

    def test_job_record_still_exists_in_db_after_delete(self):
        _auth_client(self.recruiter).delete(self.url)
        self.assertTrue(Job.objects.filter(id=self.job.id).exists())

    def test_non_owner_returns_403(self):
        other = make_recruiter(email="del_intruder@jobs.com")
        response = _auth_client(other).delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_returns_401(self):
        response = _anon_client().delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_already_deleted_job_returns_404(self):
        _auth_client(self.recruiter).delete(self.url)
        response = _auth_client(self.recruiter).delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestMyJobsView(TestCase):
    """GET /api/v1/jobs/mine/"""

    def setUp(self):
        self.url = reverse("jobs:my-jobs")
        self.recruiter = make_recruiter(email="mine@jobs.com")

    def test_recruiter_sees_own_jobs_only(self):
        other = make_recruiter(email="other_mine@jobs.com")
        make_job(owner=self.recruiter, title="My Job")
        make_job(owner=other, title="Other Job")

        response = _auth_client(self.recruiter).get(self.url)
        titles = [j["title"] for j in response.data["results"]]

        self.assertIn("My Job",    titles)
        self.assertNotIn("Other Job", titles)

    def test_includes_draft_jobs(self):
        make_job(owner=self.recruiter, title="Draft", status=Job.Status.DRAFT)
        response = _auth_client(self.recruiter).get(self.url)
        titles = [j["title"] for j in response.data["results"]]
        self.assertIn("Draft", titles)

    def test_includes_closed_jobs(self):
        make_job(owner=self.recruiter, title="Closed", status=Job.Status.CLOSED)
        response = _auth_client(self.recruiter).get(self.url)
        titles = [j["title"] for j in response.data["results"]]
        self.assertIn("Closed", titles)

    def test_job_seeker_cannot_access(self):
        seeker = make_job_seeker(email="seeker_mine@jobs.com")
        response = _auth_client(seeker).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_access(self):
        response = _anon_client().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_response_is_paginated(self):
        for _ in range(3):
            make_job(owner=self.recruiter)
        response = _auth_client(self.recruiter).get(self.url)
        self.assertIn("count",   response.data)
        self.assertIn("results", response.data)
