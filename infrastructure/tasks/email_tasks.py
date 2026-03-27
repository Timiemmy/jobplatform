"""
infrastructure/tasks/email_tasks.py

Celery tasks for all outbound emails.

Rules:
  - Tasks are fire-and-forget (ignore_result=True).
  - Tasks never raise — failures are logged, not propagated.
  - Tasks accept only primitive args (str, int) — not model instances.
    This prevents serialization issues and ensures tasks remain
    re-runnable from a queue without stale object state.
  - All task calls use .delay() — never called synchronously.

Retry strategy:
  - 3 retries with exponential back-off (60s, 120s, 240s).
  - After max retries, failure is logged and silently dropped.
    Email delivery is best-effort — it must not block or error the app.
"""

import logging
from celery import shared_task

from infrastructure.email.sender import send_email
from infrastructure.email.templates import (
    build_application_confirmation_email,
    build_status_update_email,
    build_new_applicant_notification_email,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application confirmation — sent to job seeker
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    ignore_result=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.send_application_confirmation_email",
)
def send_application_confirmation_email(
    self,
    *,
    applicant_email: str,
    applicant_name: str,
    job_title: str,
    company_name: str,
) -> None:
    """
    Send application confirmation to the job seeker.
    Triggered immediately after a successful application submission.
    """
    try:
        email = build_application_confirmation_email(
            applicant_name=applicant_name,
            job_title=job_title,
            company_name=company_name,
        )
        send_email(
            subject=email.subject,
            message=email.message,
            html_message=email.html_message,
            recipient=applicant_email,
        )
    except Exception as exc:
        logger.exception(
            "send_application_confirmation_email failed: applicant=%s job='%s'",
            applicant_email, job_title,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ---------------------------------------------------------------------------
# Status update — sent to job seeker
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    ignore_result=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.send_status_update_email",
)
def send_status_update_email(
    self,
    *,
    applicant_email: str,
    applicant_name: str,
    job_title: str,
    company_name: str,
    new_status: str,
) -> None:
    """
    Notify the job seeker when a recruiter changes their application status.
    """
    try:
        email = build_status_update_email(
            applicant_name=applicant_name,
            job_title=job_title,
            company_name=company_name,
            new_status=new_status,
        )
        send_email(
            subject=email.subject,
            message=email.message,
            html_message=email.html_message,
            recipient=applicant_email,
        )
    except Exception as exc:
        logger.exception(
            "send_status_update_email failed: applicant=%s job='%s' status=%s",
            applicant_email, job_title, new_status,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ---------------------------------------------------------------------------
# New applicant notification — sent to recruiter
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    ignore_result=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.send_new_applicant_notification_email",
)
def send_new_applicant_notification_email(
    self,
    *,
    recruiter_email: str,
    recruiter_name: str,
    applicant_name: str,
    job_title: str,
) -> None:
    """
    Notify the recruiter when a new application arrives on their job posting.
    """
    try:
        email = build_new_applicant_notification_email(
            recruiter_name=recruiter_name,
            applicant_name=applicant_name,
            job_title=job_title,
        )
        send_email(
            subject=email.subject,
            message=email.message,
            html_message=email.html_message,
            recipient=recruiter_email,
        )
    except Exception as exc:
        logger.exception(
            "send_new_applicant_notification_email failed: recruiter=%s job='%s'",
            recruiter_email, job_title,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
