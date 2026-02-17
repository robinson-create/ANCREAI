"""Document schemas."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentCreate(BaseModel):
    """Schema for creating a document (metadata only, file via multipart)."""

    doc_metadata: dict | None = None


class DocumentRead(BaseModel):
    """Schema for reading a document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID
    filename: str
    content_type: str
    file_size: int
    content_hash: str
    status: DocumentStatus
    error_message: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    tokens_used: int | None = None
    doc_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""

    id: UUID
    filename: str
    status: DocumentStatus
    message: str = "Document queued for processing"
