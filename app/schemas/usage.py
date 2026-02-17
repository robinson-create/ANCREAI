"""Usage schemas."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsageRead(BaseModel):
    """Schema for reading usage stats."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    period: date
    ingestion_tokens: int
    chat_input_tokens: int
    chat_output_tokens: int
    storage_bytes: int
    documents_count: int
    messages_count: int


class UsageSummary(BaseModel):
    """Summary of current period usage vs limits."""

    period: date
    
    # Current usage
    ingestion_tokens_used: int
    chat_tokens_used: int  # input + output
    storage_bytes_used: int
    
    # Limits
    max_ingestion_tokens: int
    max_chat_tokens: int
    max_storage_bytes: int
    
    # Percentages
    ingestion_percent: float
    chat_percent: float
    storage_percent: float


class QuotaExceededError(BaseModel):
    """Error response when quota is exceeded."""

    detail: str
    quota_type: str  # "ingestion", "chat", "storage"
    current: int
    limit: int
