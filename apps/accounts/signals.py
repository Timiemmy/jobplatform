"""
Post-save signal that creates a Profile record whenever a new User is created.
This decouples profile creation from the registration service — the accounts
domain doesn't need to know about the profiles domain.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from apps.accounts.models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance: User, created: bool, **kwargs):
    """
    Automatically create a Profile when a new User is saved.
    Imported lazily to avoid circular imports at module load time.
    """
    if not created:
        return

    # Lazy import avoids circular dependency between accounts and profiles
    from apps.profiles.models import Profile

    Profile.objects.get_or_create(user=instance)
    logger.debug("Profile auto-created for user: %s", instance.email)
