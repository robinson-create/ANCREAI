"""Dossier schemas (personal workspaces)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DossierCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None


class DossierUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class DossierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    name: str
    description: str | None = None
    color: str | None = None
    created_at: datetime
    updated_at: datetime


class DossierReadWithStats(DossierRead):
    documents_count: int = 0
    conversations_count: int = 0


class DossierDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dossier_id: UUID
    filename: str
    content_type: str
    file_size: int
    status: str
    error_message: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    created_at: datetime
    updated_at: datetime


class DossierDocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    message: str = "Document queued for processing"
