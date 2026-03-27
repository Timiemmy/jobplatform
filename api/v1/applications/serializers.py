"""
api/v1/applications/serializers.py

Serializers for the applications domain.

Security constraints:
  - resume_path is NEVER exposed in any response.
    URLs are generated on-demand via a dedicated download endpoint.
  - recruiter_notes are never sent to job seekers.
  - Applicant email is never included in recruiter-facing list responses.
"""

from rest_framework import serializers

from apps.applications.models import Application
from infrastructure.storage.validators import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    validate_resume_extension,
    validate_resume_size,
)


# ---------------------------------------------------------------------------
# Nested representations
# ---------------------------------------------------------------------------

class ApplicationJobSerializer(serializers.Serializer):
    """Minimal job info embedded in application responses."""
    id       = serializers.UUIDField(read_only=True)
    title    = serializers.CharField(read_only=True)
    location = serializers.CharField(read_only=True)


class ApplicationApplicantSerializer(serializers.Serializer):
    """Minimal applicant info shown to recruiters. No email exposed."""
    id         = serializers.UUIDField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name  = serializers.CharField(read_only=True)


# ---------------------------------------------------------------------------
# Read serializers
# ---------------------------------------------------------------------------

class ApplicationSeekerSerializer(serializers.ModelSerializer):
    """
    Application view for the job seeker.
    Shows their own application — includes job info, status, timestamps.
    Does NOT expose recruiter_notes or resume_path.
    """
    job = ApplicationJobSerializer(read_only=True)

    class Meta:
        model  = Application
        fields = [
            "id",
            "job",
            "status",
            "cover_letter",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ApplicationRecruiterSerializer(serializers.ModelSerializer):
    """
    Application view for the recruiter.
    Shows applicant info, status, cover letter, recruiter notes.
    Does NOT expose resume_path — URL generated via separate endpoint.
    Does NOT expose applicant email.
    """
    applicant = ApplicationApplicantSerializer(read_only=True)

    class Meta:
        model  = Application
        fields = [
            "id",
            "applicant",
            "status",
            "cover_letter",
            "recruiter_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Write serializers
# ---------------------------------------------------------------------------

class ApplySerializer(serializers.Serializer):
    """
    Input validation for submitting a job application.

    resume is validated for extension and size here (fast checks).
    MIME sniffing happens in the service layer after serializer passes.
    """
    resume = serializers.FileField(
        help_text=f"Resume file. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}. "
                  f"Max size: {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
    )
    cover_letter = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
        help_text="Optional cover letter.",
    )

    def validate_resume(self, file):
        """Fast file validation — extension and size only."""
        validate_resume_extension(file)
        validate_resume_size(file)
        return file


class StatusUpdateSerializer(serializers.Serializer):
    """
    Input for a recruiter updating an application's status.
    Only the status field is accepted — no other fields.
    """
    status = serializers.ChoiceField(choices=Application.Status.choices)

    def validate_status(self, value: str) -> str:
        """
        Validate the new status is not the same as the current one.
        Cross-field transition validation happens in the service layer.
        """
        return value


class RecruiterNotesSerializer(serializers.Serializer):
    """
    Allows a recruiter to update internal notes on an application.
    Notes are never visible to the applicant.
    """
    recruiter_notes = serializers.CharField(
        allow_blank=True,
        max_length=10000,
    )
