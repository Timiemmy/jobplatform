"""
apps/profiles/services.py

Business logic for the profiles domain.
All mutations go through here — views never touch the ORM directly.
"""

import logging
from typing import Any

from apps.accounts.models import User
from apps.profiles.models import Profile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Allowed field sets per role — prevents cross-role field pollution
# ---------------------------------------------------------------------------

_SHARED_FIELDS = {
    "phone_number",
    "location",
    "avatar_url",
    "bio",
}

_JOB_SEEKER_FIELDS = _SHARED_FIELDS | {
    "skills",
    "experience_years",
    "resume_url",
}

_RECRUITER_FIELDS = _SHARED_FIELDS | {
    "company_name",
    "company_website",
    "company_size",
    "company_description",
}


def _allowed_fields_for_role(role: str) -> set:
    if role == User.Role.JOB_SEEKER:
        return _JOB_SEEKER_FIELDS
    if role == User.Role.RECRUITER:
        return _RECRUITER_FIELDS
    # Admin can update any shared field
    return _SHARED_FIELDS


def update_profile(*, user: User, data: dict[str, Any]) -> Profile:
    """
    Update a user's profile with the supplied data.

    - Strips any fields that don't belong to the user's role.
      A job seeker cannot set company_name; a recruiter cannot set skills.
    - Only updates fields that are present in `data` (partial update).
    - Returns the updated Profile instance.

    Raises:
        Profile.DoesNotExist: if the profile doesn't exist (shouldn't happen
            after Phase 1 signal, but defensive).
    """
    profile = Profile.objects.get(user=user)
    allowed = _allowed_fields_for_role(user.role)

    updated_fields = []
    for field, value in data.items():
        if field not in allowed:
            logger.warning(
                "Ignoring disallowed field '%s' for role '%s' (user=%s)",
                field, user.role, user.email,
            )
            continue
        setattr(profile, field, value)
        updated_fields.append(field)

    if updated_fields:
        updated_fields.append("updated_at")
        profile.save(update_fields=updated_fields)
        logger.info(
            "Profile updated for user %s — fields: %s",
            user.email, updated_fields,
        )

    return profile
