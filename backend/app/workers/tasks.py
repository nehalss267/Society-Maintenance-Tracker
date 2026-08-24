import uuid

from app.workers.celery_app import celery_app


@celery_app.task(
    name="smt.deliver_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def deliver_notification(self, notification_id: str):
    from app.services.notification_service import _deliver_now

    _deliver_now(uuid.UUID(notification_id))
