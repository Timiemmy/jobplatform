"""
Serializers for the jobs domain.

Separation of concerns:
- JobListSerializer     → lightweight, used on list endpoints (no heavy fields)
- JobDetailSerializer   → full representation, used on retrieve endpoints
- JobCreateSerializer   → validates create payload; no id/owner/timestamps
- JobUpdateSerializer   → validates partial update payload
"""

from decimal import Decimal
from rest_framework import serializers

from apps.jobs.models import Job


# ---------------------------------------------------------------------------
# Owner nested representation (avoids leaking recruiter email on public list)
# ---------------------------------------------------------------------------

class JobOwnerSerializer(serializers.Serializer):
    """Minimal recruiter identity — safe to expose publicly."""
    id         = serializers.UUIDField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name  = serializers.CharField(read_only=True)


# ---------------------------------------------------------------------------
# Read serializers
# ---------------------------------------------------------------------------

class JobListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the jobs list endpoint.
    Omits the full description to keep response payloads small.
    """
    owner = JobOwnerSerializer(read_only=True)

    class Meta:
        model  = Job
        fields = [
            "id",
            "title",
            "location",
            "job_type",
            "experience_level",
            "job_status",
            "salary_min",
            "salary_max",
            "salary_currency",
            "application_deadline",
            "owner",
            "created_at",
        ]
        read_only_fields = fields


class JobDetailSerializer(serializers.ModelSerializer):
    """
    Full job representation including description.
    Used on retrieve (GET /jobs/{id}/) and after create/update.
    """
    owner = JobOwnerSerializer(read_only=True)

    class Meta:
        model  = Job
        fields = [
            "id",
            "title",
            "description",
            "location",
            "job_type",
            "experience_level",
            "job_status",
            "salary_min",
            "salary_max",
            "salary_currency",
            "application_deadline",
            "is_active",
            "owner",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Write serializers
# ---------------------------------------------------------------------------

class JobCreateSerializer(serializers.Serializer):
    """
    Validate the payload for creating a new job.
    owner is injected by the service — not accepted from the client.
    """

    title       = serializers.CharField(max_length=255)
    description = serializers.CharField(min_length=50)
    location    = serializers.CharField(max_length=255, required=False, allow_blank=True)

    job_type = serializers.ChoiceField(
        choices=Job.JobType.choices,
        default=Job.JobType.FULL_TIME,
    )
    experience_level = serializers.ChoiceField(
        choices=Job.ExperienceLevel.choices,
        default=Job.ExperienceLevel.MID,
    )
    job_status = serializers.ChoiceField(
        choices=[
            (Job.Status.DRAFT,     "Draft"),
            (Job.Status.PUBLISHED, "Published"),
        ],
        default=Job.Status.PUBLISHED,
    )

    salary_min = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True,
        min_value=Decimal("0"),
    )
    salary_max = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True,
        min_value=Decimal("0"),
    )
    salary_currency = serializers.CharField(
        max_length=3,
        required=False,
        default="USD",
    )
    application_deadline = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        """Cross-field: salary_max must be >= salary_min."""
        s_min = attrs.get("salary_min")
        s_max = attrs.get("salary_max")
        if s_min is not None and s_max is not None and s_max < s_min:
            raise serializers.ValidationError(
                {"salary_max": "salary_max must be greater than or equal to salary_min."}
            )
        return attrs


class JobUpdateSerializer(serializers.Serializer):
    """
    Validate the payload for a partial update to a job.
    All fields are optional — only supplied fields are updated.
    """

    title       = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(min_length=50, required=False)
    location    = serializers.CharField(max_length=255, required=False, allow_blank=True)

    job_type = serializers.ChoiceField(
        choices=Job.JobType.choices,
        required=False,
    )
    experience_level = serializers.ChoiceField(
        choices=Job.ExperienceLevel.choices,
        required=False,
    )
    job_status = serializers.ChoiceField(
        choices=Job.Status.choices,
        required=False,
    )

    salary_min = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True,
        min_value=Decimal("0"),
    )
    salary_max = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True,
        min_value=Decimal("0"),
    )
    salary_currency     = serializers.CharField(max_length=3, required=False)
    application_deadline = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        s_min = attrs.get("salary_min")
        s_max = attrs.get("salary_max")
        if s_min is not None and s_max is not None and s_max < s_min:
            raise serializers.ValidationError(
                {"salary_max": "salary_max must be greater than or equal to salary_min."}
            )
        return attrs
