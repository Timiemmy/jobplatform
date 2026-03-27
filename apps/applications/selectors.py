"""
apps/applications/selectors.py

Read-only query logic for the applications domain.

Two access patterns:
  - Job seeker: sees only their own applications.
  - Recruiter:  sees all applications for jobs they own.

Resume paths are NEVER exposed directly — views call
get_resume_url() only when explicitly serving a download.
"""

from django.db.models import QuerySet

from apps.accounts.models import User
from apps.applications.models import Application
from apps.jobs.models import Job


def get_applications_for_applicant(
    *,
    applicant: User,
    status: str = None,
) -> QuerySet[Application]:
    """
    Return all applications submitted by a job seeker.
    Optionally filtered by status.

    Returns a QuerySet — pagination applied by the view.
    """
    qs = (
        Application.objects
        .filter(applicant=applicant)
        .select_related("job", "job__owner", "applicant")
        .order_by("-created_at")
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def get_applications_for_job(
    *,
    job: Job,
    status: str = None,
) -> QuerySet[Application]:
    """
    Return all applications submitted for a specific job.
    Used by the recruiter to view their applicant pool.

    Optionally filtered by status.
    """
    qs = (
        Application.objects
        .filter(job=job)
        .select_related("applicant", "job")
        .order_by("-created_at")
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def get_application_by_id(*, application_id: str) -> Application:
    """
    Fetch a single application by UUID.
    Includes related job and applicant.

    Raises:
        Application.DoesNotExist: if not found.
    """
    return (
        Application.objects
        .select_related("job", "job__owner", "applicant")
        .get(id=application_id)
    )


def get_application_by_id_for_applicant(
    *,
    application_id: str,
    applicant: User,
) -> Application:
    """
    Fetch an application only if it belongs to the given applicant.
    Used for read/withdrawal operations by job seekers.

    Raises:
        Application.DoesNotExist: if not found or wrong owner.
    """
    return Application.objects.select_related("job", "job__owner").get(
        id=application_id,
        applicant=applicant,
    )


def get_application_for_recruiter(
    *,
    application_id: str,
    recruiter: User,
) -> Application:
    """
    Fetch an application only if it belongs to a job owned by the recruiter.
    Used for status update operations.

    Raises:
        Application.DoesNotExist: if not found or wrong job owner.
    """
    return Application.objects.select_related("job", "job__owner", "applicant").get(
        id=application_id,
        job__owner=recruiter,
    )
