import hmac
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User, UserRole
from app.services import billing_service, expense_service, notification_service


router = APIRouter(
    prefix="/api/internal/jobs",
    tags=["Internal · Jobs"],
)


def require_cron_secret(
    x_cron_secret: str | None = Header(default=None),
) -> None:
    """Guard for scheduler-triggered endpoints (cron-job.org in prod)."""
    expected = settings.CRON_SECRET

    if not expected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CRON_SECRET is not configured on the server.",
        )

    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid cron secret.",
        )


@router.post("/billing-run/{period}")
def job_billing_run(
    period: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_cron_secret),
):
    created = billing_service.generate_invoices_for_period(db, period=period)

    _email_new_invoices(db, period)

    return {"job": "billing-run", "period": period, "invoices_created": len(created)}


@router.post("/late-fees")
def job_late_fees(
    db: Session = Depends(get_db),
    _: None = Depends(require_cron_secret),
):
    result = billing_service.apply_late_fees(db)
    penalized = len(result)

    if penalized:
        _email_overdue(db)

    return {"job": "late-fees", "penalized": penalized}


@router.post("/recurring-expenses/{period}")
def job_recurring_expenses(
    period: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_cron_secret),
):
    created = expense_service.generate_recurring_expenses_for_period(
        db, period=period
    )

    return {
        "job": "recurring-expenses",
        "period": period,
        "expenses_created": created,
    }


def _residents_with_email(db: Session) -> list[User]:
    return list(
        db.scalars(select(User).where(User.role == UserRole.RESIDENT)).all()
    )


def _email_new_invoices(db: Session, period: str) -> None:
    invoices = db.scalars(
        select(Invoice).where(Invoice.billing_period == period)
    ).all()

    users = {u.id: u for u in db.scalars(select(User)).all()}

    for invoice in invoices:
        user = users.get(invoice.resident_id)

        if not user:
            continue

        notification_service.notify(
            db,
            user_id=invoice.resident_id,
            recipient_email=user.email,
            event="INVOICE_GENERATED",
            subject=f"Maintenance invoice {invoice.invoice_number} for {period}",
            body=(
                f"Your maintenance invoice {invoice.invoice_number} for "
                f"{period} is ready.\nAmount due: INR {invoice.total_amount}\n"
                f"Due date: {invoice.due_date}"
            ),
            payload={
                "invoice_id": str(invoice.id),
                "amount": float(invoice.total_amount),
            },
        )


def _email_overdue(db: Session) -> None:
    overdue = db.scalars(
        select(Invoice).where(Invoice.status == InvoiceStatus.OVERDUE)
    ).all()

    users = {u.id: u for u in _residents_with_email(db)}

    for invoice in overdue:
        user = users.get(invoice.resident_id)

        if not user:
            continue

        notification_service.notify(
            db,
            user_id=user.id,
            recipient_email=user.email,
            event="LATE_PAYMENT_REMINDER",
            subject=f"Overdue invoice {invoice.invoice_number}",
            body=(
                f"Invoice {invoice.invoice_number} is OVERDUE.\n"
                f"Outstanding: INR {invoice.total_amount - invoice.amount_paid}\n"
                f"Please pay at your earliest convenience to avoid further late fees."
            ),
            payload={"invoice_id": str(invoice.id)},
        )
