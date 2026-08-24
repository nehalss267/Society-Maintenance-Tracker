from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_accountant
from app.integrations import razorpay
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentStatus
from app.models.reconciliation import PaymentReconciliation, ReconciliationStatus
from app.models.user import User
from app.schemas.payment import (
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    PaymentResponse,
    ReconciliationResponse,
    ReconciliationUpdateRequest,
    SimulatePaymentRequest,
    VerifyPaymentRequest,
)
from app.services import payment_service


router = APIRouter(
    prefix="/api/payments",
    tags=["Payments"],
)

admin_router = APIRouter(
    prefix="/api/admin",
    tags=["Admin · Payments"],
)

webhook_router = APIRouter(
    prefix="/api/webhooks",
    tags=["Webhooks"],
)


def _payment_response(p: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=p.id,
        invoice_id=p.invoice_id,
        provider=p.provider,
        provider_order_id=p.provider_order_id,
        provider_payment_id=p.provider_payment_id,
        amount=p.amount,
        currency=p.currency,
        status=p.status,
        signature_verified=p.signature_verified,
        paid_at=p.paid_at,
        created_at=p.created_at,
    )


@router.post(
    "/initiate",
    response_model=InitiatePaymentResponse,
)
def initiate(
    request: InitiatePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.get(Invoice, request.invoice_id)

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    try:
        payment = payment_service.initiate_payment(
            db,
            invoice=invoice,
            resident_id=current_user.id,
        )
    except payment_service.PaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return InitiatePaymentResponse(
        payment_id=payment.id,
        invoice_id=invoice.id,
        provider="razorpay",
        mode=payment_service.payment_mode(),
        razorpay_key_id=(
            razorpay.get_public_key()
            if razorpay.is_configured()
            else None
        ),
        order_id=payment.provider_order_id,
        amount=payment.amount,
        currency=payment.currency,
    )


@router.post(
    "/simulate-success",
    response_model=PaymentResponse,
)
def simulate_success(
    request: SimulatePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fallback capture path when Razorpay keys are absent.

    Disabled whenever real credentials are configured.
    """
    if razorpay.is_configured():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Simulation is disabled when Razorpay is configured.",
        )

    payment = db.get(Payment, request.payment_id)

    if not payment or payment.resident_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    try:
        captured, _created = payment_service.capture_success(
            db,
            provider_order_id=payment.provider_order_id,
            provider_payment_id=f"pay_sim_{payment.id.hex[:14]}",
            signature_verified=False,
        )
    except payment_service.PaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return _payment_response(captured)


@router.post(
    "/verify",
    response_model=PaymentResponse,
)
def verify(
    request: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Checkout callback verification (real Razorpay flow)."""
    if not razorpay.is_configured():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Razorpay is not configured.",
        )

    valid = razorpay.verify_payment_signature(
        razorpay_order_id=request.razorpay_order_id,
        razorpay_payment_id=request.razorpay_payment_id,
        razorpay_signature=request.razorpay_signature,
    )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature verification failed.",
        )

    try:
        captured, _ = payment_service.capture_success(
            db,
            provider_order_id=request.razorpay_order_id,
            provider_payment_id=request.razorpay_payment_id,
            signature_verified=True,
        )
    except payment_service.PaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return _payment_response(captured)


@router.get(
    "",
    response_model=list[PaymentResponse],
)
def my_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payments = db.scalars(
        select(Payment)
        .where(Payment.resident_id == current_user.id)
        .order_by(Payment.created_at.desc())
    ).all()

    return [_payment_response(p) for p in payments]


@admin_router.get(
    "/payments",
    response_model=list[PaymentResponse],
)
def all_payments(
    payment_status: PaymentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    query = select(Payment).order_by(Payment.created_at.desc()).limit(limit)

    if payment_status is not None:
        query = query.where(Payment.status == payment_status)

    return [
        _payment_response(p)
        for p in db.scalars(query).all()
    ]


@admin_router.get(
    "/reconciliation",
    response_model=list[ReconciliationResponse],
)
def list_reconciliation(
    recon_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    query = (
        select(PaymentReconciliation)
        .order_by(PaymentReconciliation.created_at.desc())
        .limit(200)
    )

    if recon_status:
        try:
            query = query.where(
                PaymentReconciliation.status
                == ReconciliationStatus[recon_status.upper()]
            )
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unknown reconciliation status.",
            )

    rows = db.scalars(query).all()

    return [
        ReconciliationResponse(
            id=r.id,
            payment_id=r.payment_id,
            status=r.status,
            matched_by=r.matched_by,
            note=r.note,
            reconciled_at=r.reconciled_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@admin_router.patch(
    "/reconciliation/{payment_id}",
    response_model=ReconciliationResponse,
)
def update_reconciliation(
    payment_id: UUID,
    request: ReconciliationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_accountant),
):
    exists = db.get(Payment, payment_id)

    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    recon = payment_service.set_reconciliation(
        db,
        payment_id=payment_id,
        status_value=request.status,
        actor_id=current_user.id,
        note=request.note,
    )

    return ReconciliationResponse(
        id=recon.id,
        payment_id=recon.payment_id,
        status=recon.status,
        matched_by=recon.matched_by,
        note=recon.note,
        reconciled_at=recon.reconciled_at,
        created_at=recon.created_at,
    )


@webhook_router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    try:
        result, created = payment_service.handle_webhook(
            db,
            body=body,
            signature=signature,
        )
    except payment_service.PaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "accepted": True,
        "processed": bool(result),
        "newly_captured": created,
    }
