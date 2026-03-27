"""
api/v1/urls.py

Root URL aggregator for API version 1.
All domain URL modules included here.
v2 → add api/v2/urls.py + wire in config/urls.py. Nothing here changes.
"""

from django.urls import path, include
from api.v1.applications.views import JobApplicantsView

urlpatterns = [
    # Authentication
    path("auth/",         include("api.v1.accounts.urls",      namespace="accounts")),

    # Profiles
    path("profiles/",     include("api.v1.profiles.urls",      namespace="profiles")),

    # Jobs — includes nested applicants route
    path("jobs/",         include("api.v1.jobs.urls",          namespace="jobs")),

    # Applications
    path("applications/", include("api.v1.applications.urls",  namespace="applications")),

    # Recruiter views applicants for a specific job (nested under jobs/)
    path(
        "jobs/<uuid:job_id>/applicants/",
        JobApplicantsView.as_view(),
        name="job-applicants",
    ),
]
