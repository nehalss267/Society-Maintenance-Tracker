import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.complaint import ComplaintPriority, ComplaintStatus
from app.models.user import UserRole


class ComplaintCreate(BaseModel):
    category: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=5000)


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    note: str | None = Field(default=None, max_length=1000)


class ComplaintPriorityUpdate(BaseModel):
    priority: ComplaintPriority


class ComplaintHistoryItem(BaseModel):
    id: uuid.UUID
    status: ComplaintStatus
    changed_by: uuid.UUID
    changed_by_name: str | None = None
    note: str | None
    changed_at: datetime

    model_config = {
        "from_attributes": True,
    }


class ComplaintResponse(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    category: str
    description: str
    photo_url: str | None
    status: ComplaintStatus
    priority: ComplaintPriority
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    is_overdue: bool


class ComplaintDetailResponse(ComplaintResponse):
    history: list[ComplaintHistoryItem]


class AdminComplaintResponse(ComplaintResponse):
    resident_name: str | None = None
    resident_email: str | None = None


class AdminComplaintListResponse(BaseModel):
    total: int
    items: list[AdminComplaintResponse]


class ComplaintHistoryListResponse(BaseModel):
    complaint_id: uuid.UUID
    items: list[ComplaintHistoryItem]
