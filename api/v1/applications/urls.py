"""
api/v1/applications/urls.py

URL routes for the applications domain.

Note on job applicants route:
  /jobs/{job_id}/applicants/ lives here but is included under
  the /jobs/ prefix in api/v1/urls.py — keeping domain routes
  together even when the URL nests under another resource.
"""

from django.urls import path
from api.v1.applications.views import (
    ApplicationListCreateView,
    ApplicationDetailView,
    ApplicationStatusUpdateView,
    ApplicationResumeDownloadView,
)

app_name = "applications"

urlpatterns = [
    # Job seeker: apply + list own applications
    path(
        "",
        ApplicationListCreateView.as_view(),
        name="application-list-create",
    ),
    # Job seeker: retrieve single application
    path(
        "<uuid:application_id>/",
        ApplicationDetailView.as_view(),
        name="application-detail",
    ),
    # Recruiter: update application status
    path(
        "<uuid:application_id>/status/",
        ApplicationStatusUpdateView.as_view(),
        name="application-status-update",
    ),
    # Shared: get resume download URL
    path(
        "<uuid:application_id>/resume/",
        ApplicationResumeDownloadView.as_view(),
        name="application-resume-download",
    ),
]
