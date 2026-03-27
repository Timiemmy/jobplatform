from django.db.models import QuerySet

from apps.accounts.models import User


def get_user_by_id(*, user_id: str) -> User:
    """
    Fetch a single user by UUID.

    Raises:
        User.DoesNotExist: if not found
    """
    return User.objects.get(id=user_id)


def get_user_by_email(*, email: str) -> User:
    """
    Fetch a single active user by email.

    Raises:
        User.DoesNotExist: if not found
    """
    return User.objects.get(email=email, is_active=True)


def get_all_users() -> QuerySet[User]:
    """Return all active users. Admin use only."""
    return User.objects.filter(is_active=True).order_by("-created_at")


def get_users_by_role(*, role: str) -> QuerySet[User]:
    """Return all active users filtered by role."""
    return User.objects.filter(role=role, is_active=True).order_by("-created_at")


def user_exists_by_email(*, email: str) -> bool:
    """Check if an email is already registered."""
    return User.objects.filter(email=email).exists()
