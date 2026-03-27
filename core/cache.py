"""
core/cache.py

Cache utilities for the job board platform.

Strategy: cache-aside (read-through on miss, explicit invalidation on write).

Cache key conventions:
    job:list:<hash>      Paginated job list results (hash of query params)
    job:detail:<uuid>    Single job detail

TTLs:
    Job list:   2 minutes  — high read volume, acceptable staleness
    Job detail: 5 minutes  — lower volume, slightly longer TTL

Invalidation:
    On any Job mutation (create/update/delete):
        - Invalidate all job:list:* keys  (pattern delete)
        - Invalidate job:detail:<uuid>    (exact delete)

All cache operations are defensive — a Redis failure must never
crash the application. Failures are logged and silently bypassed.
"""

import hashlib
import json
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTL constants (seconds)
# ---------------------------------------------------------------------------

JOB_LIST_TTL   = 120   # 2 minutes
JOB_DETAIL_TTL = 300   # 5 minutes

# ---------------------------------------------------------------------------
# Key builders
# ---------------------------------------------------------------------------

def _job_list_key(params: dict) -> str:
    """
    Build a deterministic cache key from the query params dict.
    Sorted before hashing so param order doesn't create duplicate keys.
    """
    serialised = json.dumps(params, sort_keys=True, default=str)
    digest     = hashlib.md5(serialised.encode()).hexdigest()  # noqa: S324 — not crypto
    return f"job:list:{digest}"


def _job_detail_key(job_id: str) -> str:
    return f"job:detail:{job_id}"


# ---------------------------------------------------------------------------
# Job list cache
# ---------------------------------------------------------------------------

def get_cached_job_list(*, params: dict):
    """
    Return cached job list data, or None on miss.

    Args:
        params: dict of query params (page, page_size, filters, search).
    """
    try:
        return cache.get(_job_list_key(params))
    except Exception as exc:
        logger.warning("Cache GET failed for job list: %s", exc)
        return None


def set_cached_job_list(*, params: dict, data: dict) -> None:
    """
    Cache a serialised paginated job list response.

    Args:
        params: query params dict used to build the cache key.
        data:   serialised paginated response dict (count/next/previous/results).
    """
    try:
        cache.set(_job_list_key(params), data, timeout=JOB_LIST_TTL)
    except Exception as exc:
        logger.warning("Cache SET failed for job list: %s", exc)


# ---------------------------------------------------------------------------
# Job detail cache
# ---------------------------------------------------------------------------

def get_cached_job_detail(*, job_id: str):
    """Return cached job detail dict, or None on miss."""
    try:
        return cache.get(_job_detail_key(job_id))
    except Exception as exc:
        logger.warning("Cache GET failed for job %s: %s", job_id, exc)
        return None


def set_cached_job_detail(*, job_id: str, data: dict) -> None:
    """Cache a serialised job detail response."""
    try:
        cache.set(_job_detail_key(job_id), data, timeout=JOB_DETAIL_TTL)
    except Exception as exc:
        logger.warning("Cache SET failed for job %s: %s", job_id, exc)


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------

def invalidate_job_cache(*, job_id: str) -> None:
    """
    Invalidate all cache entries related to a specific job.

    Called after: create_job, update_job, delete_job.

    - Deletes the specific job detail key.
    - Deletes all job list keys using pattern delete (requires django-redis).
      Falls back to a no-op if pattern delete isn't available.
    """
    try:
        # Exact key delete
        cache.delete(_job_detail_key(job_id))

        # Pattern delete for all list variants
        # django-redis exposes delete_pattern via cache.delete_pattern()
        if hasattr(cache, "delete_pattern"):
            cache.delete_pattern("job:list:*")
        else:
            logger.debug(
                "Pattern delete not available — job list cache not invalidated. "
                "Upgrade to django-redis for full cache invalidation."
            )
    except Exception as exc:
        logger.warning("Cache invalidation failed for job %s: %s", job_id, exc)
