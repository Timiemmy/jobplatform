"""
tests/jobs/test_services.py

Unit tests for apps/jobs/services.py.

Covers: create_job, update_job, delete_job
"""

from decimal import Decimal

from django.test import TestCase

from apps.jobs.models import Job
from apps.jobs.services import create_job, update_job, delete_job
from core.exceptions import ForbiddenError, NotFoundError
from tests.factories import make_recruiter, make_job_seeker, make_admin, make_job


class TestCreateJob(TestCase):

    def setUp(self):
        self.recruiter = make_recruiter(email="r@jobs.com")

    def _valid_data(self, **overrides) -> dict:
        data = {
            "title": "Senior Django Engineer",
            "description": (
                "We are seeking a senior Django engineer to build "
                "scalable APIs for our growing platform. You will "
                "lead architecture decisions and mentor junior engineers."
            ),
            "location": "Lagos, Nigeria",
            "job_type": Job.JobType.FULL_TIME,
            "experience_level": Job.ExperienceLevel.SENIOR,
            "salary_min": Decimal("80000"),
            "salary_max": Decimal("120000"),
        }
        data.update(overrides)
        return data

    def test_recruiter_creates_job_successfully(self):
        job = create_job(owner=self.recruiter, data=self._valid_data())
        self.assertIsInstance(job, Job)
        self.assertEqual(job.title, "Senior Django Engineer")
        self.assertEqual(job.owner, self.recruiter)

    def test_job_is_published_by_default(self):
        job = create_job(owner=self.recruiter, data=self._valid_data())
        self.assertEqual(job.status, Job.Status.PUBLISHED)

    def test_job_is_active_by_default(self):
        job = create_job(owner=self.recruiter, data=self._valid_data())
        self.assertTrue(job.is_active)

    def test_job_seeker_cannot_create_job(self):
        seeker = make_job_seeker(email="seeker@jobs.com")
        with self.assertRaises(ForbiddenError):
            create_job(owner=seeker, data=self._valid_data())

    def test_admin_cannot_create_job(self):
        admin = make_admin(email="admin@jobs.com")
        with self.assertRaises(ForbiddenError):
            create_job(owner=admin, data=self._valid_data())

    def test_uuid_primary_key_assigned(self):
        job = create_job(owner=self.recruiter, data=self._valid_data())
        self.assertIsNotNone(job.id)
        self.assertNotIsInstance(job.id, int)

    def test_salary_max_less_than_min_raises_value_error(self):
        data = self._valid_data(salary_min=Decimal("100000"), salary_max=Decimal("50000"))
        with self.assertRaises(ValueError) as ctx:
            create_job(owner=self.recruiter, data=data)
        self.assertIn("salary_max", str(ctx.exception))

    def test_salary_without_max_is_allowed(self):
        data = self._valid_data(salary_min=Decimal("50000"), salary_max=None)
        job = create_job(owner=self.recruiter, data=data)
        self.assertIsNone(job.salary_max)

    def test_job_persisted_to_database(self):
        create_job(owner=self.recruiter, data=self._valid_data())
        self.assertTrue(Job.objects.filter(owner=self.recruiter).exists())

    def test_job_can_be_created_as_draft(self):
        data = self._valid_data(status=Job.Status.DRAFT)
        job = create_job(owner=self.recruiter, data=data)
        self.assertEqual(job.status, Job.Status.DRAFT)


class TestUpdateJob(TestCase):

    def setUp(self):
        self.recruiter = make_recruiter(email="owner@jobs.com")
        self.job = make_job(owner=self.recruiter, title="Original Title")

    def test_owner_can_update_title(self):
        updated = update_job(job=self.job, owner=self.recruiter, data={"title": "New Title"})
        self.assertEqual(updated.title, "New Title")

    def test_update_persists_to_database(self):
        update_job(job=self.job, owner=self.recruiter, data={"location": "Abuja"})
        self.job.refresh_from_db()
        self.assertEqual(self.job.location, "Abuja")

    def test_non_owner_recruiter_cannot_update(self):
        other = make_recruiter(email="other@jobs.com")
        with self.assertRaises(ForbiddenError):
            update_job(job=self.job, owner=other, data={"title": "Hijacked"})

    def test_job_seeker_cannot_update_job(self):
        seeker = make_job_seeker(email="seeker@jobs.com")
        with self.assertRaises(ForbiddenError):
            update_job(job=self.job, owner=seeker, data={"title": "Hijacked"})

    def test_admin_can_update_any_job(self):
        admin = make_admin(email="admin@jobs.com")
        updated = update_job(job=self.job, owner=admin, data={"title": "Admin Updated"})
        self.assertEqual(updated.title, "Admin Updated")

    def test_soft_deleted_job_cannot_be_updated(self):
        self.job.is_active = False
        self.job.save(update_fields=["is_active"])
        with self.assertRaises(NotFoundError):
            update_job(job=self.job, owner=self.recruiter, data={"title": "Ghost"})

    def test_invalid_salary_range_raises_value_error(self):
        with self.assertRaises(ValueError):
            update_job(
                job=self.job,
                owner=self.recruiter,
                data={"salary_min": Decimal("200000"), "salary_max": Decimal("10000")},
            )

    def test_partial_update_does_not_wipe_other_fields(self):
        original_description = self.job.description
        update_job(job=self.job, owner=self.recruiter, data={"title": "Partial Update"})
        self.job.refresh_from_db()
        self.assertEqual(self.job.description, original_description)

    def test_returns_job_instance(self):
        result = update_job(job=self.job, owner=self.recruiter, data={"title": "Updated"})
        self.assertIsInstance(result, Job)


class TestDeleteJob(TestCase):

    def setUp(self):
        self.recruiter = make_recruiter(email="del@jobs.com")
        self.job = make_job(owner=self.recruiter)

    def test_owner_can_soft_delete_job(self):
        delete_job(job=self.job, owner=self.recruiter)
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_active)

    def test_deleted_job_status_is_closed(self):
        delete_job(job=self.job, owner=self.recruiter)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.CLOSED)

    def test_job_record_still_exists_after_delete(self):
        """Soft-delete — the row must remain in the DB."""
        delete_job(job=self.job, owner=self.recruiter)
        self.assertTrue(Job.objects.filter(id=self.job.id).exists())

    def test_non_owner_cannot_delete(self):
        other = make_recruiter(email="other_del@jobs.com")
        with self.assertRaises(ForbiddenError):
            delete_job(job=self.job, owner=other)

    def test_job_seeker_cannot_delete(self):
        seeker = make_job_seeker(email="seeker_del@jobs.com")
        with self.assertRaises(ForbiddenError):
            delete_job(job=self.job, owner=seeker)

    def test_admin_can_delete_any_job(self):
        admin = make_admin(email="admin_del@jobs.com")
        delete_job(job=self.job, owner=admin)
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_active)
