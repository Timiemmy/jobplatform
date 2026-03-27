"""
Thin views for the accounts domain.
No business logic lives here — all mutations go through services.py.

Endpoints:
    POST /api/v1/auth/register/   → Register a new user
    POST /api/v1/auth/login/      → Login, receive JWT pair
    POST /api/v1/auth/logout/     → Blacklist refresh token
    POST /api/v1/auth/token/refresh/ → Rotate access token
    GET  /api/v1/auth/user/       → Retrieve own user details
"""

import logging
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.accounts.services import register_user
from api.v1.accounts.serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserDetailsSerializer,
    TokenResponseSerializer,
    TokenRefreshResponseSerializer,
)
from core.exceptions import ApplicationError
from core.throttles import LoginRateThrottle, AnonBurstThrottle

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    """
    Register a new user account.

    Open to unauthenticated users.
    Returns JWT token pair immediately after registration
    so the client doesn't need a separate login call.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonBurstThrottle]

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: TokenResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
        summary="Register a new user",
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data

        try:
            user = register_user(
                email=validated["email"],
                password=validated["password"],
                first_name=validated["first_name"],
                last_name=validated["last_name"],
                role=validated["role"],
            )
        except ValueError as exc:
            raise ApplicationError(str(exc))

        # Issue tokens immediately
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserDetailsSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    Authenticate a user and return a JWT token pair.

    Rate limited to prevent brute-force attacks.
    Uses the login throttle scope defined in settings.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: TokenResponseSerializer,
            400: OpenApiResponse(description="Invalid credentials"),
        },
        summary="Login and receive JWT tokens",
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        user = validated["user"]

        logger.info("User logged in: %s", user.email)

        return Response(
            {
                "user": UserDetailsSerializer(user).data,
                "access": validated["access"],
                "refresh": validated["refresh"],
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    Logout the current user by blacklisting their refresh token.

    The client must also discard the access token on their side —
    it will expire naturally (15 min) since JWTs cannot be
    individually invalidated without a blacklist.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request={"application/json": {"type": "object", "properties": {"refresh": {"type": "string"}}}},
        responses={
            204: OpenApiResponse(description="Logged out successfully"),
            400: OpenApiResponse(description="Invalid or expired refresh token"),
        },
        summary="Logout and blacklist refresh token",
        tags=["Authentication"],
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"error": True, "message": "Refresh token is required.", "detail": "missing_refresh_token", "code": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            raise InvalidToken(str(exc))

        logger.info("User logged out: %s", request.user.email)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserDetailView(APIView):
    """
    Retrieve the authenticated user's own profile data.

    Used by clients to hydrate the current session.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: UserDetailsSerializer},
        summary="Get current authenticated user",
        tags=["Authentication"],
    )
    def get(self, request):
        serializer = UserDetailsSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomTokenRefreshView(TokenRefreshView):
    """
    Extends SimpleJWT's token refresh view with proper schema docs.
    Rotates the refresh token and issues a new access token.
    """

    @extend_schema(
        responses={200: TokenRefreshResponseSerializer},
        summary="Refresh access token",
        tags=["Authentication"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
