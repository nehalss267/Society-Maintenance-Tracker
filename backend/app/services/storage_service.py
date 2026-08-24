import logging
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class StorageError(Exception):
    pass


class StorageValidationError(StorageError):
    pass


ALLOWED_RECEIPT_TYPES = {
    **ALLOWED_IMAGE_TYPES,
    "application/pdf": ".pdf",
}


IMAGE_MAGIC = (
    (b"\xff\xd8", ".jpg"),
    (b"\x89PNG", ".png"),
)


def _sniff_image_extension(head: bytes) -> str | None:
    """Return canonical extension from file magic bytes, or None."""
    for magic, ext in IMAGE_MAGIC:
        if head.startswith(magic):
            return ext

    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return ".webp"

    return None


def validate_image(upload: UploadFile) -> str:
    """Validate content type, size and magic bytes; returns the extension."""
    extension = ALLOWED_IMAGE_TYPES.get(upload.content_type or "")

    if not extension:
        raise StorageError(
            "Unsupported file type. Allowed: JPEG, PNG, WEBP."
        )

    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)

    if size == 0:
        raise StorageError("Uploaded file is empty.")

    if size > settings.UPLOAD_MAX_BYTES:
        raise StorageError("File too large. Max 5 MB.")

    head = upload.file.read(12)
    upload.file.seek(0)

    if _sniff_image_extension(head) != extension:
        raise StorageError(
            "File content does not match its declared image type."
        )

    return extension


def _save_local(upload: UploadFile, folder: str, extension: str) -> str:
    target_dir = UPLOAD_ROOT / folder
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{extension}"
    target_path = target_dir / filename

    with open(target_path, "wb") as buffer:
        while chunk := upload.file.read(1024 * 1024):
            buffer.write(chunk)

    return f"/uploads/{folder}/{filename}"


def _save_cloudinary(upload: UploadFile, folder: str) -> str:
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )

    result = cloudinary.uploader.upload(
        upload.file,
        folder=f"smt/{folder}",
        resource_type="image",
    )

    return result["secure_url"]


async def save_complaint_photo(upload: UploadFile | None) -> str | None:
    """Persist an uploaded image; returns a URL (or None when no file given).

    STORAGE_BACKEND=cloudinary is used only when credentials are present,
    otherwise the request degrades to local disk storage.
    """
    if upload is None or not upload.filename:
        return None

    extension = validate_image(upload)

    use_cloudinary = (
        settings.STORAGE_BACKEND == "cloudinary"
        and settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_SECRET
    )

    try:
        if use_cloudinary:
            url = _save_cloudinary(upload, "complaints")
        else:
            url = _save_local(upload, "complaints", extension)
    except StorageError:
        raise
    except Exception:
        logger.exception("Photo upload failed")
        raise StorageError("Failed to store the uploaded photo.")

    return url


def resolve_photo_url(url: str | None) -> str | None:
    """Pass through external URLs; local /uploads paths are served as-is."""
    return url


# ---------------------------------------------------------------------------
# Receipts (images + PDF)
# ---------------------------------------------------------------------------


def _sniff_receipt_extension(data: bytes, filename: str) -> str:
    """Detect type via magic bytes, falling back to the filename extension."""
    if data.startswith(b"%PDF"):
        return ".pdf"

    if data.startswith(b"\xff\xd8"):
        return ".jpg"

    if data.startswith(b"\x89PNG"):
        return ".png"

    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"

    import mimetypes

    guessed, _ = mimetypes.guess_type(filename)

    if guessed in ALLOWED_RECEIPT_TYPES:
        return ALLOWED_RECEIPT_TYPES[guessed]

    raise StorageValidationError(
        "Unsupported receipt type. Allowed: JPEG, PNG, WEBP, PDF."
    )


def save_receipt(*, data: bytes, filename: str) -> str:
    if not data:
        raise StorageValidationError("Uploaded file is empty.")

    if len(data) > settings.UPLOAD_MAX_BYTES:
        raise StorageValidationError("File too large. Max 5 MB.")

    extension = _sniff_receipt_extension(data, filename)

    target_dir = UPLOAD_ROOT / "receipts"
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{extension}"

    with open(target_dir / stored_name, "wb") as buffer:
        buffer.write(data)

    return f"/uploads/receipts/{stored_name}"


def save_document(*, data: bytes, filename: str, folder: str = "documents") -> str:
    """Generic attachment storage (images + PDF), local or cloudinary."""
    if not data:
        raise StorageValidationError("Uploaded file is empty.")

    if len(data) > settings.UPLOAD_MAX_BYTES:
        raise StorageValidationError("File too large. Max 5 MB.")

    extension = _sniff_receipt_extension(data, filename)

    use_cloudinary = (
        settings.STORAGE_BACKEND == "cloudinary"
        and settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_SECRET
    )

    if use_cloudinary:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
        )

        import io

        result = cloudinary.uploader.upload(
            io.BytesIO(data),
            folder=f"smt/{folder}",
            resource_type="raw",
        )

        return result["secure_url"]

    target_dir = UPLOAD_ROOT / folder
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{extension}"

    with open(target_dir / stored_name, "wb") as buffer:
        buffer.write(data)

    return f"/uploads/{folder}/{stored_name}"


def resolve_local_path(file_url: str):
    """Map a local /uploads URL to a filesystem Path (None when external).

    Defense-in-depth: the resolved path must stay inside UPLOAD_ROOT so a
    crafted file_url can never escape the uploads directory.
    """
    if not file_url.startswith("/uploads/"):
        return None

    root = UPLOAD_ROOT.resolve()
    candidate = (UPLOAD_ROOT / file_url.removeprefix("/uploads/")).resolve()

    if candidate != root and root not in candidate.parents:
        return None

    return candidate
