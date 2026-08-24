import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fund import (
    FundTransaction,
    FundTransactionSource,
    FundTransactionType,
    MaintenanceFund,
)
from app.services.audit_service import record_audit

logger = logging.getLogger(__name__)

DEFAULT_FUND_NAME = "Maintenance Fund"


class FundError(Exception):
    pass


class InsufficientFunds(FundError):
    pass


def get_or_create_default_fund(db: Session) -> MaintenanceFund:
    fund = db.scalars(
        select(MaintenanceFund).where(
            MaintenanceFund.name == DEFAULT_FUND_NAME
        )
    ).first()

    if not fund:
        fund = MaintenanceFund(
            name=DEFAULT_FUND_NAME,
            balance=Decimal("0.00"),
        )
        db.add(fund)
        db.flush()  # assign PK without committing caller's tx

    return fund


def list_funds(db: Session) -> list[MaintenanceFund]:
    return list(db.scalars(select(MaintenanceFund)).all())


def _apply(
    db: Session,
    *,
    fund: MaintenanceFund,
    tx_type: FundTransactionType,
    source: FundTransactionSource,
    amount: Decimal,
    description: str | None,
    reference_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
) -> FundTransaction:
    """Lock the fund row, mutate the balance, and append a ledger row.

    Must be called inside the caller's transaction - never commits.
    """
    # Serialize concurrent balance mutations on this fund
    locked = (
        db.query(MaintenanceFund)
        .filter(MaintenanceFund.id == fund.id)
        .with_for_update()
        .one()
    )

    if amount <= 0:
        raise FundError("Amount must be positive.")

    if tx_type == FundTransactionType.CREDIT:
        locked.balance = (locked.balance or Decimal("0.00")) + amount
    else:
        if (locked.balance or Decimal("0.00")) < amount:
            raise InsufficientFunds(
                f"Insufficient funds: balance "
                f"{locked.balance}, requested debit {amount}."
            )
        locked.balance = locked.balance - amount

    tx = FundTransaction(
        fund_id=locked.id,
        type=tx_type,
        source=source,
        amount=amount,
        balance_after=locked.balance,
        reference_id=reference_id,
        description=description,
        created_by=actor_id,
    )

    db.add(tx)

    record_audit(
        db,
        actor_id=actor_id,
        action="FUND_CREDITED" if tx_type == FundTransactionType.CREDIT else "FUND_DEBITED",
        entity_type="MAINTENANCE_FUND",
        entity_id=locked.id,
        old_value=None,
        new_value={
            "type": tx_type.value,
            "source": source.value,
            "amount": float(amount),
            "balance_after": float(locked.balance),
            "reference_id": str(reference_id) if reference_id else None,
            "description": description,
        },
    )

    return tx


def credit_maintenance_payment(
    db: Session,
    *,
    payment_id: uuid.UUID,
    amount: Decimal,
    invoice_number: str | None = None,
) -> FundTransaction:
    """Auto-credit on successful maintenance payment (called from
    capture_success inside its transaction)."""
    fund = get_or_create_default_fund(db)

    return _apply(
        db,
        fund=fund,
        tx_type=FundTransactionType.CREDIT,
        source=FundTransactionSource.MAINTENANCE_PAYMENT,
        amount=amount,
        description=f"Maintenance payment for {invoice_number}"
        if invoice_number
        else "Maintenance payment",
        reference_id=payment_id,
        actor_id=None,
    )


def manual_transaction(
    db: Session,
    *,
    fund: MaintenanceFund,
    tx_type: FundTransactionType,
    amount: Decimal,
    description: str | None,
    actor_id: uuid.UUID,
) -> FundTransaction:
    source = (
        FundTransactionSource.MANUAL_CREDIT
        if tx_type == FundTransactionType.CREDIT
        else FundTransactionSource.MANUAL_DEBIT
    )

    return _apply(
        db,
        fund=fund,
        tx_type=tx_type,
        source=source,
        amount=amount,
        description=description,
        reference_id=None,
        actor_id=actor_id,
    )


def debit_for_expense(
    db: Session,
    *,
    expense_id: uuid.UUID,
    amount: Decimal,
    title: str,
) -> FundTransaction:
    """Debit when an expense is recorded (caller's transaction)."""
    fund = get_or_create_default_fund(db)

    return _apply(
        db,
        fund=fund,
        tx_type=FundTransactionType.DEBIT,
        source=FundTransactionSource.EXPENSE,
        amount=amount,
        description=f"Expense: {title}",
        reference_id=expense_id,
        actor_id=None,
    )
