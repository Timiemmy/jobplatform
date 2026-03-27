"""
api/v1/applications/views.py

Applications endpoints — thin views, all logic in services/selectors.

Endpoints:
    POST   /api/v1/applications/                        → job seeker applies
    GET    /api/v1/applications/                        → job seeker lists own applications
    GET    /api/v1/applications/{id}/                   → job seeker retrieves one application
    GET    /api/v1/jobs/{job_id}/applicants/            → recruiter views applicants
    PATCH  /api/v1/applications/{id}/status/            → recruiter updates status
    GET    /api/v1/applications/{id}/resume/            → download resume (owner or recruiter)
"""

import logging
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.applications.models import Application
from apps.applications.selectors import (
    get_applications_for_applicant,
    get_applications_for_job,
    get_application_by_id_for_applicant,
    get_application_for_recruiter,
    get_application_by_id,
)
from apps.applications.services import apply_to_job, update_application_status
from apps.jobs.models import Job
from apps.jobs.selectors import get_job_by_id
from api.v1.applications.serializers import (
    ApplySerializer,
    ApplicationSeekerSerializer,
    ApplicationRecruiterSerializer,
    StatusUpdateSerializer,
    RecruiterNotesSerializer,
)
from core.exceptions import NotFoundError, ForbiddenError
from core.pagination import StandardPageNumberPagination
from core.permissions import IsJobSeeker, IsRecruiter
from core.throttles import JobApplicationRateThrottle
from infrastructure.storage.backends import get_resume_url

logger = logging.getLogger(__name__)


class ApplicationListCreateView(APIView):
    """
    POST → Job seeker submits an application (multipart form).
    GET  → Job seeker lists their own applications.
    """

    pagination_class = StandardPageNumberPagination

    def get_permissions(self):
        return [IsAuthenticated(), IsJobSeeker()]

    def get_throttles(self):
        if self.request.method == "POST":
            return [JobApplicationRateThrottle()]
        return super().get_throttles()

    # multipart for file upload, json/form for GET
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        parameters=[
            OpenApiParameter("status", str, description="Filter by application status"),
            OpenApiParameter("page",   int, description="Page number"),
        ],
        responses={200: ApplicationSeekerSerializer(many=True)},
        summary="List own applications (job seeker)",
        tags=["Applications"],
    )
    def get(self, request):
        status_filter = request.query_params.get("status")
        qs = get_applications_for_applicant(
            applicant=request.user,
            status=status_filter or None,
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ApplicationSeekerSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "job_id":       {"type": "string", "format": "uuid"},
                    "resume":       {"type": "string", "format": "binary"},
                    "cover_letter": {"type": "string"},
                },
                "required": ["job_id", "resume"],
            }
        },
        responses={
            201: ApplicationSeekerSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Job seeker role required"),
            404: OpenApiResponse(description="Job not found"),
            409: OpenApiResponse(description="Already applied"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
        summary="Apply for a job (job seeker)",
        tags=["Applications"],
    )
    def post(self, request):
        job_id = request.data.get("job_id")
        if not job_id:
            return Response(
                {"error": True, "message": "job_id is required.", "detail": {}, "code": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        application = apply_to_job(
            applicant=request.user,
            job_id=str(job_id),
            resume_file=serializer.validated_data["resume"],
            cover_letter=serializer.validated_data.get("cover_letter", ""),
        )

        return Response(
            ApplicationSeekerSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


class ApplicationDetailView(APIView):
    """
    GET /api/v1/applications/{id}/
    Job seeker retrieves a single one of their own applications.
    """

    permission_classes = [IsAuthenticated, IsJobSeeker]

    @extend_schema(
        responses={
            200: ApplicationSeekerSerializer,
            403: OpenApiResponse(description="Not your application"),
            404: OpenApiResponse(description="Application not found"),
        },
        summary="Retrieve own application detail (job seeker)",
        tags=["Applications"],
    )
    def get(self, request, application_id: str):
        try:
            application = get_application_by_id_for_applicant(
                application_id=application_id,
                applicant=request.user,
            )
        except Application.DoesNotExist:
            raise NotFoundError("Application not found.")

        return Response(
            ApplicationSeekerSerializer(application).data,
            status=status.HTTP_200_OK,
        )


class JobApplicantsView(APIView):
    """
    GET /api/v1/jobs/{job_id}/applicants/
    Recruiter views all applicants for one of their job postings.
    """

    permission_classes = [IsAuthenticated, IsRecruiter]
    pagination_class   = StandardPageNumberPagination

    @extend_schema(
        parameters=[
            OpenApiParameter("status", str, description="Filter applicants by status"),
            OpenApiParameter("page",   int, description="Page number"),
        ],
        responses={
            200: ApplicationRecruiterSerializer(many=True),
            403: OpenApiResponse(description="Not your job"),
            404: OpenApiResponse(description="Job not found"),
        },
        summary="List applicants for a job (recruiter)",
        tags=["Applications"],
    )
    def get(self, request, job_id: str):
        try:
            job = Job.objects.get(id=job_id, owner=request.user, is_active=True)
        except Job.DoesNotExist:
            raise NotFoundError("Job not found or you do not own this job.")

        status_filter = request.query_params.get("status")
        qs = get_applications_for_job(job=job, status=status_filter or None)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ApplicationRecruiterSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ApplicationStatusUpdateView(APIView):
    """
    PATCH /api/v1/applications/{id}/status/
    Recruiter advances or rejects an application.
    """

    permission_classes = [IsAuthenticated, IsRecruiter]

    @extend_schema(
        request=StatusUpdateSerializer,
        responses={
            200: ApplicationRecruiterSerializer,
            400: OpenApiResponse(description="Invalid status transition"),
            403: OpenApiResponse(description="Not your job"),
            404: OpenApiResponse(description="Application not found"),
        },
        summary="Update application status (recruiter)",
        tags=["Applications"],
    )
    def patch(self, request, application_id: str):
        try:
            application = get_application_for_recruiter(
                application_id=application_id,
                recruiter=request.user,
            )
        except Application.DoesNotExist:
            raise NotFoundError("Application not found.")

        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        application = update_application_status(
            application=application,
            recruiter=request.user,
            new_status=serializer.validated_data["status"],
        )

        return Response(
            ApplicationRecruiterSerializer(application).data,
            status=status.HTTP_200_OK,
        )


class ApplicationResumeDownloadView(APIView):
    """
    GET /api/v1/applications/{id}/resume/

    Returns a short-lived URL to the applicant's resume file.

    Access rules:
      - Job seeker: only their own resume.
      - Recruiter:  only for applications on their jobs.
      - Admin:      any resume.

    Never returns the raw storage path — only a generated URL.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: {"type": "object", "properties": {"url": {"type": "string"}}},
            403: OpenApiResponse(description="Access denied"),
            404: OpenApiResponse(description="Application not found"),
        },
        summary="Get resume download URL",
        tags=["Applications"],
    )
    def get(self, request, application_id: str):
        try:
            application = get_application_by_id(application_id=application_id)
        except Application.DoesNotExist:
            raise NotFoundError("Application not found.")

        user = request.user

        # Access control
        if user.is_job_seeker and application.applicant != user:
            raise ForbiddenError("You can only access your own resume.")
        if user.is_recruiter and application.job.owner != user:
            raise ForbiddenError("You can only access resumes for your own job postings.")

        if not application.resume_path:
            raise NotFoundError("No resume file found for this application.")

        url = get_resume_url(path=application.resume_path)
        return Response({"url": url}, status=status.HTTP_200_OK)
