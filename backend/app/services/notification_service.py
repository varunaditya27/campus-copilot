import logging
import smtplib
from email.message import EmailMessage

from app.core import config

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 10


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns whether it was sent; never raises, because
    a notification must not fail the request that caused it."""
    if not config.SMTP_HOST:
        logger.info("Email not sent (SMTP_HOST is not set): to=%s subject=%s", to, subject)
        return False
    message = EmailMessage()
    message["From"] = config.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
            if config.SMTP_STARTTLS:
                server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(message)
    except Exception:
        logger.exception("Could not send email to %s", to)
        return False
    return True


STATUS_WORDS = {"open": "open", "in_progress": "being looked into", "resolved": "resolved"}


def ticket_status_email(name: str, ref: str, status: str, note: str | None) -> tuple[str, str]:
    """The subject and body telling a student their grievance changed status."""
    subject = f"Your grievance {ref} is now {STATUS_WORDS[status]}"
    lines = [f"Hello {name},", "", f"Your grievance {ref} is now {STATUS_WORDS[status]}."]
    if note:
        lines += ["", "Note from the committee:", note]
    lines += ["", "You can ask the campus assistant for the latest status at any time.", "", "General Grievance Redressal Committee"]
    return subject, "\n".join(lines)
