"""
tests/applications/test_selectors.py

Unit tests for apps/applications/selectors.py.
"""

from django.test import TestCase

from apps.applications.models import Application
from apps.applications.selectors import (
    get_applications_for_applicant,
    get_applications_for_job,
    get_application_by_id,
    get_application_by_id_for_applicant,
    get_application_for_recruiter,
)
from tests.factories import (
    make_job_seeker,
    make_recruiter,
    make_job,
    make_application,
)


class TestGetApplicationsForApplicant(TestCase):

    def test_returns_only_own_applications(self):
        seeker_a = make_job_seeker(email="a@sel.com")
        seeker_b = make_job_seeker(email="b@sel.com")
        app_a = make_application(applicant=seeker_a)
        make_application(applicant=seeker_b)

        results = list(get_applications_for_applicant(applicant=seeker_a))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], app_a)

    def test_returns_all_statuses_when_no_filter(self):
        seeker = make_job_seeker(email="all@sel.com")
        recruiter = make_recruiter(email="r@sel.com")
        job = make_job(owner=recruiter)
        for s in [Application.Status.APPLIED, Application.Status.REVIEWED]:
            make_application(applicant=seeker, job=make_job(owner=recruiter), status=s)

        results = list(get_applications_for_applicant(applicant=seeker))
        self.assertEqual(len(results), 2)

    def test_filters_by_status(self):
        seeker = make_job_seeker(email="filter@sel.com")
        recruiter = make_recruiter(email="rf@sel.com")
        make_application(applicant=seeker, job=make_job(owner=recruiter), status=Application.Status.APPLIED)
        make_application(applicant=seeker, job=make_job(owner=recruiter), status=Application.Status.REVIEWED)

        results = list(
            get_applications_for_applicant(applicant=seeker, status=Application.Status.REVIEWED)
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Application.Status.REVIEWED)

    def test_returns_queryset(self):
        from django.db.models import QuerySet
        seeker = make_job_seeker(email="qs@sel.com")
        self.assertIsInstance(get_applications_for_applicant(applicant=seeker), QuerySet)

    def test_empty_result_when_no_applications(self):
        seeker = make_job_seeker(email="empty@sel.com")
        self.assertEqual(get_applications_for_applicant(applicant=seeker).count(), 0)


class TestGetApplicationsForJob(TestCase):

    def test_returns_all_applicants_for_job(self):
        job = make_job()
        seeker_a = make_job_seeker(email="ja@sel.com")
        seeker_b = make_job_seeker(email="jb@sel.com")
        make_application(applicant=seeker_a, job=job)
        make_application(applicant=seeker_b, job=job)

        results = list(get_applications_for_job(job=job))
        self.assertEqual(len(results), 2)

    def test_does_not_return_applications_for_other_jobs(self):
        job_a = make_job()
        job_b = make_job()
        seeker = make_job_seeker(email="cross@sel.com")
        make_application(applicant=seeker, job=job_a)

        results = list(get_applications_for_job(job=job_b))
        self.assertEqual(len(results), 0)

    def test_filters_by_status(self):
        job = make_job()
        seeker_a = make_job_seeker(email="jfa@sel.com")
        seeker_b = make_job_seeker(email="jfb@sel.com")
        make_application(applicant=seeker_a, job=job, status=Application.Status.APPLIED)
        make_application(applicant=seeker_b, job=job, status=Application.Status.INTERVIEW)

        results = list(
            get_applications_for_job(job=job, status=Application.Status.INTERVIEW)
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, Application.Status.INTERVIEW)


class TestGetApplicationById(TestCase):

    def test_returns_application_when_found(self):
        app = make_application()
        result = get_application_by_id(application_id=str(app.id))
        self.assertEqual(result, app)

    def test_raises_does_not_exist_for_unknown_id(self):
        import uuid
        with self.assertRaises(Application.DoesNotExist):
            get_application_by_id(application_id=str(uuid.uuid4()))

    def test_select_related_job_and_applicant(self):
        app = make_application()
        result = get_application_by_id(application_id=str(app.id))
        with self.assertNumQueries(0):
            _ = result.job.title
            _ = result.applicant.email


class TestGetApplicationByIdForApplicant(TestCase):

    def test_returns_application_for_correct_owner(self):
        seeker = make_job_seeker(email="own@sel.com")
        app = make_application(applicant=seeker)
        result = get_application_by_id_for_applicant(
            application_id=str(app.id),
            applicant=seeker,
        )
        self.assertEqual(result, app)

    def test_raises_for_wrong_applicant(self):
        seeker_a = make_job_seeker(email="sa@sel.com")
        seeker_b = make_job_seeker(email="sb@sel.com")
        app = make_application(applicant=seeker_a)
        with self.assertRaises(Application.DoesNotExist):
            get_application_by_id_for_applicant(
                application_id=str(app.id),
                applicant=seeker_b,
            )

    def test_raises_for_unknown_id(self):
        import uuid
        seeker = make_job_seeker(email="unk@sel.com")
        with self.assertRaises(Application.DoesNotExist):
            get_application_by_id_for_applicant(
                application_id=str(uuid.uuid4()),
                applicant=seeker,
            )


class TestGetApplicationForRecruiter(TestCase):

    def test_returns_application_for_job_owner(self):
        recruiter = make_recruiter(email="rec@sel.com")
        job = make_job(owner=recruiter)
        app = make_application(job=job)
        result = get_application_for_recruiter(
            application_id=str(app.id),
            recruiter=recruiter,
        )
        self.assertEqual(result, app)

    def test_raises_for_non_owner_recruiter(self):
        recruiter_a = make_recruiter(email="ra@sel.com")
        recruiter_b = make_recruiter(email="rb@sel.com")
        job = make_job(owner=recruiter_a)
        app = make_application(job=job)
        with self.assertRaises(Application.DoesNotExist):
            get_application_for_recruiter(
                application_id=str(app.id),
                recruiter=recruiter_b,
            )
