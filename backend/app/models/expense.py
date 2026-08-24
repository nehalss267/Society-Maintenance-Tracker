import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ExpenseCategory(str, enum.Enum):
    ELECTRICITY = "ELECTRICITY"
    WATER = "WATER"
    SECURITY = "SECURITY"
    REPAIRS = "REPAIRS"
    CLEANING = "CLEANING"
    SALARIES = "SALARIES"
    OTHER = "OTHER"


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    category: Mapped[ExpenseCategory] = mapped_column(
        Enum(ExpenseCategory, name="expense_category"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    expense_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    vendor: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    receipt_file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Set when the row was generated from a recurring definition
    source_recurring_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recurring_expenses.id"),
        nullable=True,
    )

    # Period tag ("YYYY-MM") enabling duplicate-free recurring generation
    generated_period: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    creator = relationship("User", foreign_keys=[created_by])
