import logging
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations import razorpay
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.reconciliation import (
    PaymentReconciliation,
    ReconciliationStatus,
)
from app.models.user import User
from app.services import fund_service
from app.services.audit_service import record_audit

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


def initiate_payment(
    db: Session,
    *,
    invoice: Invoice,
    resident_id: uuid.UUID,
) -> Payment:
    """Create a PENDING payment + provider order for an unpaid invoice."""

    if invoice.resident_id != resident_id:
        raise PaymentError("You can only pay your own invoices.")

    if invoice.status == InvoiceStatus.PAID:
        raise PaymentError("Invoice is already fully paid.")

    if invoice.status == InvoiceStatus.CANCELLED:
        raise PaymentError("Invoice is cancelled.")

    outstanding = invoice.total_amount - invoice.amount_paid

    if outstanding <= 0:
        raise PaymentError("Nothing outstanding on this invoice.")

    receipt = f"{invoice.invoice_number}"

    if razorpay.is_configured():
        order = razorpay.create_order(float(outstanding), receipt)
        provider = "razorpay"
    else:
        order = razorpay.simulated_order(float(outstanding), receipt)
        provider = "simulated"

    payment = Payment(
        invoice_id=invoice.id,
        resident_id=resident_id,
        provider=provider,
        provider_order_id=order["order_id"],
        amount=outstanding,
        status=PaymentStatus.PENDING,
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    return payment


def capture_success(
    db: Session,
    *,
    provider_order_id: str,
    provider_payment_id: str | None,
    signature_verified: bool = False,
    amount: Decimal | None = None,
) -> tuple[Payment, bool]:
    """Idempotently mark a payment successful and settle its invoice.

    - Unique provider_payment_id blocks double-processing at DB level.
    - Invoice row is locked (SELECT ... FOR UPDATE) while settling.
    Returns (payment, created) where created=False when this event was
    already processed.
    """
    payment = db.scalar(
        select(Payment).where(
            Payment.provider_order_id == provider_order_id
        )
    )

    if not payment:
        raise PaymentError(
            f"No payment found for order {provider_order_id}."
        )

    # Idempotency short-circuit
    if payment.status == PaymentStatus.SUCCESS:
        return payment, False

    if provider_payment_id:
        clash = db.scalar(
            select(Payment.id).where(
                Payment.provider_payment_id == provider_payment_id,
                Payment.id != payment.id,
            )
        )

        if clash:
            raise PaymentError(
                "Provider payment id already processed for another payment."
            )

        payment.provider_payment_id = provider_payment_id

    now = datetime.utcnow()

    payment.status = PaymentStatus.SUCCESS
    payment.signature_verified = signature_verified
    payment.paid_at = now

    if amount is not None:
        payment.amount = amount

    # Lock the invoice row to serialize concurrent settlements
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == payment.invoice_id)
        .with_for_update()
        .one()
    )

    invoice.amount_paid = (invoice.amount_paid or Decimal("0.00")) + (
        payment.amount or Decimal("0.00")
    )

    if invoice.amount_paid >= invoice.total_amount:
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIALLY_PAID

    recon_status = (
        ReconciliationStatus.MATCHED
        if razorpay.is_simulated_order(provider_order_id)
        or signature_verified
        else ReconciliationStatus.MANUAL_REVIEW
    )

    reconciliation = PaymentReconciliation(
        payment_id=payment.id,
        status=recon_status,
        reconciled_at=now,
        note=(
            "Simulated capture"
            if razorpay.is_simulated_order(provider_order_id)
            else "Auto-matched on verified capture"
        ),
    )

    db.add(reconciliation)

    # Auto-credit the maintenance fund in the same transaction
    fund_service.credit_maintenance_payment(
        db,
        payment_id=payment.id,
        amount=payment.amount or Decimal("0.00"),
        invoice_number=invoice.invoice_number,
    )

    record_audit(
        db,
        actor_id=None,  # provider-driven event; actor recorded in webhook logs
        action="PAYMENT_CAPTURED",
        entity_type="PAYMENT",
        entity_id=payment.id,
        old_value={"status": PaymentStatus.PENDING.value},
        new_value={
            "status": PaymentStatus.SUCCESS.value,
            "amount": float(payment.amount),
            "invoice": str(invoice.invoice_number),
            "invoice_status": invoice.status.value,
        },
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("capture_success commit failed")
        raise PaymentError(
            "Payment settlement failed; please retry."
        )

    # Payment receipt email (fire-and-forget, isolated session inside)
    from app.core.cache import invalidate_prefix
    from app.services import notification_service

    invalidate_prefix(f"dash:resident:{payment.resident_id}")
    invalidate_prefix("dash:accountant")

    payer = db.get(User, payment.resident_id)

    notification_service.notify(
        db,
        user_id=payment.resident_id,
        recipient_email=payer.email if payer else None,
        event="PAYMENT_RECEIPT",
        subject=f"Payment received for {invoice.invoice_number}",
        body=(
            f"We received your payment of INR {payment.amount} towards "
            f"invoice {invoice.invoice_number}.\n"
            f"Invoice status: {invoice.status.value}\n"
            f"Paid at: {payment.paid_at.isoformat() if payment.paid_at else 'n/a'}"
        ),
        payload={
            "payment_id": str(payment.id),
            "amount": float(payment.amount or 0),
            "invoice_status": invoice.status.value,
        },
    )

    return payment, True


def handle_webhook(db: Session, *, body: bytes, signature: str | None):
    """Verify + process a Razorpay webhook (event: payment.captured)."""

    if not razorpay.verify_webhook_signature(body, signature):
        record_audit(
            db,
            actor_id=None,
            action="WEBHOOK_SIGNATURE_INVALID",
            entity_type="PAYMENT",
        )
        db.commit()
        raise PaymentError("Invalid webhook signature.")

    import json

    payload = json.loads(body)
    event = payload.get("event", "")
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})

    order_id = entity.get("order_id")
    payment_id = entity.get("id")

    if event != "payment.captured":
        logger.info("Webhook %s ignored", event)
        return None, False

    known = db.scalar(
        select(Payment).where(Payment.provider_order_id == order_id)
    ) if order_id else None

    if not known:
        # Unknown order -> store as UNMATCHED for accountant review
        unmatched = Payment(
            invoice_id=None,
            resident_id=db.scalar(select(User.id).limit(1)),
            provider="razorpay",
            provider_order_id=order_id,
            provider_payment_id=payment_id,
            amount=Decimal(str(entity.get("amount", 0))) / 100,
            status=PaymentStatus.SUCCESS,
            signature_verified=True,
            paid_at=datetime.utcnow(),
        )

        db.add(unmatched)
        db.flush()

        db.add(
            PaymentReconciliation(
                payment_id=unmatched.id,
                status=ReconciliationStatus.UNMATCHED,
                reconciled_at=datetime.utcnow(),
                note=f"Webhook for unknown order {order_id}",
            )
        )

        record_audit(
            db,
            actor_id=None,
            action="PAYMENT_UNMATCHED_WEBHOOK",
            entity_type="PAYMENT",
            entity_id=unmatched.id,
            new_value={"order": order_id, "provider_payment": payment_id},
        )

        db.commit()
        return unmatched, True

    return capture_success(
        db,
        provider_order_id=order_id,
        provider_payment_id=payment_id,
        signature_verified=True,
        amount=Decimal(str(entity.get("amount", 0))) / 100,
    )


def set_reconciliation(
    db: Session,
    *,
    payment_id: uuid.UUID,
    status_value: ReconciliationStatus,
    actor_id: uuid.UUID,
    note: str | None = None,
) -> PaymentReconciliation:
    recon = db.scalars(
        select(PaymentReconciliation).where(
            PaymentReconciliation.payment_id == payment_id
        )
    ).first()

    if not recon:
        recon = PaymentReconciliation(payment_id=payment_id)

    old_status = recon.status

    recon.status = status_value
    recon.matched_by = actor_id
    recon.note = note
    recon.reconciled_at = datetime.utcnow() if status_value in (
        ReconciliationStatus.MATCHED,
        ReconciliationStatus.MANUAL_REVIEW,
    ) else recon.reconciled_at

    record_audit(
        db,
        actor_id=actor_id,
        action="RECONCILIATION_UPDATED",
        entity_type="PAYMENT_RECONCILIATION",
        entity_id=recon.id,
        old_value={"status": old_status.value} if old_status else None,
        new_value={
            "status": status_value.value,
            "note": note,
        },
    )

    db.commit()
    db.refresh(recon)

    return recon


def payment_mode() -> str:
    return "razorpay" if razorpay.is_configured() else "simulated"


def public_key() -> str:
    return settings.RAZORPAY_KEY_ID
