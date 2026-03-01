"""Upload document schemas with rich metadata."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UploadStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"


class UploadDocumentRead(BaseModel):
    """Rich read schema for uploaded documents."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID
    filename: str
    content_type: str
    file_size: int
    content_hash: str
    status: UploadStatus
    error_message: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    tokens_used: int | None = None

    # Rich metadata from doc_metadata JSONB
    source: str = "uploads"
    ocr_used: bool = False
    parser_used: str = "native"

    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None

    @classmethod
    def from_document(cls, doc) -> "UploadDocumentRead":
        """Build from a Document ORM instance, extracting doc_metadata fields."""
        meta = doc.doc_metadata or {}
        return cls(
            id=doc.id,
            collection_id=doc.collection_id,
            filename=doc.filename,
            content_type=doc.content_type,
            file_size=doc.file_size,
            content_hash=doc.content_hash,
            status=UploadStatus(doc.status),
            error_message=doc.error_message,
            page_count=doc.page_count,
            chunk_count=doc.chunk_count,
            tokens_used=doc.tokens_used,
            source=meta.get("source", "uploads"),
            ocr_used=meta.get("ocr_used", False),
            parser_used=meta.get("parser_used", "native"),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            processed_at=doc.processed_at,
        )


class UploadPageRead(BaseModel):
    """Schema for a single document page (extracted text)."""

    model_config = ConfigDict(from_attributes=True)

    page_number: int
    text: str
    meta: dict | None = None


class UploadDocumentDetail(UploadDocumentRead):
    """Document detail with pages included."""

    pages: list[UploadPageRead] = []


class UploadDownloadUrlResponse(BaseModel):
    """Presigned download URL response."""

    url: str
    filename: str
    content_type: str
    expires_in: int = 3600
