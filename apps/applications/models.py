"""
Application model — the bridge between a job seeker and a job posting.

Key design decisions:
  - unique_together on (job, applicant) prevents duplicate applications
    at the DB level — the service layer also guards this, but the
    constraint is the final safety net.
  - resume_path stores the storage key, NOT a URL. URLs are generated
    on-demand via infrastructure.storage.backends.get_resume_url().
    This keeps URLs short-lived (signed) in production.
  - Status transitions are validated in services.py — not enforced
    via model methods to keep the model layer thin.
  - UUID PK inherited from BaseModel.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel


class Application(BaseModel):

    class Status(models.TextChoices):
        APPLIED   = "applied",   _("Applied")
        REVIEWED  = "reviewed",  _("Reviewed")
        INTERVIEW = "interview", _("Interview")
        HIRED     = "hired",     _("Hired")
        REJECTED  = "rejected",  _("Rejected")

    # Valid transitions: only forward moves + rejection at any stage
    # Keyed by current status → set of allowed next statuses
    VALID_TRANSITIONS: dict[str, set] = {
        Status.APPLIED:   {Status.REVIEWED,  Status.REJECTED},
        Status.REVIEWED:  {Status.INTERVIEW, Status.REJECTED},
        Status.INTERVIEW: {Status.HIRED,     Status.REJECTED},
        Status.HIRED:     set(),   # terminal — no further transitions
        Status.REJECTED:  set(),   # terminal — no further transitions
    }

    # -----------------------------------------------------------------------
    # Relations
    # -----------------------------------------------------------------------

    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="applications",
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
        limit_choices_to={"role": "job_seeker"},
    )

    # -----------------------------------------------------------------------
    # Application data
    # -----------------------------------------------------------------------

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.APPLIED,
        db_index=True,
    )

    # Storage path of the resume — NOT a URL
    # Null allowed: if file is deleted from storage, we retain the record
    resume_path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Storage key for the uploaded resume file. "
                  "Generate URL via get_resume_url(path=...).",
    )

    cover_letter = models.TextField(
        blank=True,
        default="",
        help_text="Optional cover letter text submitted with the application.",
    )

    # Recruiter-facing note — internal, never exposed to job seekers
    recruiter_notes = models.TextField(
        blank=True,
        default="",
        help_text="Internal recruiter notes. Never visible to applicants.",
    )

    class Meta:
        db_table = "applications_application"
        verbose_name = "Application"
        verbose_name_plural = "Applications"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "applicant"],
                name="unique_application_per_job",
            )
        ]
        indexes = [
            models.Index(fields=["applicant", "status"]),
            models.Index(fields=["job", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.applicant.email} → {self.job.title} [{self.status}]"
