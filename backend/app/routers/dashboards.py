import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set, invalidate_prefix
from app.core.database import get_db
from app.dependencies.auth import (
    get_current_user,
    require_accountant,
    require_committee,
)
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus
from app.models.complaint_sla import ComplaintSla
from app.models.expense import Expense, ExpenseCategory
from app.models.fund import MaintenanceFund
from app.models.invoice import Invoice, InvoiceStatus, UNPAID_STATUSES
from app.models.notice import Notice
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboards"],
)

report_router = APIRouter(
    prefix="/api/admin/reports",
    tags=["Admin · Reports"],
)

CACHE_TTL = 60


def _num(v) -> float:
    return float(v or 0)


# ---------------------------------------------------------------------------
# Resident dashboard
# ---------------------------------------------------------------------------


@router.get("/resident")
def resident_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    key = f"dash:resident:{current_user.id}"
    cached = cache_get(key)

    if cached is not None:
        return cached

    open_complaints = len(
        db.scalars(
            select(Complaint.id).where(
                Complaint.resident_id == current_user.id,
                Complaint.status.in_([ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS]),
            )
        ).all()
    )

    resolved_complaints = len(
        db.scalars(
            select(Complaint.id).where(
                Complaint.resident_id == current_user.id,
                Complaint.status == ComplaintStatus.RESOLVED,
            )
        ).all()
    )

    my_invoices = list(
        db.scalars(select(Invoice).where(Invoice.resident_id == current_user.id)).all()
    )

    unpaid = [i for i in my_invoices if i.status in UNPAID_STATUSES]

    overdue_notices = list(
        db.scalars(
            select(Notice)
            .where(Notice.is_important.is_(True))
            .order_by(Notice.created_at.desc())
            .limit(3)
        ).all()
    )

    data = {
        "complaints": {
            "open": open_complaints,
            "resolved": resolved_complaints,
        },
        "billing": {
            "unpaid_count": len(unpaid),
            "outstanding_amount": _num(sum(i.total_amount - i.amount_paid for i in unpaid)),
            "overdue_count": sum(1 for i in my_invoices if i.status == InvoiceStatus.OVERDUE),
        },
        "important_notices": [
            {"id": str(n.id), "title": n.title} for n in overdue_notices
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }

    cache_set(key, data, CACHE_TTL)

    return data


# ---------------------------------------------------------------------------
# Staff dashboard (committee/admin)
# ---------------------------------------------------------------------------


@router.get("/staff")
def staff_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_committee),
):
    cached = cache_get("dash:staff")

    if cached is not None:
        return cached

    by_status = dict(
        db.execute(
            select(Complaint.status, func.count())
            .group_by(Complaint.status)
        ).all()
    )

    by_priority = dict(
        db.execute(
            select(Complaint.priority, func.count())
            .group_by(Complaint.priority)
        ).all()
    )

    overdue = len(
        db.scalars(
            select(ComplaintSla.id).where(ComplaintSla.breached.is_(True))
        ).all()
    )

    total_residents = len(
        db.scalars(select(User.id).where(User.role == UserRole.RESIDENT)).all()
    )

    data = {
        "complaints_by_status": {k.value: v for k, v in by_status.items()},
        "complaints_by_priority": {k.value: v for k, v in by_priority.items()},
        "sla_breached": overdue,
        "total_residents": total_residents,
        "generated_at": datetime.utcnow().isoformat(),
    }

    cache_set("dash:staff", data, CACHE_TTL)

    return data


# ---------------------------------------------------------------------------
# Accountant dashboard
# ---------------------------------------------------------------------------


@router.get("/accountant")
def accountant_dashboard(
    period: str | None = Query(default=None, description="YYYY-MM; defaults to current"),
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    from app.services.billing_service import current_period

    period = period or current_period()

    key = f"dash:accountant:{period}"
    cached = cache_get(key)

    if cached is not None:
        return cached

    invoices = list(
        db.scalars(
            select(Invoice).where(Invoice.billing_period == period)
        ).all()
    )

    collected = _num(sum(i.amount_paid for i in invoices))
    billed = _num(sum(i.total_amount for i in invoices))

    fund = db.scalars(select(MaintenanceFund)).first()

    month_start = date.today().replace(day=1)

    expenses_this_month = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.expense_date >= month_start
        )
    )

    payments_count = len(
        db.scalars(
            select(Payment.id).where(Payment.status == PaymentStatus.SUCCESS)
        ).all()
    )

    data = {
        "period": period,
        "invoices": {
            "count": len(invoices),
            "billed": billed,
            "collected": collected,
            "outstanding": round(billed - collected, 2),
            "overdue": sum(1 for i in invoices if i.status == InvoiceStatus.OVERDUE),
        },
        "fund_balance": _num(fund.balance) if fund else 0.0,
        "expenses_this_month": _num(expenses_this_month),
        "successful_payments_total": payments_count,
        "generated_at": datetime.utcnow().isoformat(),
    }

    cache_set(key, data, CACHE_TTL)

    return data


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@report_router.get("/expenses")
def expense_report(
    from_date: date | None = None,
    to_date: date | None = None,
    category: ExpenseCategory | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    filters = []

    if from_date:
        filters.append(Expense.expense_date >= from_date)

    if to_date:
        filters.append(Expense.expense_date <= to_date)

    if category:
        filters.append(Expense.category == category)

    stmt = select(
        Expense.category,
        func.count(),
        func.coalesce(func.sum(Expense.amount), 0),
    ).group_by(Expense.category)

    for f in filters:
        stmt = stmt.where(f)

    rows = db.execute(stmt).all()

    total = sum(float(r[2]) for r in rows)

    return {
        "rows": [
            {"category": r[0].value, "count": r[1], "total": float(r[2])}
            for r in rows
        ],
        "grand_total": total,
    }


@report_router.get("/collections")
def collections_report(
    period: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_accountant),
):
    from app.services.billing_service import current_period

    period = period or current_period()

    invoices = list(
        db.scalars(
            select(Invoice).where(Invoice.billing_period == period)
        ).all()
    )

    by_status: dict[str, float] = {}

    for i in invoices:
        by_status[i.status.value] = by_status.get(i.status.value, 0.0) + float(
            i.total_amount - i.amount_paid
        )

    return {
        "period": period,
        "invoice_count": len(invoices),
        "billed_total": _num(sum(i.total_amount for i in invoices)),
        "collected_total": _num(sum(i.amount_paid for i in invoices)),
        "outstanding_by_status": by_status,
    }
