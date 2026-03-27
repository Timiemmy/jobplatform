"""
core/permissions.py

Reusable role-based permission classes.
All views use these — never check roles inline in views or serializers.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.accounts.models import User


class IsJobSeeker(BasePermission):
    """Grants access only to authenticated users with the job_seeker role."""

    message = "Only job seekers can perform this action."

    def has_permission(self, request, view) -> bool:
        return (
            request.user.is_authenticated
            and request.user.role == User.Role.JOB_SEEKER
        )


class IsRecruiter(BasePermission):
    """Grants access only to authenticated users with the recruiter role."""

    message = "Only recruiters can perform this action."

    def has_permission(self, request, view) -> bool:
        return (
            request.user.is_authenticated
            and request.user.role == User.Role.RECRUITER
        )


class IsAdmin(BasePermission):
    """Grants access only to admin users."""

    message = "Only admins can perform this action."

    def has_permission(self, request, view) -> bool:
        return (
            request.user.is_authenticated
            and request.user.role == User.Role.ADMIN
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission.
    Grants access if the requesting user owns the object or is an admin.
    The model must expose an `owner` or `user` field.
    """

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.role == User.Role.ADMIN:
            return True
        owner = getattr(obj, "owner", None) or getattr(obj, "user", None)
        return owner == request.user


class IsRecruiterOwnerOrAdmin(BasePermission):
    """
    Object-level permission for job-related resources.
    Grants write access to the recruiter who owns the job, or admins.
    Read access open to any authenticated user.
    """

    message = "Only the recruiter who posted this job can modify it."

    def has_permission(self, request, view) -> bool:
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        if request.user.role == User.Role.ADMIN:
            return True
        owner = getattr(obj, "owner", None)
        return owner == request.user
