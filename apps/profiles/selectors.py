"""
apps/profiles/selectors.py

Read-only query logic for the profiles domain.
Returns model instances — never raw dicts.
"""

from apps.accounts.models import User
from apps.profiles.models import Profile


def get_profile_by_user(*, user: User) -> Profile:
    """
    Fetch a user's profile with user pre-fetched.
    Raises Profile.DoesNotExist if not found.
    """
    return Profile.objects.select_related("user").get(user=user)


def get_profile_by_user_id(*, user_id: str) -> Profile:
    """
    Fetch a profile by the owner's UUID.
    Raises Profile.DoesNotExist if not found.
    """
    return Profile.objects.select_related("user").get(user__id=user_id)
