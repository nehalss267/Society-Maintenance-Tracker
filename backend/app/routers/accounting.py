import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_accountant
from app.models.expense import Expense, ExpenseCategory
from app.models.fund import FundTransaction
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.schemas.accounting import (
    ExpenseCreateRequest,
    ExpenseResponse,
    ExpenseUpdateRequest,
    FundResponse,
    FundTransactionResponse,
    ManualFundTxRequest,
    RecurringExpenseCreateRequest,
    RecurringExpenseResponse,
    RecurringExpenseUpdateRequest,
)
from app.services import expense_service, fund_service
from app.services.audit_service import record_audit
from app.services.storage_service import StorageValidationError, save_receipt


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin · Accounting"],
)


def _expense_response(e: Expense) -> ExpenseResponse:
    return ExpenseResponse(
        id=e.id,
        title=e.title,
        description=e.description,
        category=e.category,
        amount=e.amount,
        expense_date=e.expense_date,
        vendor=e.vendor,
        receipt_file_path=e.receipt_file_path,
        source_recurring_id=e.source_recurring_id,
        created_by=e.created_by,
        created_at=e.created_at,
    )


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


@router.get("/expenses", response_model=list[ExpenseResponse])
def list_expenses(
    category: ExpenseCategory | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    query = (
        select(Expense)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if category:
        query = query.where(Expense.category == category)

    if from_date:
        query = query.where(Expense.expense_date >= from_date)

    if to_date:
        query = query.where(Expense.expense_date <= to_date)

    return [_expense_response(e) for e in db.scalars(query).all()]


@router.post(
    "/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    request: ExpenseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_accountant),
):
    try:
        expense = expense_service.create_expense(
            db,
            title=request.title,
            category=request.category,
            amount=request.amount,
            expense_date=request.expense_date,
            description=request.description,
            vendor=request.vendor,
            actor_id=current_user.id,
        )
    except fund_service.InsufficientFunds as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return _expense_response(expense)


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: uuid.UUID,
    request: ExpenseUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_accountant),
):
    expense = db.get(Expense, expense_id)

    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    updates = {
        k: v for k, v in request.model_dump(exclude_unset=True).items()
    }

    if "amount" in updates and updates["amount"] is not None and updates["amount"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Amount must be positive.",
        )

    try:
        updated = expense_service.update_expense(
            db,
            expense=expense,
            updates=updates,
            actor_id=current_user.id,
        )
    except fund_service.InsufficientFunds as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return _expense_response(updated)


@router.post("/expenses/{expense_id}/receipt", response_model=ExpenseResponse)
async def upload_receipt(
    expense_id: uuid.UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_accountant),
):
    expense = db.get(Expense, expense_id)

    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )

    data = await file.read()

    try:
        path = save_receipt(data=data, filename=file.filename or "receipt")
    except StorageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    expense.receipt_file_path = path
    record_audit(
        db,
        actor_id=current_user.id,
        action="EXPENSE_RECEIPT_UPLOADED",
        entity_type="EXPENSE",
        entity_id=expense.id,
        new_value={"path": path},
    )
    db.commit()
    db.refresh(expense)

    return _expense_response(expense)


# ---------------------------------------------------------------------------
# Recurring expenses
# ---------------------------------------------------------------------------


def _recurring_response(r: RecurringExpense) -> RecurringExpenseResponse:
    return RecurringExpenseResponse(
        id=r.id,
        title=r.title,
        category=r.category,
        amount=r.amount,
        frequency=r.frequency,
        day_of_month=r.day_of_month,
        next_run_date=r.next_run_date,
        is_active=r.is_active,
        last_generated_period=r.last_generated_period,
        vendor=r.vendor,
    )


@router.get("/recurring-expenses", response_model=list[RecurringExpenseResponse])
def list_recurring(
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    rows = db.scalars(select(RecurringExpense)).all()
    return [_recurring_response(r) for r in rows]


@router.post(
    "/recurring-expenses",
    response_model=RecurringExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recurring(
    request: RecurringExpenseCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    start = request.start_date or date.today()
    day = min(request.day_of_month, 28)

    first_run = date(start.year, start.month, day)

    if first_run < start:
        first_run = expense_service._next_run_after(
            request.frequency, start.year, start.month, day
        )

    rec = RecurringExpense(
        title=request.title,
        category=request.category,
        amount=request.amount,
        frequency=request.frequency,
        day_of_month=request.day_of_month,
        vendor=request.vendor,
        next_run_date=first_run,
    )

    db.add(rec)
    db.commit()
    db.refresh(rec)

    return _recurring_response(rec)


@router.patch(
    "/recurring-expenses/{rec_id}",
    response_model=RecurringExpenseResponse,
)
def update_recurring(
    rec_id: uuid.UUID,
    request: RecurringExpenseUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    rec = db.get(RecurringExpense, rec_id)

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring expense not found",
        )

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(rec, field, value)

    db.commit()
    db.refresh(rec)

    return _recurring_response(rec)


@router.post("/expenses/generate-recurring/{period}")
def generate_recurring(
    period: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    """Manual trigger; the same service function runs from the scheduler."""
    try:
        created = expense_service.generate_recurring_expenses_for_period(
            db, period=period
        )
    except expense_service.ExpenseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return {"period": period, "generated": created}


# ---------------------------------------------------------------------------
# Funds
# ---------------------------------------------------------------------------


@router.get("/funds", response_model=list[FundResponse])
def list_funds(
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    return [
        FundResponse(id=f.id, name=f.name, balance=f.balance)
        for f in fund_service.list_funds(db)
    ]


@router.get("/funds/transactions", response_model=list[FundTransactionResponse])
def list_fund_transactions(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    rows = db.scalars(
        select(FundTransaction)
        .order_by(FundTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return [
        FundTransactionResponse(
            id=t.id,
            fund_id=t.fund_id,
            type=t.type,
            source=t.source,
            amount=t.amount,
            balance_after=t.balance_after,
            reference_id=t.reference_id,
            description=t.description,
            created_by=t.created_by,
            created_at=t.created_at,
        )
        for t in rows
    ]


@router.post("/funds/transactions", response_model=FundTransactionResponse)
def manual_fund_transaction(
    request: ManualFundTxRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_accountant),
):
    fund = fund_service.get_or_create_default_fund(db)

    try:
        tx = fund_service.manual_transaction(
            db,
            fund=fund,
            tx_type=request.type,
            amount=request.amount,
            description=request.description,
            actor_id=current_user.id,
        )
    except fund_service.InsufficientFunds as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    db.commit()
    db.refresh(tx)

    return FundTransactionResponse(
        id=tx.id,
        fund_id=tx.fund_id,
        type=tx.type,
        source=tx.source,
        amount=tx.amount,
        balance_after=tx.balance_after,
        reference_id=tx.reference_id,
        description=tx.description,
        created_by=tx.created_by,
        created_at=tx.created_at,
    )
