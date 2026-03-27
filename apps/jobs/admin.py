"""
apps/jobs/admin.py

Django admin for the jobs domain.
"""

from django.contrib import admin
from apps.jobs.models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display  = ["title", "owner", "job_type", "experience_level", "status", "is_active", "created_at"]
    list_filter   = ["status", "job_type", "experience_level", "is_active"]
    search_fields = ["title", "description", "owner__email", "location"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields   = ["owner"]

    fieldsets = (
        ("Core", {
            "fields": ("id", "owner", "title", "description", "location"),
        }),
        ("Classification", {
            "fields": ("job_type", "experience_level", "status", "is_active"),
        }),
        ("Salary", {
            "fields": ("salary_min", "salary_max", "salary_currency"),
        }),
        ("Metadata", {
            "fields": ("application_deadline", "created_at", "updated_at"),
        }),
    )

    actions = ["make_published", "make_closed"]

    @admin.action(description="Mark selected jobs as Published")
    def make_published(self, request, queryset):
        queryset.update(status=Job.Status.PUBLISHED)

    @admin.action(description="Mark selected jobs as Closed")
    def make_closed(self, request, queryset):
        queryset.update(status=Job.Status.CLOSED)
