"""
tests/profiles/test_services.py

Unit tests for apps/profiles/services.py — update_profile().

Tests verify:
- Shared fields update for any role
- Role-specific fields are accepted for the correct role
- Cross-role fields are silently stripped (not rejected with error)
- Partial updates only touch supplied fields
- Returned instance reflects new values
"""

from django.test import TestCase

from apps.profiles.models import Profile
from apps.profiles.services import update_profile
from tests.factories import make_job_seeker, make_recruiter, make_admin


class TestUpdateProfileJobSeeker(TestCase):

    def setUp(self):
        self.user = make_job_seeker(email="seeker@svc.com")
        self.profile = Profile.objects.get(user=self.user)

    def test_updates_shared_bio_field(self):
        update_profile(user=self.user, data={"bio": "I love coding."})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "I love coding.")

    def test_updates_shared_location_field(self):
        update_profile(user=self.user, data={"location": "Lagos, Nigeria"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.location, "Lagos, Nigeria")

    def test_updates_shared_phone_number(self):
        update_profile(user=self.user, data={"phone_number": "+2348012345678"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone_number, "+2348012345678")

    def test_updates_job_seeker_skills(self):
        update_profile(user=self.user, data={"skills": ["Python", "Django", "PostgreSQL"]})
        self.profile.refresh_from_db()
        self.assertIn("Python", self.profile.skills)

    def test_updates_experience_years(self):
        update_profile(user=self.user, data={"experience_years": 4})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.experience_years, 4)

    def test_job_seeker_cannot_set_company_name(self):
        """company_name is a recruiter field — must be silently ignored."""
        update_profile(user=self.user, data={"company_name": "Acme Corp"})
        self.profile.refresh_from_db()
        # Field must remain blank — not written
        self.assertEqual(self.profile.company_name, "")

    def test_job_seeker_cannot_set_company_size(self):
        update_profile(user=self.user, data={"company_size": Profile.CompanySize.STARTUP})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.company_size, "")

    def test_partial_update_does_not_clear_untouched_fields(self):
        """Only supplied fields should change; others stay as-is."""
        self.profile.bio = "Original bio"
        self.profile.save(update_fields=["bio"])

        update_profile(user=self.user, data={"location": "Abuja"})
        self.profile.refresh_from_db()

        # bio should still be the original value
        self.assertEqual(self.profile.bio, "Original bio")
        self.assertEqual(self.profile.location, "Abuja")

    def test_returns_profile_instance(self):
        result = update_profile(user=self.user, data={"bio": "Test"})
        self.assertIsInstance(result, Profile)

    def test_empty_data_dict_does_not_raise(self):
        """Calling with no data is a no-op — must not raise or corrupt data."""
        try:
            update_profile(user=self.user, data={})
        except Exception as e:
            self.fail(f"update_profile raised unexpectedly: {e}")


class TestUpdateProfileRecruiter(TestCase):

    def setUp(self):
        self.user = make_recruiter(email="recruiter@svc.com")
        self.profile = Profile.objects.get(user=self.user)

    def test_updates_company_name(self):
        update_profile(user=self.user, data={"company_name": "TechCorp Nigeria"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.company_name, "TechCorp Nigeria")

    def test_updates_company_size(self):
        update_profile(user=self.user, data={"company_size": Profile.CompanySize.MEDIUM})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.company_size, Profile.CompanySize.MEDIUM)

    def test_updates_company_website(self):
        update_profile(user=self.user, data={"company_website": "https://techcorp.ng"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.company_website, "https://techcorp.ng")

    def test_recruiter_cannot_set_skills(self):
        """skills is a job_seeker field — must be silently ignored for recruiter."""
        update_profile(user=self.user, data={"skills": ["Python", "Django"]})
        self.profile.refresh_from_db()
        # skills default is an empty list — must remain so
        self.assertEqual(self.profile.skills, [])

    def test_recruiter_cannot_set_experience_years(self):
        update_profile(user=self.user, data={"experience_years": 5})
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.experience_years)

    def test_recruiter_can_update_shared_bio(self):
        update_profile(user=self.user, data={"bio": "We hire great talent."})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "We hire great talent.")


class TestUpdateProfileAdmin(TestCase):

    def setUp(self):
        self.user = make_admin(email="admin@svc.com")
        self.profile = Profile.objects.get(user=self.user)

    def test_admin_can_update_shared_fields(self):
        update_profile(user=self.user, data={"bio": "Platform admin.", "location": "Remote"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "Platform admin.")
        self.assertEqual(self.profile.location, "Remote")

    def test_admin_cannot_set_role_specific_fields(self):
        """Admin gets shared fields only — no job-seeker or recruiter fields."""
        update_profile(user=self.user, data={"skills": ["Python"], "company_name": "Acme"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.skills, [])
        self.assertEqual(self.profile.company_name, "")
