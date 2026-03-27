"""
api/v1/profiles/serializers.py

Profile serializers.

Design:
- ProfileReadSerializer    → always returned; exposes only role-relevant fields
- JobSeekerUpdateSerializer → validates update payload for job_seeker role
- RecruiterUpdateSerializer → validates update payload for recruiter role

The view selects the correct update serializer based on request.user.role.
This keeps validation tight — a recruiter cannot submit job-seeker fields
and have them silently accepted or rejected; the serializer simply doesn't
know about them.
"""

from rest_framework import serializers

from apps.accounts.models import User
from apps.profiles.models import Profile


# ---------------------------------------------------------------------------
# Read serializer — used for all GET responses regardless of role
# ---------------------------------------------------------------------------

class ProfileReadSerializer(serializers.ModelSerializer):
    """
    Full profile read representation.
    Role-specific fields are included but will be empty/null when irrelevant.
    The client should inspect the role field to decide which to render.
    """

    email      = serializers.EmailField(source="user.email",      read_only=True)
    first_name = serializers.CharField(source="user.first_name",  read_only=True)
    last_name  = serializers.CharField(source="user.last_name",   read_only=True)
    role       = serializers.CharField(source="user.role",        read_only=True)

    class Meta:
        model  = Profile
        fields = [
            # Identity (from User)
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            # Shared
            "bio",
            "phone_number",
            "location",
            "avatar_url",
            # Job seeker
            "skills",
            "experience_years",
            "resume_url",
            # Recruiter
            "company_name",
            "company_website",
            "company_size",
            "company_description",
            # Timestamps
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Update serializers — one per role
# ---------------------------------------------------------------------------

class SharedProfileUpdateSerializer(serializers.Serializer):
    """Fields writable by any role."""

    bio          = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    location     = serializers.CharField(required=False, allow_blank=True, max_length=150)
    avatar_url   = serializers.URLField(required=False,  allow_blank=True)


class JobSeekerProfileUpdateSerializer(SharedProfileUpdateSerializer):
    """
    Update payload accepted for job_seeker role.
    Extends shared fields with job-seeker-specific fields.
    """

    skills = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        max_length=50,     # max 50 skills
        help_text="List of skill strings e.g. ['Python', 'Django']",
    )
    experience_years = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=50,
    )
    resume_url = serializers.URLField(required=False, allow_blank=True)

    def validate_skills(self, value: list) -> list:
        """Normalise skill strings — strip whitespace, remove duplicates."""
        cleaned = list({s.strip() for s in value if s.strip()})
        return cleaned


class RecruiterProfileUpdateSerializer(SharedProfileUpdateSerializer):
    """
    Update payload accepted for recruiter role.
    Extends shared fields with recruiter-specific fields.
    """

    company_name = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    company_website = serializers.URLField(required=False, allow_blank=True)
    company_size = serializers.ChoiceField(
        choices=Profile.CompanySize.choices,
        required=False,
        allow_blank=True,
    )
    company_description = serializers.CharField(
        required=False, allow_blank=True, max_length=5000
    )
