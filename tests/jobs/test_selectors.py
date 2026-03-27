"""
tests/jobs/test_selectors.py

Unit tests for apps/jobs/selectors.py.

Verifies filtering, search, soft-delete visibility,
and ownership-scoped queries.
"""

from django.test import TestCase

from apps.jobs.models import Job
from apps.jobs.selectors import (
    get_published_jobs,
    get_job_by_id,
    get_jobs_by_recruiter,
    get_job_by_id_for_owner,
)
from tests.factories import make_job, make_recruiter


class TestGetPublishedJobs(TestCase):

    def test_returns_only_published_active_jobs(self):
        make_job(title="Published Job", status=Job.Status.PUBLISHED)
        make_job(title="Draft Job",     status=Job.Status.DRAFT)
        make_job(title="Closed Job",    status=Job.Status.CLOSED)
        make_job(title="Inactive Job",  status=Job.Status.PUBLISHED, is_active=False)

        results = list(get_published_jobs())
        titles = [j.title for j in results]

        self.assertIn("Published Job", titles)
        self.assertNotIn("Draft Job",     titles)
        self.assertNotIn("Closed Job",    titles)
        self.assertNotIn("Inactive Job",  titles)

    def test_search_matches_title(self):
        make_job(title="Python Backend Engineer")
        make_job(title="Java Frontend Developer")

        results = list(get_published_jobs(search="Python"))
        titles = [j.title for j in results]

        self.assertTrue(any("Python" in t for t in titles))
        self.assertFalse(any("Java" in t for t in titles))

    def test_search_matches_description(self):
        make_job(
            title="Generic Engineer",
            description=(
                "This role requires deep knowledge of machine learning "
                "and neural network architectures. You will design and "
                "implement production ML pipelines for our core platform."
            ),
        )
        make_job(title="Other Role")

        results = list(get_published_jobs(search="machine learning"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Generic Engineer")

    def test_filter_by_job_type(self):
        make_job(title="Full-Time Job",  job_type=Job.JobType.FULL_TIME)
        make_job(title="Contract Job",   job_type=Job.JobType.CONTRACT)

        results = list(get_published_jobs(job_type=Job.JobType.CONTRACT))
        titles = [j.title for j in results]

        self.assertIn("Contract Job", titles)
        self.assertNotIn("Full-Time Job", titles)

    def test_filter_by_experience_level(self):
        make_job(title="Senior Role", experience_level=Job.ExperienceLevel.SENIOR)
        make_job(title="Entry Role",  experience_level=Job.ExperienceLevel.ENTRY)

        results = list(get_published_jobs(experience_level=Job.ExperienceLevel.SENIOR))
        titles = [j.title for j in results]

        self.assertIn("Senior Role", titles)
        self.assertNotIn("Entry Role", titles)

    def test_filter_by_location(self):
        make_job(title="Lagos Job",  location="Lagos, Nigeria")
        make_job(title="Abuja Job",  location="Abuja, Nigeria")
        make_job(title="London Job", location="London, UK")

        results = list(get_published_jobs(location="Nigeria"))
        titles = [j.title for j in results]

        self.assertIn("Lagos Job", titles)
        self.assertIn("Abuja Job", titles)
        self.assertNotIn("London Job", titles)

    def test_filter_by_salary_min(self):
        from decimal import Decimal
        make_job(title="High Pay", salary_min=Decimal("100000"), salary_max=Decimal("150000"))
        make_job(title="Low Pay",  salary_min=Decimal("20000"),  salary_max=Decimal("40000"))

        results = list(get_published_jobs(salary_min=80000))
        titles = [j.title for j in results]

        self.assertIn("High Pay", titles)
        self.assertNotIn("Low Pay", titles)

    def test_filter_by_salary_max(self):
        from decimal import Decimal
        make_job(title="Affordable Job", salary_min=Decimal("30000"), salary_max=Decimal("50000"))
        make_job(title="Expensive Job",  salary_min=Decimal("80000"), salary_max=Decimal("200000"))

        results = list(get_published_jobs(salary_max=60000))
        titles = [j.title for j in results]

        self.assertIn("Affordable Job", titles)
        self.assertNotIn("Expensive Job", titles)

    def test_combined_filters(self):
        make_job(
            title="Target Job",
            job_type=Job.JobType.REMOTE,
            experience_level=Job.ExperienceLevel.SENIOR,
            location="Remote",
        )
        make_job(
            title="Wrong Level",
            job_type=Job.JobType.REMOTE,
            experience_level=Job.ExperienceLevel.ENTRY,
        )

        results = list(get_published_jobs(
            job_type=Job.JobType.REMOTE,
            experience_level=Job.ExperienceLevel.SENIOR,
        ))
        titles = [j.title for j in results]

        self.assertIn("Target Job",  titles)
        self.assertNotIn("Wrong Level", titles)

    def test_returns_queryset_not_list(self):
        from django.db.models import QuerySet
        result = get_published_jobs()
        self.assertIsInstance(result, QuerySet)

    def test_no_filters_returns_all_published_jobs(self):
        make_job()
        make_job()
        make_job()
        count = get_published_jobs().count()
        self.assertGreaterEqual(count, 3)


class TestGetJobById(TestCase):

    def test_returns_active_published_job(self):
        job = make_job()
        result = get_job_by_id(job_id=str(job.id))
        self.assertEqual(result, job)

    def test_raises_does_not_exist_for_soft_deleted(self):
        job = make_job(is_active=False)
        with self.assertRaises(Job.DoesNotExist):
            get_job_by_id(job_id=str(job.id))

    def test_raises_does_not_exist_for_unknown_id(self):
        import uuid
        with self.assertRaises(Job.DoesNotExist):
            get_job_by_id(job_id=str(uuid.uuid4()))

    def test_select_related_owner_avoids_extra_queries(self):
        """Owner must be pre-fetched — accessing it should not hit DB again."""
        job = make_job()
        result = get_job_by_id(job_id=str(job.id))
        # Access owner — if select_related works, no extra query
        with self.assertNumQueries(0):
            _ = result.owner.email


class TestGetJobsByRecruiter(TestCase):

    def test_returns_only_recruiter_owned_jobs(self):
        recruiter_a = make_recruiter(email="a@sel.com")
        recruiter_b = make_recruiter(email="b@sel.com")

        job_a = make_job(owner=recruiter_a, title="A's Job")
        job_b = make_job(owner=recruiter_b, title="B's Job")

        results = list(get_jobs_by_recruiter(recruiter=recruiter_a))
        titles = [j.title for j in results]

        self.assertIn("A's Job", titles)
        self.assertNotIn("B's Job", titles)

    def test_includes_draft_and_closed_jobs(self):
        recruiter = make_recruiter(email="all@sel.com")
        make_job(owner=recruiter, title="Published", status=Job.Status.PUBLISHED)
        make_job(owner=recruiter, title="Draft",     status=Job.Status.DRAFT)
        make_job(owner=recruiter, title="Closed",    status=Job.Status.CLOSED)

        results = list(get_jobs_by_recruiter(recruiter=recruiter))
        titles = [j.title for j in results]

        self.assertIn("Published", titles)
        self.assertIn("Draft",     titles)
        self.assertIn("Closed",    titles)

    def test_excludes_soft_deleted_jobs(self):
        recruiter = make_recruiter(email="del@sel.com")
        make_job(owner=recruiter, title="Deleted", is_active=False)

        results = list(get_jobs_by_recruiter(recruiter=recruiter))
        titles = [j.title for j in results]
        self.assertNotIn("Deleted", titles)

    def test_returns_queryset(self):
        from django.db.models import QuerySet
        recruiter = make_recruiter(email="qs@sel.com")
        self.assertIsInstance(get_jobs_by_recruiter(recruiter=recruiter), QuerySet)


class TestGetJobByIdForOwner(TestCase):

    def test_returns_job_when_owner_matches(self):
        recruiter = make_recruiter(email="own@sel.com")
        job = make_job(owner=recruiter)
        result = get_job_by_id_for_owner(job_id=str(job.id), owner=recruiter)
        self.assertEqual(result, job)

    def test_raises_for_wrong_owner(self):
        recruiter_a = make_recruiter(email="oa@sel.com")
        recruiter_b = make_recruiter(email="ob@sel.com")
        job = make_job(owner=recruiter_a)
        with self.assertRaises(Job.DoesNotExist):
            get_job_by_id_for_owner(job_id=str(job.id), owner=recruiter_b)

    def test_raises_for_soft_deleted_job(self):
        recruiter = make_recruiter(email="del_own@sel.com")
        job = make_job(owner=recruiter, is_active=False)
        with self.assertRaises(Job.DoesNotExist):
            get_job_by_id_for_owner(job_id=str(job.id), owner=recruiter)
