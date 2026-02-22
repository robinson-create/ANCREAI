"""Memory schemas (user memory, assistant memory, conversation context)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── User Memory ──────────────────────────────────────────────────────

class UserMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    raw_json: dict
    compressed_text: str | None = None
    compressed_token_count: int = 0
    created_at: datetime
    updated_at: datetime


class UserMemoryUpdate(BaseModel):
    raw_json: dict | None = None


# ── Assistant Memory ─────────────────────────────────────────────────

class AssistantMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    assistant_id: UUID
    raw_json: dict
    compressed_text: str | None = None
    compressed_token_count: int = 0
    created_at: datetime
    updated_at: datetime


class AssistantMemoryUpdate(BaseModel):
    raw_json: dict | None = None


# ── Conversation Context ─────────────────────────────────────────────

class ConversationContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    conversation_id: UUID
    assistant_id: UUID
    summary_text: str | None = None
    constraints: list | None = None
    decisions: list | None = None
    open_questions: list | None = None
    facts: list | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationContextUpdate(BaseModel):
    summary_text: str | None = None
    constraints: list | None = None
    decisions: list | None = None
    open_questions: list | None = None
    facts: list | None = None


# ── Fact schema (for typed access) ───────────────────────────────────

class Fact(BaseModel):
    key: str
    value: str
    source: str = "user"  # user | rag | inferred
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    last_seen_at: datetime | None = None
