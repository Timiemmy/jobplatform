"""
apps/profiles/admin.py

Django admin for the profiles domain.
"""

from django.contrib import admin
from apps.profiles.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ["user", "location", "company_name", "experience_years", "created_at"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "company_name"]
    list_filter   = ["company_size"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields   = ["user"]

    fieldsets = (
        ("User", {"fields": ("id", "user")}),
        ("Shared", {"fields": ("bio", "phone_number", "location", "avatar_url")}),
        ("Job Seeker", {"fields": ("skills", "experience_years", "resume_url")}),
        ("Recruiter",  {"fields": ("company_name", "company_website", "company_size", "company_description")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
