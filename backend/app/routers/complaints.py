from datetime import datetime
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.database import get_db
from app.core.sla import (
    compute_due_at,
    get_target_days,
    is_complaint_overdue,
    is_valid_category,
)
from app.dependencies.auth import get_current_user, require_committee
from app.models.audit_log import AuditLog
from app.models.complaint import (
    Complaint,
    ComplaintPriority,
    ComplaintStatus,
)
from app.models.complaint_history import ComplaintStatusHistory
from app.models.complaint_sla import ComplaintSla
from app.models.user import User
from app.schemas.complaint import (
    AdminComplaintListResponse,
    AdminComplaintResponse,
    ComplaintCreate,
    ComplaintDetailResponse,
    ComplaintHistoryItem,
    ComplaintHistoryListResponse,
    ComplaintPriorityUpdate,
    ComplaintResponse,
    ComplaintStatusUpdate,
)
from app.services import notification_service, storage_service
from app.services.complaint_service import InvalidStatusTransition
from app.services.complaint_service import (
    validate_status_transition,
)
from app.services.storage_service import StorageError


router = APIRouter(
    prefix="/api/complaints",
    tags=["Complaints"],
)

admin_router = APIRouter(
    prefix="/api/admin/complaints",
    tags=["Admin · Complaints"],
)


def _is_overdue(complaint: Complaint, now: datetime) -> bool:
    due_at = complaint.sla.due_at if complaint.sla else None
    return is_complaint_overdue(
        status_value=complaint.status.value,
        due_at=due_at,
        resolved=complaint.status == ComplaintStatus.RESOLVED,
        now=now,
    )


# ---------------------------------------------------------------------------
# Resident endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ComplaintDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_complaint(
    category: str = Form(...),
    description: str = Form(...),
    photo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payload = ComplaintCreate(
            category=category,
            description=description,
        )
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Invalid complaint data. Category must be one of "
                "PLUMBING, ELECTRICAL, CLEANING, SECURITY, OTHER and "
                "description must be 10-5000 characters."
            ),
        )

    normalized_category = payload.category.strip().upper()

    if not is_valid_category(normalized_category):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported complaint category.",
        )

    try:
        photo_url = await storage_service.save_complaint_photo(photo)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    now = datetime.utcnow()

    complaint = Complaint(
        resident_id=current_user.id,
        category=normalized_category,
        description=payload.description.strip(),
        photo_url=photo_url,
        status=ComplaintStatus.OPEN,
        priority=ComplaintPriority.MEDIUM,
        created_at=now,
        updated_at=now,
    )

    db.add(complaint)
    db.flush()

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        status=ComplaintStatus.OPEN,
        changed_by=current_user.id,
        note="Complaint created",
        changed_at=now,
    )

    sla = ComplaintSla(
        complaint_id=complaint.id,
        target_days=get_target_days(normalized_category),
        due_at=compute_due_at(now, normalized_category),
    )

    db.add(history)
    db.add(sla)

    db.commit()
    db.refresh(complaint)

    return _build_detail(db, complaint)


@router.get(
    "",
    response_model=list[ComplaintResponse],
)
def list_my_complaints(
    status_filter: ComplaintStatus | None = Query(
        default=None,
        alias="status",
    ),
    category: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Complaint)
        .options(selectinload(Complaint.sla))
        .where(Complaint.resident_id == current_user.id)
    )

    if status_filter is not None:
        query = query.where(Complaint.status == status_filter)

    if category:
        query = query.where(
            func.upper(Complaint.category) == category.strip().upper()
        )

    complaints = db.scalars(
        query.order_by(Complaint.created_at.desc())
    ).all()

    now = datetime.utcnow()

    return [
        ComplaintResponse(
            id=c.id,
            resident_id=c.resident_id,
            category=c.category,
            description=c.description,
            photo_url=c.photo_url,
            status=c.status,
            priority=c.priority,
            created_at=c.created_at,
            updated_at=c.updated_at,
            resolved_at=c.resolved_at,
            is_overdue=_is_overdue(c, now),
        )
        for c in complaints
    ]


@router.get(
    "/{complaint_id}",
    response_model=ComplaintDetailResponse,
)
def get_my_complaint(
    complaint_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    complaint = _get_owned_complaint_or_404(
        db,
        complaint_id,
        current_user.id,
    )

    return _build_detail(db, complaint)


# ---------------------------------------------------------------------------
# Admin / committee endpoints
# ---------------------------------------------------------------------------


@admin_router.get(
    "",
    response_model=AdminComplaintListResponse,
)
def list_all_complaints(
    category: str | None = Query(default=None, max_length=100),
    complaint_status: ComplaintStatus | None = Query(
        default=None,
        alias="status",
    ),
    priority: ComplaintPriority | None = None,
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    overdue: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_committee),
):
    now = datetime.utcnow()

    overdue_condition = (
        (Complaint.status != ComplaintStatus.RESOLVED)
        & ComplaintSla.due_at.is_not(None)
        & (ComplaintSla.due_at < now)
    )

    query = (
        select(Complaint)
        .join(Complaint.resident)
        .outerjoin(Complaint.sla)
        .options(
            joinedload(Complaint.resident),
            selectinload(Complaint.sla),
        )
    )

    count_query = (
        select(func.count(Complaint.id))
        .select_from(Complaint)
        .outerjoin(Complaint.sla)
    )

    filters = []

    if category:
        filters.append(
            func.upper(Complaint.category) == category.strip().upper()
        )

    if complaint_status is not None:
        filters.append(Complaint.status == complaint_status)

    if priority is not None:
        filters.append(Complaint.priority == priority)

    if from_date is not None:
        filters.append(Complaint.created_at >= from_date)

    if to_date is not None:
        filters.append(Complaint.created_at <= to_date)

    if overdue is True:
        filters.append(overdue_condition)
    elif overdue is False:
        filters.append(~overdue_condition)

    for condition in filters:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = db.scalar(count_query) or 0

    complaints = db.scalars(
        query.order_by(
            case((overdue_condition, 0), else_=1),
            Complaint.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return AdminComplaintListResponse(
        total=total,
        items=[
            AdminComplaintResponse(
                id=c.id,
                resident_id=c.resident_id,
                category=c.category,
                description=c.description,
                photo_url=c.photo_url,
                status=c.status,
                priority=c.priority,
                created_at=c.created_at,
                updated_at=c.updated_at,
                resolved_at=c.resolved_at,
                is_overdue=_is_overdue(c, now),
                resident_name=c.resident.name,
                resident_email=c.resident.email,
            )
            for c in complaints
        ],
    )


@admin_router.get(
    "/{complaint_id}/history",
    response_model=ComplaintHistoryListResponse,
)
def get_complaint_history(
    complaint_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_committee),
):
    complaint = db.get(Complaint, complaint_id)

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )

    rows = db.scalars(
        select(ComplaintStatusHistory)
        .options(joinedload(ComplaintStatusHistory.changed_by_user))
        .where(ComplaintStatusHistory.complaint_id == complaint_id)
        .order_by(ComplaintStatusHistory.changed_at.asc())
    ).all()

    return ComplaintHistoryListResponse(
        complaint_id=complaint_id,
        items=[
            ComplaintHistoryItem(
                id=row.id,
                status=row.status,
                changed_by=row.changed_by,
                changed_by_name=(
                    row.changed_by_user.name
                    if row.changed_by_user
                    else None
                ),
                note=row.note,
                changed_at=row.changed_at,
            )
            for row in rows
        ],
    )


@admin_router.patch(
    "/{complaint_id}/priority",
    response_model=AdminComplaintResponse,
)
def update_priority(
    complaint_id: UUID,
    request: ComplaintPriorityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_committee),
):
    complaint = (
        db.query(Complaint)
        .options(joinedload(Complaint.resident))
        .filter(Complaint.id == complaint_id)
        .first()
    )

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )

    old_priority = complaint.priority

    if old_priority != request.priority:
        complaint.priority = request.priority

        db.add(
            AuditLog(
                actor_id=current_user.id,
                action="COMPLAINT_PRIORITY_CHANGED",
                entity_type="COMPLAINT",
                entity_id=complaint.id,
                old_value={"priority": old_priority.value},
                new_value={"priority": request.priority.value},
            )
        )

        db.commit()

    now = datetime.utcnow()

    return AdminComplaintResponse(
        id=complaint.id,
        resident_id=complaint.resident_id,
        category=complaint.category,
        description=complaint.description,
        photo_url=complaint.photo_url,
        status=complaint.status,
        priority=complaint.priority,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
        resolved_at=complaint.resolved_at,
        is_overdue=_is_overdue(complaint, now),
        resident_name=complaint.resident.name,
        resident_email=complaint.resident.email,
    )


@admin_router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintDetailResponse,
)
def update_status(
    complaint_id: UUID,
    request: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_committee),
):
    complaint = db.get(Complaint, complaint_id)

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )

    old_status = complaint.status

    try:
        validate_status_transition(old_status, request.status)
    except InvalidStatusTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    now = datetime.utcnow()

    complaint.status = request.status
    complaint.updated_at = now

    if request.status == ComplaintStatus.RESOLVED:
        complaint.resolved_at = now

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        status=request.status,
        changed_by=current_user.id,
        note=request.note,
        changed_at=now,
    )

    db.add(history)
    db.add(
        AuditLog(
            actor_id=current_user.id,
            action="COMPLAINT_STATUS_CHANGED",
            entity_type="COMPLAINT",
            entity_id=complaint.id,
            old_value={"status": old_status.value},
            new_value={
                "status": request.status.value,
                "note": request.note,
            },
        )
    )

    db.commit()
    db.refresh(complaint)

    # Dashboards reflect status counts; drop stale cache entries
    from app.core.cache import invalidate_prefix

    invalidate_prefix("dash:staff")
    invalidate_prefix(f"dash:resident:{complaint.resident_id}")

    # Fire-and-forget email to the resident (never blocks the response)
    resident = db.get(User, complaint.resident_id)

    if resident:
        notification_service.notify(
            db,
            user_id=resident.id,
            recipient_email=resident.email,
            event="COMPLAINT_STATUS_CHANGED",
            subject=f"Your complaint is now {request.status.value}",
            body=(
                f"Your {complaint.category} complaint "
                f"(ref {str(complaint.id)[:8]}) is now {request.status.value}."
                + (f"\nNote: {request.note}" if request.note else "")
            ),
            payload={
                "complaint_id": str(complaint.id),
                "old_status": old_status.value,
                "new_status": request.status.value,
            },
        )

    return _build_detail(db, complaint)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_owned_complaint_or_404(
    db: Session,
    complaint_id: UUID,
    resident_id: UUID,
) -> Complaint:
    complaint = (
        db.query(Complaint)
        .options(selectinload(Complaint.sla))
        .filter(
            Complaint.id == complaint_id,
            Complaint.resident_id == resident_id,
        )
        .first()
    )

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )

    return complaint


def _build_detail(
    db: Session,
    complaint: Complaint,
) -> ComplaintDetailResponse:
    complaint = (
        db.query(Complaint)
        .options(
            selectinload(Complaint.sla),
            selectinload(Complaint.history).joinedload(
                ComplaintStatusHistory.changed_by_user
            ),
        )
        .filter(Complaint.id == complaint.id)
        .first()
    )

    now = datetime.utcnow()

    return ComplaintDetailResponse(
        id=complaint.id,
        resident_id=complaint.resident_id,
        category=complaint.category,
        description=complaint.description,
        photo_url=complaint.photo_url,
        status=complaint.status,
        priority=complaint.priority,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
        resolved_at=complaint.resolved_at,
        is_overdue=_is_overdue(complaint, now),
        history=[
            ComplaintHistoryItem(
                id=h.id,
                status=h.status,
                changed_by=h.changed_by,
                changed_by_name=(
                    h.changed_by_user.name if h.changed_by_user else None
                ),
                note=h.note,
                changed_at=h.changed_at,
            )
            for h in sorted(
                complaint.history,
                key=lambda x: x.changed_at,
            )
        ],
    )
