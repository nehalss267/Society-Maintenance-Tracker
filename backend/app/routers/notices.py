from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_committee
from app.models.notice import Notice
from app.models.user import User, UserRole
from app.schemas.notice import (
    NoticeCreate,
    NoticeListResponse,
    NoticeResponse,
    NoticeUpdate,
)
from app.services import notification_service
from app.services.audit_service import record_audit


router = APIRouter(
    prefix="/api/notices",
    tags=["Notices"],
)

admin_router = APIRouter(
    prefix="/api/admin/notices",
    tags=["Admin · Notices"],
)


def _to_response(notice: Notice) -> NoticeResponse:
    return NoticeResponse(
        id=notice.id,
        title=notice.title,
        content=notice.content,
        is_important=notice.is_important,
        created_by=notice.created_by,
        created_by_name=(
            notice.creator.name if notice.creator else None
        ),
        created_at=notice.created_at,
    )


@router.get(
    "",
    response_model=NoticeListResponse,
)
def list_notices(
    important_first: bool = True,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    base = select(Notice).join(Notice.creator)

    count_query = select(func.count(Notice.id)).select_from(Notice)

    total = db.scalar(count_query) or 0

    query = base.options(joinedload(Notice.creator))

    if important_first:
        query = query.order_by(
            Notice.is_important.desc(),
            Notice.created_at.desc(),
        )
    else:
        query = query.order_by(Notice.created_at.desc())

    notices = db.scalars(query.limit(limit).offset(offset)).all()

    return NoticeListResponse(
        total=total,
        items=[_to_response(n) for n in notices],
    )


@router.get(
    "/{notice_id}",
    response_model=NoticeResponse,
)
def get_notice(
    notice_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    notice = db.get(Notice, notice_id)

    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    return _to_response(notice)


@admin_router.post(
    "",
    response_model=NoticeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notice(
    request: NoticeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_committee),
):
    notice = Notice(
        title=request.title.strip(),
        content=request.content.strip(),
        is_important=request.is_important,
        created_by=current_user.id,
    )

    db.add(notice)
    db.flush()

    record_audit(
        db,
        actor_id=current_user.id,
        action="NOTICE_CREATED",
        entity_type="NOTICE",
        entity_id=notice.id,
        new_value={
            "title": notice.title,
            "is_important": notice.is_important,
        },
    )

    db.commit()
    db.refresh(notice)

    # Important notices fan out to every resident via email
    if notice.is_important:
        residents = db.scalars(
            select(User).where(User.role == UserRole.RESIDENT)
        ).all()

        for resident in residents:
            notification_service.notify(
                db,
                user_id=resident.id,
                recipient_email=resident.email,
                event="IMPORTANT_NOTICE_POSTED",
                subject=f"Important notice: {notice.title}",
                body=notice.content[:1500],
                payload={"notice_id": str(notice.id)},
            )

    return _to_response(notice)


@admin_router.patch(
    "/{notice_id}",
    response_model=NoticeResponse,
)
def update_notice(
    notice_id: UUID,
    request: NoticeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_committee),
):
    notice = db.get(Notice, notice_id)

    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    old_value = {
        "title": notice.title,
        "content": notice.content,
        "is_important": notice.is_important,
    }

    changed = False

    if request.title is not None and request.title != notice.title:
        notice.title = request.title.strip()
        changed = True

    if request.content is not None and request.content != notice.content:
        notice.content = request.content.strip()
        changed = True

    if (
        request.is_important is not None
        and request.is_important != notice.is_important
    ):
        notice.is_important = request.is_important
        changed = True

    if changed:
        record_audit(
            db,
            actor_id=current_user.id,
            action="NOTICE_UPDATED",
            entity_type="NOTICE",
            entity_id=notice.id,
            old_value=old_value,
            new_value={
                "title": notice.title,
                "content": notice.content,
                "is_important": notice.is_important,
            },
        )

        db.commit()
        db.refresh(notice)

    return _to_response(notice)


@admin_router.delete(
    "/{notice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_notice(
    notice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_committee),
):
    notice = db.get(Notice, notice_id)

    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    record_audit(
        db,
        actor_id=current_user.id,
        action="NOTICE_DELETED",
        entity_type="NOTICE",
        entity_id=notice.id,
        old_value={"title": notice.title},
    )

    db.delete(notice)
    db.commit()
