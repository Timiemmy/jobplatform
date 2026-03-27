"""
apps/profiles/models.py

Profile model — one-to-one extension of User.

A single Profile model stores all user profile data.
Role-specific fields are nullable — only populated for the relevant role.

  job_seeker  → bio, skills, experience_years, resume_url
  recruiter   → company_name, company_website, company_size, company_description

Shared fields (all roles): phone_number, location, avatar_url
"""

from django.conf import settings
from django.db import models

from core.models import BaseModel


class Profile(BaseModel):
    """
    Extended profile for every platform user.

    Auto-created by the post_save signal on User.
    Role-specific fields are nullable so the same table
    serves both job seekers and recruiters cleanly.
    """

    class CompanySize(models.TextChoices):
        STARTUP     = "1-10",     "1–10 employees"
        SMALL       = "11-50",    "11–50 employees"
        MEDIUM      = "51-200",   "51–200 employees"
        LARGE       = "201-500",  "201–500 employees"
        ENTERPRISE  = "500+",     "500+ employees"

    # -----------------------------------------------------------------------
    # Core relation
    # -----------------------------------------------------------------------

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # -----------------------------------------------------------------------
    # Shared fields (all roles)
    # -----------------------------------------------------------------------

    phone_number = models.CharField(max_length=20, blank=True, default="")
    location     = models.CharField(max_length=150, blank=True, default="")
    avatar_url   = models.URLField(blank=True, default="")
    bio          = models.TextField(blank=True, default="")

    # -----------------------------------------------------------------------
    # Job seeker fields
    # -----------------------------------------------------------------------

    skills = models.JSONField(
        default=list,
        blank=True,
        help_text="List of skill strings e.g. ['Python', 'Django']",
    )
    experience_years = models.PositiveSmallIntegerField(null=True, blank=True)
    resume_url       = models.URLField(blank=True, default="")

    # -----------------------------------------------------------------------
    # Recruiter fields
    # -----------------------------------------------------------------------

    company_name        = models.CharField(max_length=255, blank=True, default="")
    company_website     = models.URLField(blank=True, default="")
    company_size        = models.CharField(
        max_length=10,
        choices=CompanySize.choices,
        blank=True,
        default="",
    )
    company_description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "profiles_profile"
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"

    def __str__(self) -> str:
        return f"Profile({self.user.email})"
