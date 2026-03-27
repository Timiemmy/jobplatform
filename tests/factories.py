"""
tests/factories.py

Centralised test data factories for all domains.
Plain helper functions — no third-party library needed.
All factories generate unique emails/titles by default to prevent
constraint violations when multiple factories are called in one test.
"""

import uuid
from decimal import Decimal

from apps.accounts.models import User
from apps.jobs.models import Job


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    """Short unique hex suffix to avoid DB constraint collisions."""
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# User factories
# ---------------------------------------------------------------------------

def make_user(
    *,
    email: str = None,
    password: str = "StrongPass123!",
    role: str = User.Role.JOB_SEEKER,
    first_name: str = "Test",
    last_name: str = "User",
    is_active: bool = True,
) -> User:
    """Create and persist a User. Generates a unique email if none given."""
    if email is None:
        email = f"user_{_uid()}@example.com"
    return User.objects.create_user(
        email=email,
        password=password,
        role=role,
        first_name=first_name,
        last_name=last_name,
        is_active=is_active,
    )


def make_job_seeker(*, email: str = None, **kwargs) -> User:
    return make_user(email=email, role=User.Role.JOB_SEEKER, **kwargs)


def make_recruiter(*, email: str = None, **kwargs) -> User:
    return make_user(email=email, role=User.Role.RECRUITER, **kwargs)


def make_admin(*, email: str = None, **kwargs) -> User:
    return make_user(email=email, role=User.Role.ADMIN, **kwargs)


# ---------------------------------------------------------------------------
# Job factory
# ---------------------------------------------------------------------------

def make_job(
    *,
    owner: User = None,
    title: str = None,
    description: str = None,
    location: str = "Lagos, Nigeria",
    job_type: str = Job.JobType.FULL_TIME,
    experience_level: str = Job.ExperienceLevel.MID,
    status: str = Job.Status.PUBLISHED,
    salary_min: Decimal = Decimal("50000.00"),
    salary_max: Decimal = Decimal("80000.00"),
    salary_currency: str = "USD",
    is_active: bool = True,
    **kwargs,
) -> Job:
    """
    Create and persist a Job.
    Auto-creates a recruiter owner if none given.
    Generates a unique title if none given.
    """
    if owner is None:
        owner = make_recruiter(email=f"recruiter_{_uid()}@example.com")
    if title is None:
        title = f"Software Engineer {_uid()}"
    if description is None:
        description = (
            "We are looking for a talented engineer to join our team. "
            "You will work on exciting projects using modern technologies. "
            "This role requires strong problem-solving skills and experience "
            "with backend systems and API development."
        )
    return Job.objects.create(
        owner=owner,
        title=title,
        description=description,
        location=location,
        job_type=job_type,
        experience_level=experience_level,
        status=status,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        is_active=is_active,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def make_application(
    *,
    applicant=None,
    job=None,
    status: str = "applied",
    resume_path: str = "resumes/2025/01/test/fake_resume.pdf",
    cover_letter: str = "I am very interested in this position.",
) -> "Application":
    """
    Create and persist an Application.
    Auto-creates a job seeker applicant and a job if none given.
    Bypasses file upload — injects a fake resume_path directly.
    """
    from apps.applications.models import Application

    if applicant is None:
        applicant = make_job_seeker(email=f"applicant_{_uid()}@example.com")
    if job is None:
        job = make_job()

    return Application.objects.create(
        applicant=applicant,
        job=job,
        status=status,
        resume_path=resume_path,
        cover_letter=cover_letter,
    )
