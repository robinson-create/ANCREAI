"""Assistant schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssistantBase(BaseModel):
    """Base assistant schema."""

    name: str
    system_prompt: str | None = None
    model: str = "mistral-medium-latest"
    agent_profile: str = "reactive"
    settings: dict | None = None


class AssistantCreate(AssistantBase):
    """Schema for creating an assistant."""

    collection_ids: list[UUID] | None = None
    integration_ids: list[UUID] | None = None


class AssistantUpdate(BaseModel):
    """Schema for updating an assistant."""

    name: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    agent_profile: str | None = None
    settings: dict | None = None
    collection_ids: list[UUID] | None = None
    integration_ids: list[UUID] | None = None


class AssistantRead(AssistantBase):
    """Schema for reading an assistant."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


class AssistantReadWithCollections(AssistantRead):
    """Schema for reading an assistant with collections and integrations."""

    collection_ids: list[UUID] = []
    integration_ids: list[UUID] = []
