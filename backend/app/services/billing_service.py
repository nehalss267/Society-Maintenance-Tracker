import logging
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus, UNPAID_STATUSES
from app.models.invoice_item import InvoiceItem, InvoiceItemKind
from app.models.maintenance_plan import BillingCycle, MaintenancePlan
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


def period_to_dates(period: str) -> tuple[date, date]:
    """'2026-08' -> (first_day, last_day). Raises ValueError when malformed."""
    year_str, month_str = period.split("-")
    first = date(int(year_str), int(month_str), 1)
    last = date(first.year, first.month, monthrange(first.year, first.month)[1])
    return first, last


def current_period() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def _due_date(period: str, due_day: int) -> date:
    _, last = period_to_dates(period)
    return date(last.year, last.month, min(due_day, last.day))


def generate_invoice_number(db: Session) -> str:
    while True:
        candidate = f"INV-{uuid.uuid4().hex[:10].upper()}"

        if not db.scalar(
            select(Invoice.id).where(Invoice.invoice_number == candidate)
        ):
            return candidate


def create_invoice(
    db: Session,
    *,
    resident_id: uuid.UUID,
    plan: MaintenancePlan | None,
    billing_period: str,
    description: str,
    amount: Decimal,
    actor_id: uuid.UUID | None = None,
) -> Invoice:
    """Create one invoice + its CHARGE item. Caller commits."""

    period_start, _ = period_to_dates(billing_period)

    invoice = Invoice(
        invoice_number=generate_invoice_number(db),
        resident_id=resident_id,
        plan_id=plan.id if plan else None,
        billing_period=billing_period,
        period_start=period_start,
        subtotal=amount,
        late_fee=Decimal("0.00"),
        total_amount=amount,
        amount_paid=Decimal("0.00"),
        status=InvoiceStatus.PENDING,
        due_date=(
            _due_date(billing_period, plan.due_day_of_month)
            if plan
            else _due_date(billing_period, 10)
        ),
    )

    db.add(invoice)
    db.flush()

    item = InvoiceItem(
        invoice_id=invoice.id,
        kind=InvoiceItemKind.CHARGE,
        description=description,
        unit_price=amount,
        amount=amount,
    )

    db.add(item)

    return invoice


def generate_invoices_for_period(
    db: Session,
    period: str,
    *,
    actor_id: uuid.UUID | None = None,
) -> list[Invoice]:
    """Idempotent monthly billing run.

    For every active plan x every RESIDENT: skip when an invoice already
    exists for (resident, plan, period). The unique constraint backs this up.
    """
    residents = db.scalars(
        select(User).where(User.role == UserRole.RESIDENT)
    ).all()

    plans = db.scalars(
        select(MaintenancePlan).where(MaintenancePlan.is_active.is_(True))
    ).all()

    created: list[Invoice] = []

    for plan in plans:
        if plan.cycle != BillingCycle.MONTHLY:
            logger.warning(
                "Plan %s has unsupported cycle %s; skipped",
                plan.name,
                plan.cycle.value,
            )
            continue

        for resident in residents:
            exists = db.scalar(
                select(Invoice.id).where(
                    Invoice.resident_id == resident.id,
                    Invoice.plan_id == plan.id,
                    Invoice.billing_period == period,
                    Invoice.status != InvoiceStatus.CANCELLED,
                )
            )

            if exists:
                continue

            invoice = create_invoice(
                db,
                resident_id=resident.id,
                plan=plan,
                billing_period=period,
                description=f"{plan.name} - maintenance {period}",
                amount=plan.amount,
                actor_id=actor_id,
            )

            created.append(invoice)

    db.commit()

    from app.core.cache import invalidate_prefix

    if created:
        invalidate_prefix("dash:accountant")

        from app.services import notification_service

    for invoice in created:
        invalidate_prefix(f"dash:resident:{invoice.resident_id}")

        resident = db.get(User, invoice.resident_id)

        if not resident:
            continue

        from app.services import notification_service

        notification_service.notify(
            db,
            user_id=resident.id,
            recipient_email=resident.email,
            event="INVOICE_GENERATED",
            subject=f"Maintenance invoice {invoice.invoice_number} for {period}",
            body=(
                f"Your maintenance invoice {invoice.invoice_number} for "
                f"{period} is ready.\nAmount due: INR {invoice.total_amount}\n"
                f"Due date: {invoice.due_date.isoformat()}"
            ),
            payload={
                "invoice_id": str(invoice.id),
                "amount": float(invoice.total_amount),
            },
        )

    return created


def apply_late_fees(
    db: Session,
    *,
    reference_date: date | None = None,
    actor_id: uuid.UUID | None = None,
) -> list[Invoice]:
    """Apply each plan's late fee once to unpaid invoices past grace period.

    Duplicate prevention: an invoice only ever gets one LATE_FEE item.
    """
    today = reference_date or date.today()

    unpaid_invoices = db.scalars(
        select(Invoice).where(
            Invoice.status.in_(UNPAID_STATUSES),
            Invoice.due_date < today,
        )
    ).all()

    penalized: list[Invoice] = []

    for invoice in unpaid_invoices:
        plan: MaintenancePlan | None = (
            db.get(MaintenancePlan, invoice.plan_id)
            if invoice.plan_id
            else None
        )

        if not plan or plan.late_fee_amount <= 0:
            continue

        # Grace window: penalty applies from due_date + grace_days onwards
        if today < invoice.due_date + timedelta(
            days=plan.late_fee_grace_days
        ):
            continue

        existing_fee = db.scalar(
            select(InvoiceItem.id).where(
                InvoiceItem.invoice_id == invoice.id,
                InvoiceItem.kind == InvoiceItemKind.LATE_FEE,
            )
        )

        if existing_fee:
            continue

        fee_item = InvoiceItem(
            invoice_id=invoice.id,
            kind=InvoiceItemKind.LATE_FEE,
            description=f"Late payment penalty (due {invoice.due_date.isoformat()})",
            unit_price=plan.late_fee_amount,
            amount=plan.late_fee_amount,
        )

        db.add(fee_item)

        invoice.late_fee = (invoice.late_fee or Decimal("0.00")) + plan.late_fee_amount
        invoice.total_amount = (invoice.subtotal or Decimal("0.00")) + invoice.late_fee

        if invoice.status == InvoiceStatus.PENDING:
            invoice.status = InvoiceStatus.OVERDUE

        penalized.append(invoice)

    if penalized:
        db.commit()

    return penalized
