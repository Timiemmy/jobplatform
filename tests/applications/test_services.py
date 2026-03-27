"""
tests/applications/test_services.py

Unit tests for apps/applications/services.py.

Celery tasks are patched with unittest.mock so no real
emails fire and no Redis connection is required.
File uploads are patched via a fake file object so no
real filesystem or S3 interaction happens.
"""

import io
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.applications.models import Application
from apps.applications.services import apply_to_job, update_application_status
from apps.jobs.models import Job
from core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ApplicationError,
)
from tests.factories import (
    make_job_seeker,
    make_recruiter,
    make_admin,
    make_job,
    make_application,
)


# ---------------------------------------------------------------------------
# Fake resume file for tests — bypasses real storage
# ---------------------------------------------------------------------------

def _fake_resume(name="resume.pdf", size=1024 * 100):
    """Return a minimal file-like object that satisfies all validators."""
    f = MagicMock()
    f.name = name
    f.size = size
    f.read.return_value = b"%PDF-1.4 fake content" + b"\x00" * size
    f.seek.return_value = None
    return f


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

UPLOAD_PATCH    = "apps.applications.services.upload_resume"
VALIDATE_PATCH  = "apps.applications.services.validate_resume_file"
EMAIL_PATCH     = "apps.applications.services._fire_application_emails"
STATUS_EMAIL_PATCH = "apps.applications.services._fire_status_update_email"


# ---------------------------------------------------------------------------
# apply_to_job tests
# ---------------------------------------------------------------------------

class TestApplyToJob(TestCase):

    def setUp(self):
        self.seeker    = make_job_seeker(email="seeker@apply.com")
        self.job       = make_job()
        self.fake_file = _fake_resume()

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/2025/01/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_successful_application_returns_application(
        self, mock_validate, mock_upload, mock_email
    ):
        app = apply_to_job(
            applicant=self.seeker,
            job_id=str(self.job.id),
            resume_file=self.fake_file,
        )
        self.assertIsInstance(app, Application)

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/2025/01/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_application_status_is_applied(
        self, mock_validate, mock_upload, mock_email
    ):
        app = apply_to_job(
            applicant=self.seeker,
            job_id=str(self.job.id),
            resume_file=self.fake_file,
        )
        self.assertEqual(app.status, Application.Status.APPLIED)

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_resume_path_stored_from_upload(
        self, mock_validate, mock_upload, mock_email
    ):
        app = apply_to_job(
            applicant=self.seeker,
            job_id=str(self.job.id),
            resume_file=self.fake_file,
        )
        self.assertEqual(app.resume_path, "resumes/test/resume.pdf")

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_cover_letter_is_stored(
        self, mock_validate, mock_upload, mock_email
    ):
        app = apply_to_job(
            applicant=self.seeker,
            job_id=str(self.job.id),
            resume_file=self.fake_file,
            cover_letter="I am very interested.",
        )
        self.assertEqual(app.cover_letter, "I am very interested.")

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_application_persisted_to_database(
        self, mock_validate, mock_upload, mock_email
    ):
        app = apply_to_job(
            applicant=self.seeker,
            job_id=str(self.job.id),
            resume_file=self.fake_file,
        )
        self.assertTrue(Application.objects.filter(id=app.id).exists())

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_async_emails_are_fired(
        self, mock_validate, mock_upload, mock_email
    ):
        apply_to_job(
            applicant=self.seeker,
            job_id=str(self.job.id),
            resume_file=self.fake_file,
        )
        mock_email.assert_called_once()

    def test_recruiter_cannot_apply(self):
        recruiter = make_recruiter(email="r@apply.com")
        with self.assertRaises(ForbiddenError):
            apply_to_job(
                applicant=recruiter,
                job_id=str(self.job.id),
                resume_file=self.fake_file,
            )

    def test_admin_cannot_apply(self):
        admin = make_admin(email="a@apply.com")
        with self.assertRaises(ForbiddenError):
            apply_to_job(
                applicant=admin,
                job_id=str(self.job.id),
                resume_file=self.fake_file,
            )

    def test_nonexistent_job_raises_not_found(self):
        import uuid
        with self.assertRaises(NotFoundError):
            apply_to_job(
                applicant=self.seeker,
                job_id=str(uuid.uuid4()),
                resume_file=self.fake_file,
            )

    def test_closed_job_raises_not_found(self):
        closed_job = make_job(status=Job.Status.CLOSED)
        with self.assertRaises(NotFoundError):
            apply_to_job(
                applicant=self.seeker,
                job_id=str(closed_job.id),
                resume_file=self.fake_file,
            )

    def test_draft_job_raises_not_found(self):
        draft_job = make_job(status=Job.Status.DRAFT)
        with self.assertRaises(NotFoundError):
            apply_to_job(
                applicant=self.seeker,
                job_id=str(draft_job.id),
                resume_file=self.fake_file,
            )

    def test_soft_deleted_job_raises_not_found(self):
        deleted_job = make_job(is_active=False)
        with self.assertRaises(NotFoundError):
            apply_to_job(
                applicant=self.seeker,
                job_id=str(deleted_job.id),
                resume_file=self.fake_file,
            )

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_duplicate_application_raises_conflict(
        self, mock_validate, mock_upload, mock_email
    ):
        apply_to_job(
            applicant=self.seeker,
            job_id=str(self.job.id),
            resume_file=self.fake_file,
        )
        with self.assertRaises(ConflictError):
            apply_to_job(
                applicant=self.seeker,
                job_id=str(self.job.id),
                resume_file=self.fake_file,
            )

    def test_invalid_resume_extension_raises_validation_error(self):
        bad_file = _fake_resume(name="cv.exe")
        with self.assertRaises(ValidationError):
            apply_to_job(
                applicant=self.seeker,
                job_id=str(self.job.id),
                resume_file=bad_file,
            )

    def test_oversized_resume_raises_validation_error(self):
        big_file = _fake_resume(name="resume.pdf", size=10 * 1024 * 1024)  # 10 MB
        with self.assertRaises(ValidationError):
            apply_to_job(
                applicant=self.seeker,
                job_id=str(self.job.id),
                resume_file=big_file,
            )

    @patch(EMAIL_PATCH)
    @patch(UPLOAD_PATCH, return_value="resumes/test/resume.pdf")
    @patch(VALIDATE_PATCH)
    def test_file_upload_called_with_correct_user_id(
        self, mock_validate, mock_upload, mock_email
    ):
        apply_to_job(
            applicant=self.seeker,
            job_id=str(self.job.id),
            resume_file=self.fake_file,
        )
        mock_upload.assert_called_once_with(
            file=self.fake_file,
            user_id=str(self.seeker.id),
        )


# ---------------------------------------------------------------------------
# update_application_status tests
# ---------------------------------------------------------------------------

class TestUpdateApplicationStatus(TestCase):

    def setUp(self):
        self.recruiter = make_recruiter(email="rec@status.com")
        self.seeker    = make_job_seeker(email="app@status.com")
        self.job       = make_job(owner=self.recruiter)
        self.application = make_application(applicant=self.seeker, job=self.job)

    @patch(STATUS_EMAIL_PATCH)
    def test_recruiter_can_advance_to_reviewed(self, mock_email):
        app = update_application_status(
            application=self.application,
            recruiter=self.recruiter,
            new_status=Application.Status.REVIEWED,
        )
        self.assertEqual(app.status, Application.Status.REVIEWED)

    @patch(STATUS_EMAIL_PATCH)
    def test_recruiter_can_reject_at_applied_stage(self, mock_email):
        app = update_application_status(
            application=self.application,
            recruiter=self.recruiter,
            new_status=Application.Status.REJECTED,
        )
        self.assertEqual(app.status, Application.Status.REJECTED)

    @patch(STATUS_EMAIL_PATCH)
    def test_full_positive_lifecycle(self, mock_email):
        """applied → reviewed → interview → hired"""
        for next_status in [
            Application.Status.REVIEWED,
            Application.Status.INTERVIEW,
            Application.Status.HIRED,
        ]:
            self.application = update_application_status(
                application=self.application,
                recruiter=self.recruiter,
                new_status=next_status,
            )
            self.assertEqual(self.application.status, next_status)

    @patch(STATUS_EMAIL_PATCH)
    def test_status_change_is_persisted(self, mock_email):
        update_application_status(
            application=self.application,
            recruiter=self.recruiter,
            new_status=Application.Status.REVIEWED,
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.REVIEWED)

    @patch(STATUS_EMAIL_PATCH)
    def test_status_update_email_is_fired(self, mock_email):
        update_application_status(
            application=self.application,
            recruiter=self.recruiter,
            new_status=Application.Status.REVIEWED,
        )
        mock_email.assert_called_once()

    def test_illegal_transition_applied_to_interview_raises(self):
        """applied → interview is not in VALID_TRANSITIONS."""
        with self.assertRaises(ApplicationError) as ctx:
            update_application_status(
                application=self.application,
                recruiter=self.recruiter,
                new_status=Application.Status.INTERVIEW,
            )
        self.assertIn("Cannot transition", str(ctx.exception.detail))

    def test_illegal_transition_applied_to_hired_raises(self):
        with self.assertRaises(ApplicationError):
            update_application_status(
                application=self.application,
                recruiter=self.recruiter,
                new_status=Application.Status.HIRED,
            )

    @patch(STATUS_EMAIL_PATCH)
    def test_terminal_status_hired_cannot_be_changed(self, mock_email):
        hired_app = make_application(
            applicant=make_job_seeker(email="hired@status.com"),
            job=self.job,
            status=Application.Status.HIRED,
        )
        with self.assertRaises(ApplicationError):
            update_application_status(
                application=hired_app,
                recruiter=self.recruiter,
                new_status=Application.Status.REVIEWED,
            )

    @patch(STATUS_EMAIL_PATCH)
    def test_terminal_status_rejected_cannot_be_changed(self, mock_email):
        rejected_app = make_application(
            applicant=make_job_seeker(email="rejected@status.com"),
            job=self.job,
            status=Application.Status.REJECTED,
        )
        with self.assertRaises(ApplicationError):
            update_application_status(
                application=rejected_app,
                recruiter=self.recruiter,
                new_status=Application.Status.REVIEWED,
            )

    def test_non_owner_recruiter_cannot_update_status(self):
        other_recruiter = make_recruiter(email="other@status.com")
        with self.assertRaises(ForbiddenError):
            update_application_status(
                application=self.application,
                recruiter=other_recruiter,
                new_status=Application.Status.REVIEWED,
            )

    def test_job_seeker_cannot_update_status(self):
        with self.assertRaises(ForbiddenError):
            update_application_status(
                application=self.application,
                recruiter=self.seeker,  # passing a seeker as recruiter
                new_status=Application.Status.REVIEWED,
            )

    @patch(STATUS_EMAIL_PATCH)
    def test_admin_can_update_any_application_status(self, mock_email):
        admin = make_admin(email="admin@status.com")
        # Admin bypasses owner check
        app = update_application_status(
            application=self.application,
            recruiter=admin,
            new_status=Application.Status.REVIEWED,
        )
        self.assertEqual(app.status, Application.Status.REVIEWED)
