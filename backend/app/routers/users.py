from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_admin
from app.models.user import User, UserRole
from app.schemas.user import (
    AdminUserResponse,
    RoleUpdateRequest,
    UserListResponse,
)
from app.services.audit_service import record_audit


router = APIRouter(
    prefix="/api/admin/users",
    tags=["Admin · Users"],
)


@router.get(
    "",
    response_model=UserListResponse,
)
def list_users(
    role: UserRole | None = None,
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):

    query = select(User)

    if role is not None:
        query = query.where(User.role == role)

    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower(User.name).like(pattern)
            | func.lower(User.email).like(pattern)
        )

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    )

    users = db.scalars(
        query.order_by(User.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return UserListResponse(
        total=total or 0,
        items=users,
    )


@router.patch(
    "/{user_id}/role",
    response_model=AdminUserResponse,
)
def change_user_role(
    user_id: UUID,
    request: RoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot change their own role",
        )

    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    old_role = user.role

    if old_role == request.role:
        return user

    user.role = request.role

    record_audit(
        db,
        actor_id=current_user.id,
        action="USER_ROLE_CHANGED",
        entity_type="USER",
        entity_id=user.id,
        old_value={"role": old_role.value},
        new_value={"role": request.role.value},
    )

    db.commit()
    db.refresh(user)

    return user
