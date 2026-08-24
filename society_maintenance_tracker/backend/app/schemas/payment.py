import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.payment import PaymentStatus
from app.models.reconciliation import ReconciliationStatus


class InitiatePaymentRequest(BaseModel):
    invoice_id: uuid.UUID


class InitiatePaymentResponse(BaseModel):
    payment_id: uuid.UUID
    invoice_id: uuid.UUID
    provider: str
    mode: str
    razorpay_key_id: str | None
    order_id: str
    amount: Decimal
    currency: str


class SimulatePaymentRequest(BaseModel):
    payment_id: uuid.UUID


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID | None
    provider: str
    provider_order_id: str | None
    provider_payment_id: str | None
    amount: Decimal
    currency: str
    status: PaymentStatus
    signature_verified: bool
    paid_at: datetime | None
    created_at: datetime


class ReconciliationResponse(BaseModel):
    id: uuid.UUID
    payment_id: uuid.UUID
    status: ReconciliationStatus
    matched_by: uuid.UUID | None
    note: str | None
    reconciled_at: datetime | None
    created_at: datetime


class ReconciliationUpdateRequest(BaseModel):
    status: ReconciliationStatus
    note: str | None = None
