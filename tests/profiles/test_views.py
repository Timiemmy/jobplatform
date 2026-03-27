"""
tests/profiles/test_views.py

Integration tests for profile API endpoints.

Endpoints covered:
    GET   /api/v1/profiles/me/
    PATCH /api/v1/profiles/me/
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.profiles.models import Profile
from tests.factories import make_job_seeker, make_recruiter, make_admin


def _auth_client(user) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


class TestMyProfileRetrieve(TestCase):
    """GET /api/v1/profiles/me/"""

    def setUp(self):
        self.url = reverse("profiles:my-profile")
        self.seeker = make_job_seeker(
            email="seeker@profile.com",
            first_name="Alice",
            last_name="Smith",
        )
        self.client = _auth_client(self.seeker)

    def test_returns_200_for_authenticated_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_user_identity_fields(self):
        response = self.client.get(self.url)
        self.assertEqual(response.data["email"], "seeker@profile.com")
        self.assertEqual(response.data["first_name"], "Alice")
        self.assertEqual(response.data["last_name"], "Smith")
        self.assertEqual(response.data["role"], "job_seeker")

    def test_response_contains_all_expected_fields(self):
        response = self.client.get(self.url)
        expected = {
            "id", "email", "first_name", "last_name", "role",
            "bio", "phone_number", "location", "avatar_url",
            "skills", "experience_years", "resume_url",
            "company_name", "company_website", "company_size", "company_description",
            "created_at", "updated_at",
        }
        self.assertEqual(set(response.data.keys()), expected)

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recruiter_can_retrieve_own_profile(self):
        recruiter = make_recruiter(email="recruiter@profile.com")
        response = _auth_client(recruiter).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "recruiter")

    def test_admin_can_retrieve_own_profile(self):
        admin = make_admin(email="admin@profile.com")
        response = _auth_client(admin).get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestMyProfileUpdate(TestCase):
    """PATCH /api/v1/profiles/me/"""

    def setUp(self):
        self.url = reverse("profiles:my-profile")

    # ------------------------------------------------------------------
    # Job seeker updates
    # ------------------------------------------------------------------

    def test_job_seeker_can_update_bio(self):
        seeker = make_job_seeker(email="s1@profile.com")
        response = _auth_client(seeker).patch(
            self.url, {"bio": "Passionate developer."}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["bio"], "Passionate developer.")

    def test_job_seeker_can_update_skills(self):
        seeker = make_job_seeker(email="s2@profile.com")
        response = _auth_client(seeker).patch(
            self.url, {"skills": ["Python", "Django"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Python", response.data["skills"])

    def test_job_seeker_can_update_experience_years(self):
        seeker = make_job_seeker(email="s3@profile.com")
        response = _auth_client(seeker).patch(
            self.url, {"experience_years": 3}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["experience_years"], 3)

    def test_job_seeker_company_name_is_ignored(self):
        """company_name is stripped for job seekers — response still 200."""
        seeker = make_job_seeker(email="s4@profile.com")
        response = _auth_client(seeker).patch(
            self.url, {"company_name": "Acme Corp"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The field must not have been written
        self.assertEqual(response.data["company_name"], "")

    def test_job_seeker_negative_experience_years_returns_400(self):
        seeker = make_job_seeker(email="s5@profile.com")
        response = _auth_client(seeker).patch(
            self.url, {"experience_years": -1}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_job_seeker_too_many_skills_returns_400(self):
        seeker = make_job_seeker(email="s6@profile.com")
        skills = [f"skill_{i}" for i in range(51)]  # max is 50
        response = _auth_client(seeker).patch(
            self.url, {"skills": skills}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Recruiter updates
    # ------------------------------------------------------------------

    def test_recruiter_can_update_company_name(self):
        recruiter = make_recruiter(email="r1@profile.com")
        response = _auth_client(recruiter).patch(
            self.url, {"company_name": "TechCorp"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["company_name"], "TechCorp")

    def test_recruiter_can_update_company_size(self):
        recruiter = make_recruiter(email="r2@profile.com")
        response = _auth_client(recruiter).patch(
            self.url, {"company_size": Profile.CompanySize.STARTUP}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["company_size"], Profile.CompanySize.STARTUP)

    def test_recruiter_skills_field_is_ignored(self):
        """skills is stripped for recruiters — response still 200."""
        recruiter = make_recruiter(email="r3@profile.com")
        response = _auth_client(recruiter).patch(
            self.url, {"skills": ["Python"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["skills"], [])

    def test_recruiter_invalid_company_size_returns_400(self):
        recruiter = make_recruiter(email="r4@profile.com")
        response = _auth_client(recruiter).patch(
            self.url, {"company_size": "mega_corp"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # General behaviour
    # ------------------------------------------------------------------

    def test_patch_returns_full_profile_in_response(self):
        seeker = make_job_seeker(email="full@profile.com")
        response = _auth_client(seeker).patch(
            self.url, {"bio": "Updated."}, format="json"
        )
        self.assertIn("id", response.data)
        self.assertIn("email", response.data)
        self.assertIn("role", response.data)

    def test_unauthenticated_patch_returns_401(self):
        response = APIClient().patch(
            self.url, {"bio": "Hacker"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_partial_update_preserves_untouched_fields(self):
        seeker = make_job_seeker(email="preserve@profile.com")
        # First update — set bio
        _auth_client(seeker).patch(self.url, {"bio": "Original bio."}, format="json")
        # Second update — set location only
        response = _auth_client(seeker).patch(self.url, {"location": "Abuja"}, format="json")
        self.assertEqual(response.data["bio"], "Original bio.")
        self.assertEqual(response.data["location"], "Abuja")

    def test_invalid_avatar_url_returns_400(self):
        seeker = make_job_seeker(email="avatar@profile.com")
        response = _auth_client(seeker).patch(
            self.url, {"avatar_url": "not-a-url"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
