"""
apps/applications/admin.py
"""

from django.contrib import admin
from apps.applications.models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display  = ["applicant", "job", "status", "created_at", "updated_at"]
    list_filter   = ["status"]
    search_fields = ["applicant__email", "job__title"]
    readonly_fields = [
        "id", "created_at", "updated_at",
        "applicant", "job", "resume_path",
    ]
    raw_id_fields = ["job", "applicant"]

    fieldsets = (
        ("Application", {"fields": ("id", "job", "applicant", "status")}),
        ("Content",     {"fields": ("cover_letter", "resume_path")}),
        ("Internal",    {"fields": ("recruiter_notes",)}),
        ("Timestamps",  {"fields": ("created_at", "updated_at")}),
    )
