import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.models.expense import ExpenseCategory
from app.models.fund import FundTransactionSource, FundTransactionType
from app.models.recurring_expense import ExpenseFrequency


class ExpenseCreateRequest(BaseModel):
    title: str
    category: ExpenseCategory
    amount: Decimal
    expense_date: date
    description: str | None = None
    vendor: str | None = None

    @field_validator("amount")
    @classmethod
    def positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("title", "vendor", "description")
    @classmethod
    def strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class ExpenseUpdateRequest(BaseModel):
    title: str | None = None
    category: ExpenseCategory | None = None
    amount: Decimal | None = None
    expense_date: date | None = None
    description: str | None = None
    vendor: str | None = None


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    category: ExpenseCategory
    amount: Decimal
    expense_date: date
    vendor: str | None
    receipt_file_path: str | None
    source_recurring_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: datetime


class RecurringExpenseCreateRequest(BaseModel):
    title: str
    category: ExpenseCategory
    amount: Decimal
    frequency: ExpenseFrequency
    day_of_month: int
    vendor: str | None = None
    start_date: date | None = None

    @field_validator("amount")
    @classmethod
    def positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be positive")
        return v

    @field_validator("day_of_month")
    @classmethod
    def valid_day(cls, v):
        if not 1 <= v <= 28:
            raise ValueError("day_of_month must be between 1 and 28")
        return v


class RecurringExpenseUpdateRequest(BaseModel):
    title: str | None = None
    amount: Decimal | None = None
    frequency: ExpenseFrequency | None = None
    day_of_month: int | None = None
    is_active: bool | None = None
    vendor: str | None = None


class RecurringExpenseResponse(BaseModel):
    id: uuid.UUID
    title: str
    category: ExpenseCategory
    amount: Decimal
    frequency: ExpenseFrequency
    day_of_month: int
    next_run_date: date
    is_active: bool
    last_generated_period: str | None
    vendor: str | None


class FundResponse(BaseModel):
    id: uuid.UUID
    name: str
    balance: Decimal


class FundTransactionResponse(BaseModel):
    id: uuid.UUID
    fund_id: uuid.UUID
    type: FundTransactionType
    source: FundTransactionSource
    amount: Decimal
    balance_after: Decimal
    reference_id: uuid.UUID | None
    description: str | None
    created_by: uuid.UUID | None
    created_at: datetime


class ManualFundTxRequest(BaseModel):
    type: FundTransactionType
    amount: Decimal
    description: str | None = None

    @field_validator("amount")
    @classmethod
    def positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be positive")
        return v
