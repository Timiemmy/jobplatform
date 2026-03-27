"""
tests/applications/test_email_templates.py

Unit tests for infrastructure/email/templates.py.

Tests verify message content and structure without
sending any real emails.
"""

from django.test import SimpleTestCase

from infrastructure.email.templates import (
    build_application_confirmation_email,
    build_status_update_email,
    build_new_applicant_notification_email,
    EmailMessage,
)


class TestBuildApplicationConfirmationEmail(SimpleTestCase):

    def _build(self, **overrides):
        defaults = dict(
            applicant_name="Alice Smith",
            job_title="Senior Django Engineer",
            company_name="TechCorp",
        )
        defaults.update(overrides)
        return build_application_confirmation_email(**defaults)

    def test_returns_email_message_instance(self):
        self.assertIsInstance(self._build(), EmailMessage)

    def test_subject_contains_job_title(self):
        msg = self._build()
        self.assertIn("Senior Django Engineer", msg.subject)

    def test_plain_text_body_contains_applicant_name(self):
        msg = self._build()
        self.assertIn("Alice Smith", msg.message)

    def test_plain_text_body_contains_job_title(self):
        msg = self._build()
        self.assertIn("Senior Django Engineer", msg.message)

    def test_plain_text_body_contains_company_name(self):
        msg = self._build()
        self.assertIn("TechCorp", msg.message)

    def test_html_message_is_not_empty(self):
        msg = self._build()
        self.assertTrue(len(msg.html_message) > 0)

    def test_html_contains_applicant_name(self):
        msg = self._build()
        self.assertIn("Alice Smith", msg.html_message)

    def test_works_without_company_name(self):
        """company_name is optional — empty string must not break template."""
        try:
            msg = build_application_confirmation_email(
                applicant_name="Bob",
                job_title="Developer",
                company_name="",
            )
        except Exception as e:
            self.fail(f"Raised unexpectedly: {e}")
        self.assertIsInstance(msg, EmailMessage)


class TestBuildStatusUpdateEmail(SimpleTestCase):

    def _build(self, status="reviewed", **overrides):
        defaults = dict(
            applicant_name="Alice Smith",
            job_title="Senior Django Engineer",
            company_name="TechCorp",
            new_status=status,
        )
        defaults.update(overrides)
        return build_status_update_email(**defaults)

    def test_returns_email_message_instance(self):
        self.assertIsInstance(self._build(), EmailMessage)

    def test_subject_contains_job_title(self):
        msg = self._build()
        self.assertIn("Senior Django Engineer", msg.subject)

    def test_subject_contains_status_label(self):
        msg = self._build(status="interview")
        self.assertIn("Interview", msg.subject)

    def test_body_contains_applicant_name(self):
        msg = self._build()
        self.assertIn("Alice Smith", msg.message)

    def test_all_valid_statuses_produce_output(self):
        for s in ["reviewed", "interview", "hired", "rejected"]:
            try:
                msg = self._build(status=s)
                self.assertIsInstance(msg, EmailMessage)
            except Exception as e:
                self.fail(f"Raised for status='{s}': {e}")

    def test_hired_message_contains_congratulations(self):
        msg = self._build(status="hired")
        combined = msg.message + msg.html_message
        self.assertIn("ongratulation", combined)

    def test_rejected_message_does_not_contain_congratulations(self):
        msg = self._build(status="rejected")
        self.assertNotIn("Congratulations", msg.message)

    def test_unknown_status_does_not_raise(self):
        """Graceful fallback for unexpected status values."""
        try:
            msg = build_status_update_email(
                applicant_name="Bob",
                job_title="Dev",
                company_name="",
                new_status="unknown_status",
            )
        except Exception as e:
            self.fail(f"Raised for unknown status: {e}")


class TestBuildNewApplicantNotificationEmail(SimpleTestCase):

    def _build(self, **overrides):
        defaults = dict(
            recruiter_name="Bob Jones",
            applicant_name="Alice Smith",
            job_title="Senior Django Engineer",
        )
        defaults.update(overrides)
        return build_new_applicant_notification_email(**defaults)

    def test_returns_email_message_instance(self):
        self.assertIsInstance(self._build(), EmailMessage)

    def test_subject_contains_job_title(self):
        msg = self._build()
        self.assertIn("Senior Django Engineer", msg.subject)

    def test_subject_contains_applicant_name(self):
        msg = self._build()
        self.assertIn("Alice Smith", msg.subject)

    def test_body_addresses_recruiter(self):
        msg = self._build()
        self.assertIn("Bob Jones", msg.message)

    def test_body_mentions_applicant(self):
        msg = self._build()
        self.assertIn("Alice Smith", msg.message)

    def test_html_message_present(self):
        msg = self._build()
        self.assertTrue(len(msg.html_message) > 0)
