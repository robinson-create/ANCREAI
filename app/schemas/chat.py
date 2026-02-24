"""Chat schemas."""

from uuid import UUID

from pydantic import BaseModel


class Citation(BaseModel):
    """Citation from a document chunk."""

    chunk_id: UUID
    document_id: UUID
    document_filename: str
    page_number: int | None = None
    excerpt: str
    score: float


class ChatRequest(BaseModel):
    """Chat request schema."""

    message: str
    conversation_id: UUID | None = None
    include_history: bool = True
    max_history_messages: int = 10
    context_hint: str | None = None  # Optional hint about the UI context (e.g. "email")


class BlockData(BaseModel):
    """A generative UI block produced by a tool call."""

    id: str
    type: str  # "kpi_cards" | "steps" | "table" | "callout" | "error"
    payload: dict


class ChatResponse(BaseModel):
    """Chat response schema (non-streaming)."""

    message: str
    conversation_id: UUID
    citations: list[Citation] = []
    blocks: list[BlockData] = []
    tokens_input: int
    tokens_output: int


class ChatStreamEvent(BaseModel):
    """SSE event for streaming chat."""

    event: str  # "start", "token", "block", "citations", "done", "error"
    data: str | list[Citation] | dict | None = None
