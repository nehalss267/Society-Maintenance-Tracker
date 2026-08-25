import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.dependencies.auth import get_current_user
from app.integrations import resend_client
from app.models.audit_log import AuditLog
from app.models.password_reset import PasswordResetToken
from app.models.user import User, UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)

from app.core.config import settings


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

RESET_TOKEN_TTL_MINUTES = 30


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):

    existing_user = db.scalar(
        select(User).where(
            User.email == request.email
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        name=request.name,
        email=request.email,
        password_hash=hash_password(request.password),
        role=UserRole.RESIDENT,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):

    user = db.scalar(
        select(User).where(
            User.email == request.email
        )
    )

    if not user or not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        str(user.id)
    )

    return TokenResponse(
        access_token=token,
        user=user,
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------


def _token_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _issue_reset_token(db: Session, user: User) -> None:
    """Invalidate outstanding tokens, then create + email a fresh one."""
    now = datetime.utcnow()

    for row in db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    ).all():
        row.used_at = now

    raw_token = secrets.token_urlsafe(32)

    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_token_digest(raw_token),
            expires_at=now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
            created_at=now,
        )
    )
    db.commit()

    reset_link = (
        f"{settings.FRONTEND_URL.rstrip('/')}"
        f"/reset-password?token={raw_token}"
    )

    try:
        resend_client.send_email(
            to=user.email,
            subject="Reset your password",
            text=(
                "We received a request to reset your password.\n\n"
                f"Open this link within {RESET_TOKEN_TTL_MINUTES} minutes:\n"
                f"{reset_link}\n\n"
                "If you didn't request this, you can ignore this email."
            ),
        )
    except Exception:
        # Never leak delivery failures to the caller (no user enumeration,
        # no 500 on provider outage) - the token stays valid until expiry.
        import logging

        logging.getLogger(__name__).exception(
            "Reset email delivery failed for %s", user.email
        )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == request.email))

    if user:
        _issue_reset_token(db, user)

    return MessageResponse(
        message=(
            "If that email is registered, a reset link has been sent. "
            "It expires in 30 minutes."
        )
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
)
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()

    row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _token_digest(request.token)
        )
    )

    if not row or row.used_at is not None or row.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link.",
        )

    user = db.get(User, row.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link.",
        )

    user.password_hash = hash_password(request.new_password)
    row.used_at = now

    db.add(
        AuditLog(
            actor_id=user.id,
            action="PASSWORD_RESET_COMPLETED",
            entity_type="USER",
            entity_id=user.id,
            old_value=None,
            new_value=None,
        )
    )

    db.commit()

    return MessageResponse(message="Password updated. You can sign in now.")


@router.patch(
    "/change-password",
    response_model=MessageResponse,
)
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(
        request.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.password_hash = hash_password(request.new_password)

    db.add(
        AuditLog(
            actor_id=current_user.id,
            action="PASSWORD_CHANGED",
            entity_type="USER",
            entity_id=current_user.id,
            old_value=None,
            new_value=None,
        )
    )

    db.commit()

    return MessageResponse(message="Password changed.")