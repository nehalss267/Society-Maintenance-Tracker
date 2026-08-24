import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FundTransactionType(str, enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class FundTransactionSource(str, enum.Enum):
    MAINTENANCE_PAYMENT = "MAINTENANCE_PAYMENT"
    EXPENSE = "EXPENSE"
    MANUAL_CREDIT = "MANUAL_CREDIT"
    MANUAL_DEBIT = "MANUAL_DEBIT"
    ADJUSTMENT = "ADJUSTMENT"


class MaintenanceFund(Base):
    __tablename__ = "maintenance_funds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
    )

    # Authoritative running balance - mutated only inside fund_service
    # within the same transaction that writes the fund_transaction row.
    balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=Decimal("0.00"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    transactions = relationship(
        "FundTransaction",
        back_populates="fund",
    )


class FundTransaction(Base):
    __tablename__ = "fund_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_funds.id"),
        nullable=False,
        index=True,
    )

    type: Mapped[FundTransactionType] = mapped_column(
        Enum(FundTransactionType, name="fund_transaction_type"),
        nullable=False,
    )

    source: Mapped[FundTransactionSource] = mapped_column(
        Enum(FundTransactionSource, name="fund_transaction_source"),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # Balance snapshot after this transaction - makes the ledger fully
    # reconstructable and auditable.
    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
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

    fund = relationship(
        "MaintenanceFund",
        back_populates="transactions",
    )
