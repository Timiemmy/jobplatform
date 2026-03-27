"""
api/v1/jobs/filters.py

FilterSet for the job list endpoint.

Supports:
    ?search=python developer       → full-text on title + description
    ?location=Lagos                → partial match on location
    ?job_type=full_time            → exact match
    ?experience_level=senior       → exact match
    ?salary_min=50000              → salary_min__gte
    ?salary_max=120000             → salary_max__lte

search is handled by DRF SearchFilter (configured on the view).
All other params are handled here via django-filter.
"""

import django_filters
from apps.jobs.models import Job


class JobFilter(django_filters.FilterSet):
    """
    FilterSet attached to the job list view.
    Works alongside DRF's SearchFilter for title/description search.
    """

    location = django_filters.CharFilter(
        field_name="location",
        lookup_expr="icontains",
        label="Location (partial match)",
    )
    job_type = django_filters.ChoiceFilter(
        choices=Job.JobType.choices,
        label="Job type (exact)",
    )
    experience_level = django_filters.ChoiceFilter(
        choices=Job.ExperienceLevel.choices,
        label="Experience level (exact)",
    )

    # Salary range filters — each independently optional
    salary_min = django_filters.NumberFilter(
        field_name="salary_min",
        lookup_expr="gte",
        label="Minimum salary (gte)",
    )
    salary_max = django_filters.NumberFilter(
        field_name="salary_max",
        lookup_expr="lte",
        label="Maximum salary (lte)",
    )

    class Meta:
        model  = Job
        fields = ["location", "job_type", "experience_level", "salary_min", "salary_max"]
