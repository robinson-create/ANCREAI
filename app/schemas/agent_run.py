"""Agent run schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentRunCreate(BaseModel):
    assistant_id: UUID
    conversation_id: UUID
    input_text: str
    profile: str = "reactive"
    budget_tokens: int | None = None


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    assistant_id: UUID
    conversation_id: UUID
    profile: str
    status: str
    input_text: str
    output_text: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    tool_rounds: int = 0
    budget_tokens: int | None = None
    budget_tokens_remaining: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class AgentRunStatusUpdate(BaseModel):
    """Partial update for run lifecycle transitions."""
    status: str
    output_text: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    tool_rounds: int | None = None
    budget_tokens_remaining: int | None = None
    error_code: str | None = None
    error_message: str | None = None
