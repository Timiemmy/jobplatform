"""
infrastructure/email/sender.py

Email sending abstraction.

All outbound emails go through send_email().
Never call Django's send_mail() directly from services or views.

This module is called exclusively from Celery tasks — never
from the synchronous request/response cycle.
"""

import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email(
    *,
    subject: str,
    message: str,
    recipient: str,
    html_message: str = None,
) -> bool:
    """
    Send a single email.

    Returns True on success, False on failure (never raises —
    email failures must not crash the application).

    Args:
        subject:       Email subject line.
        message:       Plain-text body (always required as fallback).
        recipient:     Single recipient email address.
        html_message:  Optional HTML body. Falls back to plain text if None.
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("Email sent: subject='%s' recipient=%s", subject, recipient)
        return True
    except Exception as exc:
        logger.exception(
            "Failed to send email: subject='%s' recipient=%s error=%s",
            subject, recipient, exc,
        )
        return False
