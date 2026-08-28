import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def is_configured() -> bool:
    return bool(settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD)


def send_email(*, to: str, subject: str, text: str) -> dict:
    """Send via Gmail SMTP when configured; otherwise log-only fallback.

    Returns {"provider": "gmail"|"logged", "message_id": ...}.
    Raises RuntimeError on provider failure (caller marks FAILED).
    """
    if not is_configured():
        logger.info(
            "[email:fallback] to=%s subject=%r body=%r",
            to,
            subject,
            text[:200],
        )

        return {"provider": "logged", "message_id": None}

    sender = settings.EMAIL_FROM or settings.GMAIL_USER

    message = MIMEText(text)
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.sendmail(settings.GMAIL_USER, [to], message.as_string())
    except Exception as exc:
        logger.error("Gmail SMTP error: %s", exc)
        raise RuntimeError("Gmail delivery failed.") from exc

    return {"provider": "gmail", "message_id": None}