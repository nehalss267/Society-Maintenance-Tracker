import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.document import DocumentEntity


class DocumentResponse(BaseModel):
    id: uuid.UUID
    entity_type: DocumentEntity
    entity_id: uuid.UUID
    file_url: str
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
