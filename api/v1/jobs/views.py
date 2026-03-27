"""
api/v1/jobs/views.py

Jobs endpoints — thin views, all business logic in services/selectors.

Caching:
  - GET /jobs/       → cache-aside, keyed on query params, 2-min TTL
  - GET /jobs/{id}/  → cache-aside, keyed on job UUID, 5-min TTL
  - POST/PATCH/DELETE → invalidate cache via invalidate_job_cache()

Endpoints:
    GET    /api/v1/jobs/            → list published jobs
    POST   /api/v1/jobs/            → create job (recruiter only)
    GET    /api/v1/jobs/mine/       → recruiter's own jobs
    GET    /api/v1/jobs/{id}/       → retrieve single job
    PATCH  /api/v1/jobs/{id}/       → update job (owner only)
    DELETE /api/v1/jobs/{id}/       → soft-delete job (owner only)
"""

import logging
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from apps.jobs.models import Job
from apps.jobs.selectors import (
    get_published_jobs,
    get_job_by_id,
    get_jobs_by_recruiter,
)
from apps.jobs.services import create_job, update_job, delete_job
from api.v1.jobs.serializers import (
    JobListSerializer,
    JobDetailSerializer,
    JobCreateSerializer,
    JobUpdateSerializer,
)
from api.v1.jobs.filters import JobFilter
from core.cache import (
    get_cached_job_list,
    set_cached_job_list,
    get_cached_job_detail,
    set_cached_job_detail,
    invalidate_job_cache,
)
from core.exceptions import NotFoundError, ApplicationError
from core.pagination import StandardPageNumberPagination
from core.permissions import IsRecruiter, IsRecruiterOwnerOrAdmin

logger = logging.getLogger(__name__)


class JobListCreateView(APIView):
    """
    GET  → Public paginated job listing with search, filters, and caching.
    POST → Recruiter creates a new job (invalidates list cache).
    """

    pagination_class = StandardPageNumberPagination

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), IsRecruiter()]

    @extend_schema(
        parameters=[
            OpenApiParameter("search",           str,   description="Search title and description"),
            OpenApiParameter("location",         str,   description="Filter by location (partial match)"),
            OpenApiParameter("job_type",         str,   description="Filter by job type"),
            OpenApiParameter("experience_level", str,   description="Filter by experience level"),
            OpenApiParameter("salary_min",       float, description="Minimum salary (gte)"),
            OpenApiParameter("salary_max",       float, description="Maximum salary (lte)"),
            OpenApiParameter("page",             int,   description="Page number"),
            OpenApiParameter("page_size",        int,   description="Results per page (max 100)"),
        ],
        responses={200: JobListSerializer(many=True)},
        summary="List published jobs",
        tags=["Jobs"],
    )
    def get(self, request):
        # Build normalised params dict for cache key
        params = dict(request.query_params)

        # Cache hit
        cached = get_cached_job_list(params=params)
        if cached is not None:
            logger.debug("Job list cache HIT: params=%s", params)
            return Response(cached)

        # Cache miss — query + paginate
        filterset = JobFilter(request.query_params, queryset=get_published_jobs())
        if not filterset.is_valid():
            return Response(filterset.errors, status=status.HTTP_400_BAD_REQUEST)
        qs = filterset.qs

        search_term = request.query_params.get("search", "").strip()
        if search_term:
            qs = qs.filter(
                Q(title__icontains=search_term) | Q(description__icontains=search_term)
            )

        paginator  = self.pagination_class()
        page       = paginator.paginate_queryset(qs, request)
        serializer = JobListSerializer(page, many=True)
        response   = paginator.get_paginated_response(serializer.data)

        # Populate cache
        set_cached_job_list(params=params, data=response.data)

        return response

    @extend_schema(
        request=JobCreateSerializer,
        responses={
            201: JobDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Recruiter role required"),
        },
        summary="Create a job posting (recruiter only)",
        tags=["Jobs"],
    )
    def post(self, request):
        serializer = JobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            job = create_job(owner=request.user, data=serializer.validated_data)
        except ValueError as exc:
            raise ApplicationError(str(exc))

        # Any new job invalidates the list cache
        invalidate_job_cache(job_id=str(job.id))

        logger.info("Job created: id=%s by=%s", job.id, request.user.email)
        return Response(JobDetailSerializer(job).data, status=status.HTTP_201_CREATED)


class JobDetailView(APIView):
    """
    GET    → Retrieve a single published job (public, cached).
    PATCH  → Partial update (owner recruiter or admin, cache-invalidating).
    DELETE → Soft-delete (owner recruiter or admin, cache-invalidating).
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), IsRecruiterOwnerOrAdmin()]

    def _get_job_or_404(self, job_id: str) -> Job:
        try:
            return get_job_by_id(job_id=job_id)
        except Job.DoesNotExist:
            raise NotFoundError("Job not found.")

    @extend_schema(
        responses={
            200: JobDetailSerializer,
            404: OpenApiResponse(description="Job not found"),
        },
        summary="Retrieve a job posting",
        tags=["Jobs"],
    )
    def get(self, request, job_id: str):
        job_id_str = str(job_id)

        cached = get_cached_job_detail(job_id=job_id_str)
        if cached is not None:
            logger.debug("Job detail cache HIT: id=%s", job_id_str)
            return Response(cached)

        job        = self._get_job_or_404(job_id_str)
        serializer = JobDetailSerializer(job)
        set_cached_job_detail(job_id=job_id_str, data=serializer.data)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=JobUpdateSerializer,
        responses={
            200: JobDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Not the job owner"),
            404: OpenApiResponse(description="Job not found"),
        },
        summary="Update a job posting (owner or admin)",
        tags=["Jobs"],
    )
    def patch(self, request, job_id: str):
        job = self._get_job_or_404(str(job_id))
        self.check_object_permissions(request, job)

        serializer = JobUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            job = update_job(job=job, owner=request.user, data=serializer.validated_data)
        except ValueError as exc:
            raise ApplicationError(str(exc))

        invalidate_job_cache(job_id=str(job.id))

        return Response(JobDetailSerializer(job).data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Job deleted"),
            403: OpenApiResponse(description="Not the job owner"),
            404: OpenApiResponse(description="Job not found"),
        },
        summary="Delete a job posting (owner or admin)",
        tags=["Jobs"],
    )
    def delete(self, request, job_id: str):
        job = self._get_job_or_404(str(job_id))
        self.check_object_permissions(request, job)
        delete_job(job=job, owner=request.user)
        invalidate_job_cache(job_id=str(job.id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyJobsView(APIView):
    """
    GET /api/v1/jobs/mine/
    Recruiter's own listings — not cached (owner-specific, low volume).
    """

    permission_classes = [IsAuthenticated, IsRecruiter]
    pagination_class   = StandardPageNumberPagination

    @extend_schema(
        responses={200: JobListSerializer(many=True)},
        summary="List own job postings (recruiter only)",
        tags=["Jobs"],
    )
    def get(self, request):
        qs         = get_jobs_by_recruiter(recruiter=request.user)
        paginator  = self.pagination_class()
        page       = paginator.paginate_queryset(qs, request)
        serializer = JobListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
