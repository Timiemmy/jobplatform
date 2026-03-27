"""
api/v1/profiles/views.py

Profile endpoints — thin views, all logic in services/selectors.

Endpoints:
    GET   /api/v1/profiles/me/       → Retrieve own profile
    PATCH /api/v1/profiles/me/       → Update own profile (partial)
"""

import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.accounts.models import User
from apps.profiles.selectors import get_profile_by_user
from apps.profiles.services import update_profile
from api.v1.profiles.serializers import (
    ProfileReadSerializer,
    JobSeekerProfileUpdateSerializer,
    RecruiterProfileUpdateSerializer,
    SharedProfileUpdateSerializer,
)
from core.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class MyProfileView(APIView):
    """
    Retrieve or update the authenticated user's own profile.

    GET  → returns full profile data
    PATCH → partial update; serializer selected based on user role
    """

    permission_classes = [IsAuthenticated]

    def _get_update_serializer_class(self, user: User):
        """Return the correct update serializer for the user's role."""
        if user.role == User.Role.JOB_SEEKER:
            return JobSeekerProfileUpdateSerializer
        if user.role == User.Role.RECRUITER:
            return RecruiterProfileUpdateSerializer
        return SharedProfileUpdateSerializer   # admin

    @extend_schema(
        responses={200: ProfileReadSerializer},
        summary="Retrieve own profile",
        tags=["Profiles"],
    )
    def get(self, request):
        try:
            profile = get_profile_by_user(user=request.user)
        except Exception:
            raise NotFoundError("Profile not found.")

        serializer = ProfileReadSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=JobSeekerProfileUpdateSerializer,  # shown in docs; actual depends on role
        responses={
            200: ProfileReadSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
        summary="Update own profile (partial)",
        tags=["Profiles"],
    )
    def patch(self, request):
        serializer_class = self._get_update_serializer_class(request.user)
        serializer = serializer_class(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        profile = update_profile(
            user=request.user,
            data=serializer.validated_data,
        )

        logger.info("Profile updated: user=%s", request.user.email)
        return Response(
            ProfileReadSerializer(profile).data,
            status=status.HTTP_200_OK,
        )
