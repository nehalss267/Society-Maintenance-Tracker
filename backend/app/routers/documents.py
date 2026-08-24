import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.complaint import Complaint
from app.models.document import Document, DocumentEntity
from app.models.expense import Expense
from app.models.invoice import Invoice
from app.models.user import User, UserRole
from app.schemas.document import DocumentResponse
from app.services.audit_service import record_audit
from app.services.storage_service import (
    StorageValidationError,
    resolve_local_path,
    save_document,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)

STAFF_ROLES = {UserRole.COMMITTEE, UserRole.ACCOUNTANT, UserRole.ADMIN}


class DocumentAccessError(Exception):
    pass


def _resolve_owner_id(
    db: Session,
    entity_type: DocumentEntity,
    entity_id: uuid.UUID,
) -> uuid.UUID | None:
    """Resident-owner of the entity (None for staff-only entities)."""
    if entity_type == DocumentEntity.COMPLAINT:
        complaint = db.get(Complaint, entity_id)

        return complaint.resident_id if complaint else None

    if entity_type == DocumentEntity.INVOICE:
        invoice = db.get(Invoice, entity_id)

        return invoice.resident_id if invoice else None

    expense = db.get(Expense, entity_id)

    return expense.created_by if expense else None


def _ensure_entity_exists(
    db: Session,
    entity_type: DocumentEntity,
    entity_id: uuid.UUID,
) -> None:
    model = {
        DocumentEntity.COMPLAINT: Complaint,
        DocumentEntity.INVOICE: Invoice,
        DocumentEntity.EXPENSE: Expense,
    }[entity_type]

    if not db.get(model, entity_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target entity does not exist",
        )


def _authorize_read(
    db: Session,
    user: User,
    doc: Document,
) -> None:
    """Owner-or-staff visibility; expenses are staff-only material."""
    owner_id = _resolve_owner_id(db, doc.entity_type, doc.entity_id)

    if doc.entity_type == DocumentEntity.EXPENSE:
        allowed = user.role in {UserRole.ACCOUNTANT, UserRole.ADMIN}
    else:
        allowed = (
            user.role in STAFF_ROLES or owner_id == user.id
        )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )


def _authorize_upload(
    db: Session,
    user: User,
    entity_type: DocumentEntity,
    entity_id: uuid.UUID,
) -> None:
    """Uploads are stricter than reads:
    - COMPLAINT: the resident owner or staff may attach evidence.
    - INVOICE / EXPENSE: accountant/admin only (association material).
    """
    if entity_type == DocumentEntity.COMPLAINT:
        owner_id = _resolve_owner_id(db, entity_type, entity_id)
        allowed = user.role in STAFF_ROLES or owner_id == user.id
    else:
        allowed = user.role in {UserRole.ACCOUNTANT, UserRole.ADMIN}

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )


@router.get("/download/{document_id}")
def download_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.get(Document, document_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    _authorize_read(db, current_user, doc)

    local_path = resolve_local_path(doc.file_url)

    if local_path:
        if not local_path.exists():
            logger.error("Document row %s points at missing file", doc.id)

            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Stored file is missing",
            )

        return FileResponse(
            local_path,
            filename=doc.original_filename,
            media_type=doc.content_type,
        )

    from fastapi.responses import RedirectResponse

    return RedirectResponse(doc.file_url)


@router.post(
    "/{entity_type}/{entity_id}",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    entity_type: DocumentEntity,
    entity_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_entity_exists(db, entity_type, entity_id)
    _authorize_upload(db, current_user, entity_type, entity_id)

    data = await file.read()

    try:
        url = save_document(data=data, filename=file.filename or "attachment")
    except StorageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    doc = Document(
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by=current_user.id,
        file_url=url,
        original_filename=(file.filename or "attachment")[:255],
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
    )

    db.add(doc)
    record_audit(
        db,
        actor_id=current_user.id,
        action="DOCUMENT_UPLOADED",
        entity_type="DOCUMENT",
        entity_id=doc.id,
        new_value={
            "target": f"{entity_type.value}:{str(entity_id)[:8]}",
            "filename": doc.original_filename,
            "size": doc.size_bytes,
        },
    )
    db.commit()
    db.refresh(doc)

    return [_to_response(doc)]


@router.get("/{entity_type}/{entity_id}", response_model=list[DocumentResponse])
def list_documents(
    entity_type: DocumentEntity,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_entity_exists(db, entity_type, entity_id)

    probe = Document(entity_type=entity_type, entity_id=entity_id)
    _authorize_read(db, current_user, probe)

    docs = db.scalars(
        select(Document)
        .where(Document.entity_type == entity_type, Document.entity_id == entity_id)
        .order_by(Document.created_at.desc())
    ).all()

    return [_to_response(d) for d in docs]


def _to_response(d: Document) -> DocumentResponse:
    return DocumentResponse(
        id=d.id,
        entity_type=d.entity_type,
        entity_id=d.entity_id,
        file_url=d.file_url,
        original_filename=d.original_filename,
        content_type=d.content_type,
        size_bytes=d.size_bytes,
        created_at=d.created_at,
    )
