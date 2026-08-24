import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import UserRole


class NoticeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=5, max_length=10000)
    is_important: bool = False


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    content: str | None = Field(
        default=None,
        min_length=5,
        max_length=10000,
    )
    is_important: bool | None = None


class NoticeResponse(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    is_important: bool
    created_by: uuid.UUID
    created_by_name: str | None = None
    created_at: datetime


class NoticeListResponse(BaseModel):
    total: int
    items: list[NoticeResponse]
