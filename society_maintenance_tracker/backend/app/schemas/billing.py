import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.invoice import InvoiceStatus
from app.models.invoice_item import InvoiceItemKind
from app.models.maintenance_plan import BillingCycle


# --- Plans (accountant/admin) ---


class PlanCreate(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    amount: Decimal = Field(gt=0)
    cycle: BillingCycle = BillingCycle.MONTHLY
    due_day_of_month: int = Field(default=10, ge=1, le=28)
    late_fee_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    late_fee_grace_days: int = Field(default=0, ge=0)


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    amount: Decimal | None = Field(default=None, gt=0)
    cycle: BillingCycle | None = None
    due_day_of_month: int | None = Field(default=None, ge=1, le=28)
    late_fee_amount: Decimal | None = Field(default=None, ge=0)
    late_fee_grace_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    amount: Decimal
    cycle: BillingCycle
    due_day_of_month: int
    late_fee_amount: Decimal
    late_fee_grace_days: int
    is_active: bool
    created_at: datetime


# --- Invoice items ---


class InvoiceItemResponse(BaseModel):
    id: uuid.UUID
    kind: InvoiceItemKind
    description: str
    unit_price: Decimal
    amount: Decimal


# --- Invoices ---


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    resident_id: uuid.UUID
    plan_id: uuid.UUID | None
    billing_period: str
    subtotal: Decimal
    late_fee: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    status: InvoiceStatus
    due_date: date
    created_at: datetime


class AdminInvoiceResponse(InvoiceResponse):
    resident_name: str | None = None
    resident_email: str | None = None


class InvoiceDetailResponse(InvoiceResponse):
    items: list[InvoiceItemResponse]


class AdminInvoiceListResponse(BaseModel):
    total: int
    items: list[AdminInvoiceResponse]


class BillingRunResponse(BaseModel):
    period: str
    invoices_created: int


class LateFeeRunResponse(BaseModel):
    invoices_penalized: int
