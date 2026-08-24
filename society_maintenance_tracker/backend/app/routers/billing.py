from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_accountant
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_item import InvoiceItem
from app.models.maintenance_plan import MaintenancePlan
from app.models.user import User
from app.schemas.billing import (
    AdminInvoiceListResponse,
    AdminInvoiceResponse,
    BillingRunResponse,
    InvoiceDetailResponse,
    InvoiceItemResponse,
    InvoiceResponse,
    LateFeeRunResponse,
    PlanCreate,
    PlanResponse,
    PlanUpdate,
)
from app.services import billing_service


router = APIRouter(
    prefix="/api/invoices",
    tags=["Invoices"],
)

admin_router = APIRouter(
    prefix="/api/admin",
    tags=["Admin · Billing"],
)


def _invoice_response(inv: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=inv.id,
        invoice_number=inv.invoice_number,
        resident_id=inv.resident_id,
        plan_id=inv.plan_id,
        billing_period=inv.billing_period,
        subtotal=inv.subtotal,
        late_fee=inv.late_fee,
        total_amount=inv.total_amount,
        amount_paid=inv.amount_paid,
        status=inv.status,
        due_date=inv.due_date,
        created_at=inv.created_at,
    )


# ---------------------------------------------------------------------------
# Resident endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[InvoiceResponse],
)
def list_my_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.resident_id == current_user.id)
        .order_by(Invoice.billing_period.desc())
    ).all()

    return [_invoice_response(i) for i in invoices]


@router.get(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
)
def get_my_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.items))
        .filter(
            Invoice.id == invoice_id,
            Invoice.resident_id == current_user.id,
        )
        .first()
    )

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    return InvoiceDetailResponse(
        **_invoice_response(invoice).model_dump(),
        items=[
            InvoiceItemResponse(
                id=item.id,
                kind=item.kind,
                description=item.description,
                unit_price=item.unit_price,
                amount=item.amount,
            )
            for item in invoice.items
        ],
    )


# ---------------------------------------------------------------------------
# Accountant / admin endpoints
# ---------------------------------------------------------------------------


@admin_router.get("/plans", response_model=list[PlanResponse])
def list_plans(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    query = select(MaintenancePlan).order_by(MaintenancePlan.name)

    if not include_inactive:
        query = query.where(MaintenancePlan.is_active.is_(True))

    return db.scalars(query).all()


@admin_router.post(
    "/plans",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_plan(
    request: PlanCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    exists = db.scalar(
        select(MaintenancePlan.id).where(
            MaintenancePlan.name == request.name.strip()
        )
    )

    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A plan with this name already exists",
        )

    plan = MaintenancePlan(
        name=request.name.strip(),
        description=request.description,
        amount=request.amount,
        cycle=request.cycle,
        due_day_of_month=request.due_day_of_month,
        late_fee_amount=request.late_fee_amount,
        late_fee_grace_days=request.late_fee_grace_days,
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)

    return plan


@admin_router.patch("/plans/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: UUID,
    request: PlanUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    plan = db.get(MaintenancePlan, plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    updates = request.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if field == "name":
            value = value.strip()

        setattr(plan, field, value)

    db.commit()
    db.refresh(plan)

    return plan


@admin_router.post(
    "/billing/run/{period}",
    response_model=BillingRunResponse,
)
def run_billing_generation(
    period: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    try:
        billing_service.period_to_dates(period)
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Period must be in YYYY-MM format.",
        )

    created = billing_service.generate_invoices_for_period(db, period)

    return BillingRunResponse(
        period=period,
        invoices_created=len(created),
    )


@admin_router.post(
    "/billing/late-fees",
    response_model=LateFeeRunResponse,
)
def run_late_fees(
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    penalized = billing_service.apply_late_fees(db)

    return LateFeeRunResponse(invoices_penalized=len(penalized))


@admin_router.get(
    "/invoices",
    response_model=AdminInvoiceListResponse,
)
def list_all_invoices(
    invoice_status: InvoiceStatus | None = Query(default=None, alias="status"),
    period: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    base_filters = []

    if invoice_status is not None:
        base_filters.append(Invoice.status == invoice_status)

    if period:
        base_filters.append(Invoice.billing_period == period)

    count_query = select(func.count(Invoice.id))

    for condition in base_filters:
        count_query = count_query.where(condition)

    total = db.scalar(count_query) or 0

    query = (
        select(Invoice)
        .options(joinedload(Invoice.plan), joinedload(Invoice.resident))
        .order_by(Invoice.billing_period.desc(), Invoice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    for condition in base_filters:
        query = query.where(condition)

    invoices = db.scalars(query).all()

    return AdminInvoiceListResponse(
        total=total,
        items=[
            AdminInvoiceResponse(
                **_invoice_response(i).model_dump(),
                resident_name=i.resident.name if i.resident else None,
                resident_email=i.resident.email if i.resident else None,
            )
            for i in invoices
        ],
    )
