"""
tests/security/test_cache.py

Tests for core/cache.py — job list and detail caching.

Uses Django's test cache (LocMemCache) so no Redis needed in CI.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.cache import cache

from core.cache import (
    get_cached_job_list,
    set_cached_job_list,
    get_cached_job_detail,
    set_cached_job_detail,
    invalidate_job_cache,
    _job_list_key,
    _job_detail_key,
)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
)
class TestJobListCache(TestCase):

    def setUp(self):
        cache.clear()

    def test_miss_returns_none(self):
        result = get_cached_job_list(params={"page": "1"})
        self.assertIsNone(result)

    def test_set_then_get_returns_data(self):
        data   = {"count": 5, "results": [{"id": "abc"}]}
        params = {"page": "1", "search": "python"}
        set_cached_job_list(params=params, data=data)
        result = get_cached_job_list(params=params)
        self.assertEqual(result, data)

    def test_different_params_produce_different_keys(self):
        data_a = {"count": 1, "results": [{"id": "a"}]}
        data_b = {"count": 2, "results": [{"id": "b"}]}
        set_cached_job_list(params={"page": "1"}, data=data_a)
        set_cached_job_list(params={"page": "2"}, data=data_b)

        result_a = get_cached_job_list(params={"page": "1"})
        result_b = get_cached_job_list(params={"page": "2"})

        self.assertEqual(result_a, data_a)
        self.assertEqual(result_b, data_b)
        self.assertNotEqual(result_a, result_b)

    def test_param_order_does_not_affect_key(self):
        """Params with different ordering must hit the same cache entry."""
        data   = {"count": 3, "results": []}
        params_a = {"page": "1", "job_type": "remote"}
        params_b = {"job_type": "remote", "page": "1"}

        set_cached_job_list(params=params_a, data=data)
        result = get_cached_job_list(params=params_b)

        self.assertEqual(result, data)

    def test_invalidate_clears_detail_key(self):
        job_id = "test-uuid-1234"
        set_cached_job_detail(job_id=job_id, data={"id": job_id})
        invalidate_job_cache(job_id=job_id)
        result = get_cached_job_detail(job_id=job_id)
        self.assertIsNone(result)

    def test_cache_failure_does_not_raise(self):
        """All cache operations must swallow exceptions silently."""
        with patch("core.cache.cache") as mock_cache:
            mock_cache.get.side_effect  = Exception("Redis is down")
            mock_cache.set.side_effect  = Exception("Redis is down")
            # Must NOT raise
            result = get_cached_job_list(params={"page": "1"})
            self.assertIsNone(result)

    def test_set_failure_does_not_raise(self):
        with patch("core.cache.cache") as mock_cache:
            mock_cache.set.side_effect = Exception("Redis is down")
            try:
                set_cached_job_list(params={}, data={})
            except Exception as e:
                self.fail(f"set_cached_job_list raised: {e}")


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
)
class TestJobDetailCache(TestCase):

    def setUp(self):
        cache.clear()

    def test_miss_returns_none(self):
        self.assertIsNone(get_cached_job_detail(job_id="nonexistent"))

    def test_set_then_get_returns_data(self):
        job_id = "abc-123"
        data   = {"id": job_id, "title": "Engineer"}
        set_cached_job_detail(job_id=job_id, data=data)
        self.assertEqual(get_cached_job_detail(job_id=job_id), data)

    def test_different_job_ids_have_different_entries(self):
        set_cached_job_detail(job_id="id-1", data={"title": "Job 1"})
        set_cached_job_detail(job_id="id-2", data={"title": "Job 2"})
        self.assertEqual(get_cached_job_detail(job_id="id-1")["title"], "Job 1")
        self.assertEqual(get_cached_job_detail(job_id="id-2")["title"], "Job 2")

    def test_invalidate_removes_entry(self):
        job_id = "del-me"
        set_cached_job_detail(job_id=job_id, data={"id": job_id})
        invalidate_job_cache(job_id=job_id)
        self.assertIsNone(get_cached_job_detail(job_id=job_id))
