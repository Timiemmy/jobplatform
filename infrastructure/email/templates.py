"""
infrastructure/email/templates.py

All outbound email message builders.

Each function returns a dict with `subject`, `message` (plain text),
and `html_message` (HTML version). The Celery tasks call these and
pass the result to send_email().

Keeping content here (not in tasks or services) means:
  - Content is testable without sending real emails.
  - A future template engine (Jinja2, MJML) can be dropped in here only.
  - Tasks stay thin — build message, send, done.
"""

from dataclasses import dataclass


@dataclass
class EmailMessage:
    subject: str
    message: str          # plain text — always required
    html_message: str     # HTML — shown when client supports it


# ---------------------------------------------------------------------------
# Application confirmation
# ---------------------------------------------------------------------------

def build_application_confirmation_email(
    *,
    applicant_name: str,
    job_title: str,
    company_name: str,
) -> EmailMessage:
    """
    Sent to the job seeker immediately after a successful application.
    """
    subject = f"Application received — {job_title}"

    message = (
        f"Hi {applicant_name},\n\n"
        f"Thank you for applying for the {job_title} position"
        f"{f' at {company_name}' if company_name else ''}.\n\n"
        "We've received your application and the recruiter will be in touch.\n\n"
        "Good luck!\n\n"
        "The Job Board Team"
    )

    html_message = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">Application Received</h2>
        <p>Hi <strong>{applicant_name}</strong>,</p>
        <p>
          Thank you for applying for the <strong>{job_title}</strong> position
          {f'at <strong>{company_name}</strong>' if company_name else ''}.
        </p>
        <p>We've received your application and the recruiter will be in touch.</p>
        <p>Good luck!</p>
        <hr style="border: 1px solid #eee; margin: 24px 0;" />
        <p style="color: #888; font-size: 12px;">The Job Board Team</p>
      </body>
    </html>
    """

    return EmailMessage(subject=subject, message=message, html_message=html_message)


# ---------------------------------------------------------------------------
# Application status update
# ---------------------------------------------------------------------------

_STATUS_LABELS = {
    "applied":   "Applied",
    "reviewed":  "Under Review",
    "interview": "Interview Stage",
    "hired":     "Offer Extended",
    "rejected":  "Not Selected",
}

_STATUS_MESSAGES = {
    "reviewed":  "Your application is being reviewed by the recruiter.",
    "interview": "Congratulations! The recruiter would like to invite you to an interview.",
    "hired":     "Congratulations! The recruiter has extended an offer for this position.",
    "rejected":  "After careful review, the recruiter has decided not to move forward with your application at this time.",
}


def build_status_update_email(
    *,
    applicant_name: str,
    job_title: str,
    company_name: str,
    new_status: str,
) -> EmailMessage:
    """
    Sent to the job seeker when a recruiter updates their application status.
    """
    status_label   = _STATUS_LABELS.get(new_status, new_status.title())
    status_message = _STATUS_MESSAGES.get(new_status, "Your application status has been updated.")

    subject = f"Application update — {job_title}: {status_label}"

    message = (
        f"Hi {applicant_name},\n\n"
        f"There's an update on your application for {job_title}"
        f"{f' at {company_name}' if company_name else ''}.\n\n"
        f"Status: {status_label}\n\n"
        f"{status_message}\n\n"
        "The Job Board Team"
    )

    html_message = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">Application Update</h2>
        <p>Hi <strong>{applicant_name}</strong>,</p>
        <p>
          There's an update on your application for
          <strong>{job_title}</strong>
          {f'at <strong>{company_name}</strong>' if company_name else ''}.
        </p>
        <div style="background: #f8f9fa; border-left: 4px solid #3498db;
                    padding: 16px; margin: 24px 0; border-radius: 4px;">
          <strong>Status:</strong> {status_label}
        </div>
        <p>{status_message}</p>
        <hr style="border: 1px solid #eee; margin: 24px 0;" />
        <p style="color: #888; font-size: 12px;">The Job Board Team</p>
      </body>
    </html>
    """

    return EmailMessage(subject=subject, message=message, html_message=html_message)


# ---------------------------------------------------------------------------
# New applicant notification (sent to recruiter)
# ---------------------------------------------------------------------------

def build_new_applicant_notification_email(
    *,
    recruiter_name: str,
    applicant_name: str,
    job_title: str,
) -> EmailMessage:
    """
    Sent to the recruiter when someone applies to their job posting.
    """
    subject = f"New applicant for {job_title} — {applicant_name}"

    message = (
        f"Hi {recruiter_name},\n\n"
        f"{applicant_name} has applied for your {job_title} posting.\n\n"
        "Log in to your dashboard to review their application.\n\n"
        "The Job Board Team"
    )

    html_message = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">New Applicant</h2>
        <p>Hi <strong>{recruiter_name}</strong>,</p>
        <p>
          <strong>{applicant_name}</strong> has applied for your
          <strong>{job_title}</strong> posting.
        </p>
        <p>Log in to your dashboard to review their application.</p>
        <hr style="border: 1px solid #eee; margin: 24px 0;" />
        <p style="color: #888; font-size: 12px;">The Job Board Team</p>
      </body>
    </html>
    """

    return EmailMessage(subject=subject, message=message, html_message=html_message)
