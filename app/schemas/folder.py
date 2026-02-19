"""Folder schemas — CRUD and folder items."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class FolderCreate(BaseModel):
    """Create a new folder."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    color: str | None = Field(None, max_length=7)


class FolderUpdate(BaseModel):
    """Update folder metadata."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    color: str | None = Field(None, max_length=7)


class FolderRead(BaseModel):
    """Folder with item counts."""

    id: UUID
    name: str
    description: str | None
    color: str | None
    item_counts: dict[str, int] = Field(default_factory=lambda: {"conversation": 0, "document": 0, "email_thread": 0})
    created_at: datetime
    updated_at: datetime


class FolderItemAdd(BaseModel):
    """Add an item to a folder."""

    item_type: Literal["conversation", "document", "email_thread"]
    item_id: str = Field(..., min_length=1, max_length=255)


class FolderItemRead(BaseModel):
    """Folder item with enriched metadata."""

    id: UUID
    item_type: Literal["conversation", "document", "email_thread"]
    item_id: str
    title: str
    subtitle: str | None = None
    date: datetime
    added_at: datetime
