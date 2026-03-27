"""
core/throttles.py

Named throttle scopes that map to the rates defined in settings:

    DEFAULT_THROTTLE_RATES = {
        "login":             "5/minute",
        "job_applications":  "10/hour",
    }

Attach to a view with:
    throttle_classes = [LoginRateThrottle]

or declare on the view:
    throttle_scope = "login"
"""

from rest_framework.throttling import ScopedRateThrottle, AnonRateThrottle


class LoginRateThrottle(ScopedRateThrottle):
    """
    Limits login attempts to 5 per minute per IP.
    Applies to unauthenticated users — prevents brute-force attacks.
    """
    scope = "login"


class JobApplicationRateThrottle(ScopedRateThrottle):
    """
    Limits job application submissions to 10 per hour per user.
    Prevents application spam from a single account.
    Applied only to authenticated job seekers.
    """
    scope = "job_applications"


class AnonBurstThrottle(AnonRateThrottle):
    """
    Short burst limit for anonymous endpoints (e.g., registration).
    Falls back to the 'anon' scope rate in settings.
    """
    scope = "anon"

