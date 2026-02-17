"""Tenant schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantBase(BaseModel):
    """Base tenant schema."""

    name: str
    settings: dict | None = None


class TenantCreate(TenantBase):
    """Schema for creating a tenant."""

    max_assistants: int = 3
    max_ingestion_tokens: int = 1_000_000
    max_chat_tokens: int = 500_000
    max_storage_bytes: int = 1_073_741_824


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""

    name: str | None = None
    settings: dict | None = None
    max_assistants: int | None = None
    max_ingestion_tokens: int | None = None
    max_chat_tokens: int | None = None
    max_storage_bytes: int | None = None


class TenantRead(TenantBase):
    """Schema for reading a tenant."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    max_assistants: int
    max_ingestion_tokens: int
    max_chat_tokens: int
    max_storage_bytes: int
    created_at: datetime
    updated_at: datetime
