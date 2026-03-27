"""
apps/accounts/services.py

All business logic for the accounts domain.
Views never touch the ORM directly — they delegate here.
"""

import logging
from django.db import transaction

from apps.accounts.models import User

logger = logging.getLogger(__name__)


def register_user(
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role: str,
) -> User:
    """
    Register a new user on the platform.

    - Validates role is a legal choice
    - Creates user atomically
    - Triggers profile creation (signal handles this — see apps/profiles)
    - Returns the created User instance

    Raises:
        ValueError: if the role is not a valid choice
        django.db.IntegrityError: if email already exists (caught at view layer)
    """

    if role not in User.Role.values:
        raise ValueError(
            f"Invalid role '{role}'. Must be one of: {', '.join(User.Role.values)}"
        )

    # Admin role cannot be self-assigned via the public API
    if role == User.Role.ADMIN:
        raise ValueError("The admin role cannot be assigned during registration.")

    with transaction.atomic():
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )
        logger.info("New user registered: %s (role=%s)", email, role)

    return user


def deactivate_user(*, user: User) -> User:
    """
    Soft-delete a user by marking them inactive.
    Does not remove the record from the database.
    """
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    logger.info("User deactivated: %s", user.email)
    return user


def change_user_role(*, user: User, new_role: str, performed_by: User) -> User:
    """
    Change a user's role. Only admins can do this.

    Raises:
        PermissionError: if the requesting user is not an admin
        ValueError: if the new_role is invalid
    """

    if not performed_by.is_platform_admin:
        raise PermissionError("Only admins can change user roles.")

    if new_role not in User.Role.values:
        raise ValueError(f"Invalid role: {new_role}")

    user.role = new_role
    user.save(update_fields=["role", "updated_at"])
    logger.info(
        "User %s role changed to %s by admin %s",
        user.email,
        new_role,
        performed_by.email,
    )
    return user
