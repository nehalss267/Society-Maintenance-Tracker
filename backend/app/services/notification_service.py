import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import settings
from app.integrations import gmail_client
from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
)

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    recipient_email: str,
    event: str,
    subject: str,
    body: str,
    payload: dict | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        recipient_email=recipient_email,
        channel=NotificationChannel.EMAIL,
        event=event,
        subject=subject,
        body=body,
        payload=payload,
        status=NotificationStatus.PENDING,
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification


def notify(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    recipient_email: str | None,
    event: str,
    subject: str,
    body: str,
    payload: dict | None = None,
) -> Notification | None:
    """Fire-and-forget entry point for business hooks.

    Never raises - notification failures must not break business flows.
    Dispatches to Celery (broker mode) or delivers inline.
    """
    if not recipient_email:
        logger.warning("notify() skipped for %s: no recipient email", event)
        return None

    try:
        notification = create_notification(
            db,
            user_id=user_id,
            recipient_email=recipient_email,
            event=event,
            subject=subject,
            body=body,
            payload=payload,
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to create notification row for %s", event)
        return None

    if settings.JOB_EXECUTION_MODE == "celery":
        try:
            from app.workers.tasks import deliver_notification

            deliver_notification.delay(str(notification.id))
        except Exception:
            logger.exception(
                "Celery dispatch failed for %s; delivering inline",
                notification.id,
            )
            _safe_deliver(notification.id)
    else:
        _safe_deliver(notification.id)

    return notification


def _safe_deliver(notification_id: uuid.UUID) -> None:
    """Inline dispatch that can never propagate into business flows."""
    try:
        _deliver_now(notification_id)
    except Exception:
        logger.exception("Inline delivery crashed for %s", notification_id)


def _deliver_now(notification_id: uuid.UUID) -> None:
    """Deliver using an isolated session (safe for Celery + inline)."""
    db = SessionLocal()

    try:
        notification = db.get(Notification, notification_id)

        if not notification or notification.status != NotificationStatus.PENDING:
            return

        result = gmail_client.send_email(
            to=notification.recipient_email,
            subject=notification.subject,
            text=notification.body,
        )

        notification.status = NotificationStatus.SENT
        notification.provider_message_id = result["message_id"]
        notification.sent_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        db.rollback()

        notification = db.get(Notification, notification_id)

        if notification:
            notification.status = NotificationStatus.FAILED
            notification.error = str(exc)[:500]
            db.commit()

        logger.exception("Notification %s delivery failed", notification_id)
    finally:
        db.close()


def pending_count(db: Session) -> int:
    return len(
        db.scalars(
            select(Notification.id).where(
                Notification.status == NotificationStatus.PENDING
            )
        ).all()
    )
