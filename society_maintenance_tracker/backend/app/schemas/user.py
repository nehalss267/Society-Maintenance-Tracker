import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class RoleUpdateRequest(BaseModel):
    role: UserRole


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class UserListResponse(BaseModel):
    total: int
    items: list[AdminUserResponse]
