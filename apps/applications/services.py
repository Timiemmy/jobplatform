"""
apps/applications/services.py

All business logic for the applications domain.

Rules enforced here:
  - Only job seekers can apply.
  - Job must exist and be published.
  - No duplicate applications (UniqueConstraint + service guard).
  - Resume file is validated and uploaded before Application is created.
  - Status transitions must follow the allowed graph (no illegal jumps).
  - Only recruiters who own the job can update application status.
  - Async email tasks are fired AFTER the DB transaction commits.
"""

import logging
from django.db import transaction, IntegrityError

from apps.accounts.models import User
from apps.applications.models import Application
from apps.jobs.models import Job
from core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ApplicationError,
)
from infrastructure.storage.backends import upload_resume
from infrastructure.storage.validators import validate_resume_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Apply for a job
# ---------------------------------------------------------------------------

def apply_to_job(
    *,
    applicant: User,
    job_id: str,
    resume_file,
    cover_letter: str = "",
) -> Application:
    """
    Submit a job application.

    Steps:
      1. Validate applicant role is job_seeker.
      2. Fetch job — must exist and be published.
      3. Reject duplicate applications.
      4. Validate resume file (extension, size, MIME).
      5. Upload resume to storage.
      6. Create Application record (atomic).
      7. Fire async confirmation + recruiter notification emails.

    Returns:
        Application: The newly created application.

    Raises:
        ForbiddenError:    if applicant is not a job seeker.
        NotFoundError:     if job does not exist or is not published.
        ConflictError:     if a duplicate application exists.
        ValidationError:   if resume file is invalid.
        ApplicationError:  for any other failure.
    """
    # 1. Role check
    if not applicant.is_job_seeker:
        raise ForbiddenError("Only job seekers can apply for jobs.")

    # 2. Fetch job
    try:
        job = Job.objects.select_related("owner").get(
            id=job_id,
            job_status=Job.Status.PUBLISHED,
            is_active=True,
        )
    except Job.DoesNotExist:
        raise NotFoundError("Job not found or is no longer accepting applications.")

    # 3. Duplicate check (early — before uploading the file)
    if Application.objects.filter(job=job, applicant=applicant).exists():
        raise ConflictError("You have already applied for this job.")

    # 4. Validate resume
    validate_resume_file(resume_file)

    # 5. Upload resume to storage
    resume_path = upload_resume(
        file=resume_file,
        user_id=str(applicant.id),
    )

    # 6. Create Application atomically
    try:
        with transaction.atomic():
            application = Application.objects.create(
                job=job,
                applicant=applicant,
                resume_path=resume_path,
                cover_letter=cover_letter,
                status=Application.Status.APPLIED,
            )
    except IntegrityError:
        # Race condition: two simultaneous requests — DB constraint caught it
        raise ConflictError("You have already applied for this job.")

    logger.info(
        "Application created: id=%s applicant=%s job=%s",
        application.id, applicant.email, job.title,
    )

    # 7. Fire async emails (after commit — never inside the transaction)
    _fire_application_emails(application=application, job=job, applicant=applicant)

    return application


# ---------------------------------------------------------------------------
# Update application status (recruiter only)
# ---------------------------------------------------------------------------

def update_application_status(
    *,
    application: Application,
    recruiter: User,
    new_status: str,
) -> Application:
    """
    Advance or reject an application.

    Rules:
      - Caller must be the recruiter who owns the job.
      - Transition must be valid per Application.VALID_TRANSITIONS.
      - After update, fires async status notification email to applicant.

    Returns:
        Application: The updated application.

    Raises:
        ForbiddenError:    if caller is not the job owner.
        ApplicationError:  if the transition is illegal.
    """
    if not recruiter.is_recruiter:
        raise ForbiddenError("Only recruiters can update application status.")

    if application.job.owner != recruiter and not recruiter.is_platform_admin:
        raise ForbiddenError(
            "You can only update applications for jobs you have posted."
        )

    # Validate transition
    allowed = Application.VALID_TRANSITIONS.get(application.status, set())
    if new_status not in allowed:
        raise ApplicationError(
            f"Cannot transition from '{application.status}' to '{new_status}'. "
            f"Allowed transitions: {sorted(allowed) if allowed else 'none (terminal status)'}."
        )

    old_status = application.status
    application.status = new_status
    application.save(update_fields=["status", "updated_at"])

    logger.info(
        "Application %s status changed: %s → %s by recruiter %s",
        application.id, old_status, new_status, recruiter.email,
    )

    # Fire async email to applicant
    _fire_status_update_email(application=application, new_status=new_status)

    return application


# ---------------------------------------------------------------------------
# Internal helpers — task dispatch
# ---------------------------------------------------------------------------

def _fire_application_emails(
    *,
    application: Application,
    job: Job,
    applicant: User,
) -> None:
    """
    Dispatch both async emails triggered on application submission.
    Imported lazily to avoid circular imports at module load time.
    """
    from infrastructure.tasks.email_tasks import (
        send_application_confirmation_email,
        send_new_applicant_notification_email,
    )

    # Get recruiter profile for company name
    company_name = ""
    try:
        company_name = job.owner.profile.company_name or ""
    except Exception:
        pass

    applicant_name = f"{applicant.first_name} {applicant.last_name}".strip() or applicant.email

    # Confirmation to job seeker
    send_application_confirmation_email.delay(
        applicant_email=applicant.email,
        applicant_name=applicant_name,
        job_title=job.title,
        company_name=company_name,
    )

    # Notification to recruiter
    recruiter = job.owner
    recruiter_name = f"{recruiter.first_name} {recruiter.last_name}".strip() or recruiter.email

    send_new_applicant_notification_email.delay(
        recruiter_email=recruiter.email,
        recruiter_name=recruiter_name,
        applicant_name=applicant_name,
        job_title=job.title,
    )


def _fire_status_update_email(
    *,
    application: Application,
    new_status: str,
) -> None:
    """Dispatch async status update email to the applicant."""
    from infrastructure.tasks.email_tasks import send_status_update_email

    applicant = application.applicant
    applicant_name = (
        f"{applicant.first_name} {applicant.last_name}".strip() or applicant.email
    )

    company_name = ""
    try:
        company_name = application.job.owner.profile.company_name or ""
    except Exception:
        pass

    send_status_update_email.delay(
        applicant_email=applicant.email,
        applicant_name=applicant_name,
        job_title=application.job.title,
        company_name=company_name,
        new_status=new_status,
    )
