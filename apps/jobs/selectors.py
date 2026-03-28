"""
Read-only query logic for the jobs domain.

All functions return QuerySets (not evaluated lists) so the
calling view can attach pagination and filtering without
triggering extra DB hits.
"""

import logging
from django.db.models import QuerySet, Q

from apps.accounts.models import User
from apps.jobs.models import Job

logger = logging.getLogger(__name__)


def get_published_jobs(
    *,
    search:           str | None = None,
    location:         str | None = None,
    job_type:         str | None = None,
    experience_level: str | None = None,
    salary_min:       float | None = None,
    salary_max:       float | None = None,
) -> QuerySet[Job]:
    """
    Return all published, active jobs with optional search and filters.

    Full-text search covers title and description (icontains — DB agnostic).
    For production-scale full-text search, replace with
    SearchVector + SearchQuery (PostgreSQL specific).

    All filter params are optional. Only supplied params are applied.
    Returns a QuerySet — pagination applied by the view.
    """
    qs = (
        Job.objects
        .filter(job_status=Job.Status.PUBLISHED, is_active=True)
        .select_related("owner")
        .order_by("-created_at")
    )

    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )

    if location:
        qs = qs.filter(location__icontains=location)

    if job_type:
        qs = qs.filter(job_type=job_type)

    if experience_level:
        qs = qs.filter(experience_level=experience_level)

    if salary_min is not None:
        # Jobs without a salary_min are excluded when filtering by min
        qs = qs.filter(salary_min__gte=salary_min)

    if salary_max is not None:
        qs = qs.filter(salary_max__lte=salary_max)

    return qs


def get_job_by_id(*, job_id: str) -> Job:
    """
    Fetch a single active job by UUID.

    Raises:
        Job.DoesNotExist: if not found or soft-deleted.
    """
    return (
        Job.objects
        .select_related("owner")
        .get(id=job_id, is_active=True)
    )


def get_jobs_by_recruiter(*, recruiter: User) -> QuerySet[Job]:
    """
    Return all active jobs posted by a specific recruiter.
    Includes drafts and closed jobs — visible to the owner only.
    """
    return (
        Job.objects
        .filter(owner=recruiter, is_active=True)
        .select_related("owner")
        .order_by("-created_at")
    )


def get_job_by_id_for_owner(*, job_id: str, owner: User) -> Job:
    """
    Fetch a job only if it belongs to the given owner.
    Used for ownership-gated mutations (update, delete).

    Raises:
        Job.DoesNotExist: if not found, soft-deleted, or wrong owner.
    """
    return Job.objects.get(id=job_id, owner=owner, is_active=True)
