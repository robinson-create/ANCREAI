"""Observability schemas (audit log, LLM trace)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ── Audit Log ────────────────────────────────────────────────────────

class AuditLogCreate(BaseModel):
    tenant_id: UUID | None = None
    run_id: UUID | None = None
    user_id: UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    detail: dict | None = None
    level: str = "info"
    message: str | None = None


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None = None
    run_id: UUID | None = None
    user_id: UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    detail: dict | None = None
    level: str
    message: str | None = None
    created_at: datetime


# ── LLM Trace ────────────────────────────────────────────────────────

class LLMTraceCreate(BaseModel):
    tenant_id: UUID | None = None
    run_id: UUID | None = None
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int | None = None
    status: str = "success"
    error_message: str | None = None
    request_metadata: dict | None = None


class LLMTraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None = None
    run_id: UUID | None = None
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int | None = None
    status: str
    error_message: str | None = None
    request_metadata: dict | None = None
    created_at: datetime
