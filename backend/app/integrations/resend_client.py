import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def is_configured() -> bool:
    return bool(settings.RESEND_API_KEY)


def send_email(*, to: str, subject: str, text: str) -> dict:
    """Send via Resend when configured; otherwise log-only fallback.

    Returns {"provider": "resend"|"logged", "message_id": ...}.
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

    response = httpx.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": settings.EMAIL_FROM,
            "to": [to],
            "subject": subject,
            "text": text,
        },
        timeout=15.0,
    )

    if response.status_code >= 400:
        logger.error("Resend error %s: %s", response.status_code, response.text[:300])
        raise RuntimeError(f"Resend delivery failed ({response.status_code}).")

    data = response.json()

    return {
        "provider": "resend",
        "message_id": data.get("id"),
    }
