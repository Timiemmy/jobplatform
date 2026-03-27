"""
apps/jobs/models.py

Job listing model.

Key decisions:
- owner FK to User (recruiter) — only recruiters can create jobs
- salary stored as min/max range, both optional (some jobs don't disclose)
- job_type and experience_level use TextChoices for DB integrity
- is_active flag enables soft-delete without losing data
- UUID PK inherited from BaseModel
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel


class Job(BaseModel):

    class JobType(models.TextChoices):
        FULL_TIME  = "full_time",   _("Full Time")
        PART_TIME  = "part_time",   _("Part Time")
        CONTRACT   = "contract",    _("Contract")
        FREELANCE  = "freelance",   _("Freelance")
        INTERNSHIP = "internship",  _("Internship")
        REMOTE     = "remote",      _("Remote")

    class ExperienceLevel(models.TextChoices):
        ENTRY    = "entry",    _("Entry Level")
        JUNIOR   = "junior",   _("Junior")
        MID      = "mid",      _("Mid Level")
        SENIOR   = "senior",   _("Senior")
        LEAD     = "lead",     _("Lead")
        MANAGER  = "manager",  _("Manager")

    class Status(models.TextChoices):
        DRAFT     = "draft",     _("Draft")
        PUBLISHED = "published", _("Published")
        CLOSED    = "closed",    _("Closed")

    # -----------------------------------------------------------------------
    # Ownership
    # -----------------------------------------------------------------------

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="jobs",
        limit_choices_to={"role": "recruiter"},
        help_text="Recruiter who posted this job.",
    )

    # -----------------------------------------------------------------------
    # Core fields
    # -----------------------------------------------------------------------

    title       = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    location    = models.CharField(max_length=255, blank=True, default="")

    job_type = models.CharField(
        max_length=20,
        choices=JobType.choices,
        default=JobType.FULL_TIME,
        db_index=True,
    )
    experience_level = models.CharField(
        max_length=20,
        choices=ExperienceLevel.choices,
        default=ExperienceLevel.MID,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PUBLISHED,
        db_index=True,
    )

    # -----------------------------------------------------------------------
    # Salary range (optional — null = undisclosed)
    # -----------------------------------------------------------------------

    salary_min = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text="Minimum salary in the job's currency.",
    )
    salary_max = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text="Maximum salary in the job's currency.",
    )
    salary_currency = models.CharField(max_length=3, default="USD")

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------

    application_deadline = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="False = soft-deleted. Never expose to job seekers.",
    )

    class Meta:
        db_table  = "jobs_job"
        ordering  = ["-created_at"]
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        indexes = [
            models.Index(fields=["status", "is_active"]),
            models.Index(fields=["owner", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} @ {self.owner.email}"

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED and self.is_active

    @property
    def has_salary_range(self) -> bool:
        return self.salary_min is not None and self.salary_max is not None
