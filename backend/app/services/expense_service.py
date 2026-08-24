import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseCategory
from app.models.recurring_expense import ExpenseFrequency, RecurringExpense
from app.services import fund_service
from app.services.audit_service import record_audit

logger = logging.getLogger(__name__)


class ExpenseError(Exception):
    pass


def create_expense(
    db: Session,
    *,
    title: str,
    category: ExpenseCategory,
    amount: Decimal,
    expense_date: date,
    description: str | None = None,
    vendor: str | None = None,
    actor_id: uuid.UUID,
) -> Expense:
    expense = Expense(
        title=title,
        category=category,
        amount=amount,
        expense_date=expense_date,
        description=description,
        vendor=vendor,
        created_by=actor_id,
    )

    db.add(expense)
    db.flush()

    # Debit the fund in the same transaction (fails -> whole tx rolls back)
    fund_service.debit_for_expense(
        db,
        expense_id=expense.id,
        amount=amount,
        title=title,
    )

    record_audit(
        db,
        actor_id=actor_id,
        action="EXPENSE_CREATED",
        entity_type="EXPENSE",
        entity_id=expense.id,
        new_value={
            "title": title,
            "category": category.value,
            "amount": float(amount),
            "expense_date": expense_date.isoformat(),
            "vendor": vendor,
        },
    )

    db.commit()
    db.refresh(expense)

    return expense


def update_expense(
    db: Session,
    *,
    expense: Expense,
    updates: dict,
    actor_id: uuid.UUID,
) -> Expense:
    old_amount = expense.amount

    for field, value in updates.items():
        setattr(expense, field, value)

    new_amount = expense.amount

    if new_amount != old_amount:
        delta = new_amount - old_amount

        # Compensating ledger movement keeps the fund consistent
        if delta > 0:
            fund_service.debit_for_expense(
                db,
                expense_id=expense.id,
                amount=delta,
                title=f"{expense.title} (amount revision)",
            )
        else:
            default_fund = fund_service.get_or_create_default_fund(db)
            from app.models.fund import (
                FundTransactionSource,
                FundTransactionType,
            )

            fund_service._apply(
                db,
                fund=default_fund,
                tx_type=FundTransactionType.CREDIT,
                source=FundTransactionSource.ADJUSTMENT,
                amount=abs(delta),
                description=f"Refund on expense revision: {expense.title}",
                reference_id=expense.id,
                actor_id=actor_id,
            )

    record_audit(
        db,
        actor_id=actor_id,
        action="EXPENSE_UPDATED",
        entity_type="EXPENSE",
        entity_id=expense.id,
        old_value={"amount": float(old_amount)},
        new_value={k: str(v) for k, v in updates.items()},
    )

    db.commit()
    db.refresh(expense)

    return expense


# ---------------------------------------------------------------------------
# Recurring expenses
# ---------------------------------------------------------------------------


def _period_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _next_run_after(freq: ExpenseFrequency, year: int, month: int, day: int) -> date:
    if freq == ExpenseFrequency.MONTHLY:
        m = month + 1
        y = year + (m - 1) // 12
        m = (m - 1) % 12 + 1
    elif freq == ExpenseFrequency.QUARTERLY:
        m = month + 3
        y = year + (m - 1) // 12
        m = (m - 1) % 12 + 1
    else:  # ANNUAL
        y, m = year + 1, month

    return date(y, m, min(day, 28))


def generate_recurring_expenses_for_period(
    db: Session,
    *,
    period: str,  # "YYYY-MM"
) -> int:
    """Generate actual expense rows from active recurring definitions whose
    next_run_date falls within the period.

    Idempotent via the unique constraint on (source_recurring_id,
    generated_period).
    """
    try:
        year, month = int(period[:4]), int(period[5:7])
    except ValueError as exc:
        raise ExpenseError("Period must be formatted YYYY-MM.") from exc

    definitions = list(
        db.scalars(
            select(RecurringExpense).where(
                RecurringExpense.is_active.is_(True)
            )
        ).all()
    )

    created = 0

    for rec in definitions:
        run = rec.next_run_date

        while run.year == year and run.month == month:
            dup = db.scalar(
                select(Expense.id).where(
                    Expense.source_recurring_id == rec.id,
                    Expense.generated_period == period,
                )
            )

            if dup:
                break

            expense = Expense(
                title=rec.title,
                category=rec.category,
                amount=rec.amount,
                expense_date=run,
                vendor=rec.vendor,
                source_recurring_id=rec.id,
                generated_period=period,
            )
            db.add(expense)
            db.flush()

            fund_service.debit_for_expense(
                db,
                expense_id=expense.id,
                amount=rec.amount,
                title=rec.title,
            )

            rec.last_generated_period = period
            rec.next_run_date = _next_run_after(
                rec.frequency, run.year, run.month, rec.day_of_month
            )
            created += 1
            break

    db.commit()
    logger.info("Generated %s recurring expenses for %s", created, period)

    return created
