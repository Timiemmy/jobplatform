"""
conftest.py

Root-level pytest fixtures available to every test module.
Import fixtures directly — pytest discovers them automatically.

Usage in a test:
    def test_something(api_client, job_seeker_user, job_seeker_token):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {job_seeker_token}")
        ...
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client() -> APIClient:
    """Unauthenticated DRF APIClient."""
    return APIClient()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def job_seeker_user(db):
    """A persisted job seeker user."""
    from tests.factories import make_job_seeker
    return make_job_seeker(email="seeker@fixture.com")


@pytest.fixture
def recruiter_user(db):
    """A persisted recruiter user."""
    from tests.factories import make_recruiter
    return make_recruiter(email="recruiter@fixture.com")


@pytest.fixture
def admin_user(db):
    """A persisted admin user."""
    from tests.factories import make_admin
    return make_admin(email="admin@fixture.com")


# ---------------------------------------------------------------------------
# Token fixtures — return the raw access token string
# ---------------------------------------------------------------------------

@pytest.fixture
def job_seeker_token(job_seeker_user) -> str:
    """Valid JWT access token for the job seeker fixture user."""
    refresh = RefreshToken.for_user(job_seeker_user)
    return str(refresh.access_token)


@pytest.fixture
def recruiter_token(recruiter_user) -> str:
    """Valid JWT access token for the recruiter fixture user."""
    refresh = RefreshToken.for_user(recruiter_user)
    return str(refresh.access_token)


@pytest.fixture
def admin_token(admin_user) -> str:
    """Valid JWT access token for the admin fixture user."""
    refresh = RefreshToken.for_user(admin_user)
    return str(refresh.access_token)


# ---------------------------------------------------------------------------
# Authenticated client shortcuts
# ---------------------------------------------------------------------------

@pytest.fixture
def seeker_client(api_client, job_seeker_token) -> APIClient:
    """APIClient pre-authenticated as a job seeker."""
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {job_seeker_token}")
    return api_client


@pytest.fixture
def recruiter_client(api_client, recruiter_token) -> APIClient:
    """APIClient pre-authenticated as a recruiter."""
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {recruiter_token}")
    return api_client


@pytest.fixture
def admin_client(api_client, admin_token) -> APIClient:
    """APIClient pre-authenticated as an admin."""
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")
    return api_client
