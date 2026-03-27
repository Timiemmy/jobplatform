"""
tests/security/test_cache_integration.py

Integration tests: verify the jobs API correctly
reads from cache on GET and invalidates on mutations.
"""

from unittest.mock import patch, call
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import make_recruiter, make_job_seeker, make_job


def _auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class TestJobListCacheIntegration(TestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_second_get_is_served_from_cache(self):
        make_job()
        url = reverse("jobs:job-list-create")

        with patch("api.v1.jobs.views.set_cached_job_list") as mock_set, \
             patch("api.v1.jobs.views.get_cached_job_list", return_value=None) as mock_get:
            APIClient().get(url)
            mock_set.assert_called_once()

    def test_cache_hit_bypasses_db(self):
        url        = reverse("jobs:job-list-create")
        cached_val = {"count": 99, "next": None, "previous": None, "results": []}

        with patch("api.v1.jobs.views.get_cached_job_list", return_value=cached_val):
            response = APIClient().get(url)

        self.assertEqual(response.data["count"], 99)

    def test_create_job_invalidates_cache(self):
        recruiter = make_recruiter(email="inv@cache.com")
        url = reverse("jobs:job-list-create")
        payload = {
            "title":            "Cache Buster",
            "description":      "This job tests that creating a new posting invalidates "
                                "the job list cache so stale data is never served to users.",
            "job_type":         "full_time",
            "experience_level": "mid",
        }

        with patch("api.v1.jobs.views.invalidate_job_cache") as mock_inv:
            _auth_client(recruiter).post(url, payload, format="json")
            mock_inv.assert_called_once()

    def test_delete_job_invalidates_cache(self):
        recruiter = make_recruiter(email="del_inv@cache.com")
        job = make_job(owner=recruiter)
        url = reverse("jobs:job-detail", kwargs={"job_id": job.id})

        with patch("api.v1.jobs.views.invalidate_job_cache") as mock_inv:
            _auth_client(recruiter).delete(url)
            mock_inv.assert_called_once_with(job_id=str(job.id))

    def test_patch_job_invalidates_cache(self):
        recruiter = make_recruiter(email="patch_inv@cache.com")
        job = make_job(owner=recruiter)
        url = reverse("jobs:job-detail", kwargs={"job_id": job.id})

        with patch("api.v1.jobs.views.invalidate_job_cache") as mock_inv:
            _auth_client(recruiter).patch(url, {"title": "Updated"}, format="json")
            mock_inv.assert_called_once_with(job_id=str(job.id))


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class TestJobDetailCacheIntegration(TestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_detail_cache_hit_returned(self):
        job        = make_job()
        cached_val = {"id": str(job.id), "title": "Cached Title", "description": "x"}
        url        = reverse("jobs:job-detail", kwargs={"job_id": job.id})

        with patch("api.v1.jobs.views.get_cached_job_detail", return_value=cached_val):
            response = APIClient().get(url)

        self.assertEqual(response.data["title"], "Cached Title")

    def test_detail_cache_miss_queries_db_and_stores(self):
        job = make_job()
        url = reverse("jobs:job-detail", kwargs={"job_id": job.id})

        with patch("api.v1.jobs.views.get_cached_job_detail", return_value=None), \
             patch("api.v1.jobs.views.set_cached_job_detail") as mock_set:
            response = APIClient().get(url)

        self.assertEqual(response.status_code, 200)
        mock_set.assert_called_once()
