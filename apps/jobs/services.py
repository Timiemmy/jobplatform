"""
apps/jobs/services.py

All business logic for the jobs domain.
Views never mutate data directly — everything goes through here.
"""

import logging
from typing import Any

from django.db import transaction

from apps.accounts.models import User
from apps.jobs.models import Job
from core.exceptions import ForbiddenError, NotFoundError

logger = logging.getLogger(__name__)


def create_job(*, owner: User, data: dict[str, Any]) -> Job:
    """
    Create a new job posting.

    Rules:
    - Only recruiters can create jobs.
    - Job is published by default.

    Raises:
        ForbiddenError: if the owner is not a recruiter.
    """
    if not owner.is_recruiter:
        raise ForbiddenError("Only recruiters can create job postings.")

    _validate_salary_range(data.get("salary_min"), data.get("salary_max"))

    with transaction.atomic():
        job = Job.objects.create(owner=owner, **data)
        logger.info("Job created: id=%s title='%s' owner=%s", job.id, job.title, owner.email)

    return job


def update_job(*, job: Job, owner: User, data: dict[str, Any]) -> Job:
    """
    Update an existing job posting.

    Rules:
    - Only the recruiter who owns the job can update it.
    - Admins bypass this check.
    - Cannot update a soft-deleted job.

    Raises:
        ForbiddenError: if caller doesn't own the job.
        NotFoundError:  if job is soft-deleted.
    """
    if not job.is_active:
        raise NotFoundError("This job posting no longer exists.")

    if not owner.is_platform_admin and job.owner != owner:
        raise ForbiddenError("You can only update jobs you have posted.")

    _validate_salary_range(
        data.get("salary_min", job.salary_min),
        data.get("salary_max", job.salary_max),
    )

    updated_fields = []
    for field, value in data.items():
        setattr(job, field, value)
        updated_fields.append(field)

    if updated_fields:
        updated_fields.append("updated_at")
        job.save(update_fields=updated_fields)
        logger.info("Job updated: id=%s fields=%s", job.id, updated_fields)

    return job


def delete_job(*, job: Job, owner: User) -> None:
    """
    Soft-delete a job posting by marking it inactive.

    Rules:
    - Only the owning recruiter or an admin can delete.
    - Deletion is non-destructive (is_active=False).

    Raises:
        ForbiddenError: if caller doesn't own the job.
    """
    if not owner.is_platform_admin and job.owner != owner:
        raise ForbiddenError("You can only delete jobs you have posted.")

    job.is_active = False
    job.status    = Job.Status.CLOSED
    job.save(update_fields=["is_active", "status", "updated_at"])
    logger.info("Job soft-deleted: id=%s by=%s", job.id, owner.email)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_salary_range(salary_min, salary_max) -> None:
    """
    Validate that min <= max when both are provided.

    Raises:
        ValueError: if salary_max < salary_min.
    """
    if salary_min is not None and salary_max is not None:
        if salary_max < salary_min:
            raise ValueError("salary_max must be greater than or equal to salary_min.")
