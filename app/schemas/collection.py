"""Collection schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CollectionBase(BaseModel):
    """Base collection schema."""

    name: str
    description: str | None = None


class CollectionCreate(CollectionBase):
    """Schema for creating a collection."""

    pass


class CollectionUpdate(BaseModel):
    """Schema for updating a collection."""

    name: str | None = None
    description: str | None = None


class CollectionRead(CollectionBase):
    """Schema for reading a collection."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


class CollectionReadWithStats(CollectionRead):
    """Schema for reading a collection with document stats."""

    documents_count: int = 0
    total_chunks: int = 0
