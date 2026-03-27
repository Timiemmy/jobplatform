"""
api/v1/jobs/urls.py

URL routes for the jobs domain under /api/v1/jobs/.

Note: /mine/ must come BEFORE /{job_id}/ to avoid being matched
as a UUID route — Django matches top-to-bottom.
"""

from django.urls import path
from api.v1.jobs.views import JobListCreateView, JobDetailView, MyJobsView

app_name = "jobs"

urlpatterns = [
    # Must appear before <job_id> to avoid routing conflict
    path("mine/",        MyJobsView.as_view(),        name="my-jobs"),

    path("",             JobListCreateView.as_view(),  name="job-list-create"),
    path("<uuid:job_id>/", JobDetailView.as_view(),    name="job-detail"),
]
