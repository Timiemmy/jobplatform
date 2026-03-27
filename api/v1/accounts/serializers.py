"""
All serializers for the accounts domain.

Rules enforced here:
- Input validation only — no business logic
- Sensitive fields (password) are write-only
- Role cannot be set to admin via public API
- Email uniqueness validated at serializer level for clear error messages
"""

from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.selectors import user_exists_by_email


class RegisterSerializer(serializers.Serializer):
    """
    Handles new user registration.

    Validates:
    - Email uniqueness
    - Password strength (min 8 chars, confirmed)
    - Role is job_seeker or recruiter only
    """

    email = serializers.EmailField()
    password = serializers.CharField(
        min_length=8,
        write_only=True,
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        min_length=8,
        write_only=True,
        style={"input_type": "password"},
    )
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(
        choices=[
            (User.Role.JOB_SEEKER, "Job Seeker"),
            (User.Role.RECRUITER, "Recruiter"),
        ]
    )

    def validate_email(self, value: str) -> str:
        normalised = value.lower().strip()
        if user_exists_by_email(email=normalised):
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return normalised

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs


class LoginSerializer(serializers.Serializer):
    """
    Validates login credentials and returns JWT token pair.

    Returns both access and refresh tokens so the client
    can immediately start making authenticated requests.
    """

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs: dict) -> dict:
        email = attrs["email"].lower().strip()
        password = attrs["password"]

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError(
                {"non_field_errors": _("Invalid email or password.")}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": _("This account has been deactivated.")}
            )

        # Generate token pair
        refresh = RefreshToken.for_user(user)

        return {
            "user": user,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class UserDetailsSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the authenticated user's own data.
    Returned by /auth/user/ and included in login/register responses.

    Deliberately excludes: password, is_staff, is_superuser, groups, permissions.
    """

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class TokenResponseSerializer(serializers.Serializer):
    """
    Shape of the token response returned after login or registration.
    Used by drf-spectacular for schema generation only.
    """

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserDetailsSerializer()


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Schema serializer for token refresh responses."""

    access = serializers.CharField()
    refresh = serializers.CharField()
