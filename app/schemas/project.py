"""Project schemas (private user workspaces with RAG)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class ProjectReadWithStats(ProjectRead):
    documents_count: int = 0
    conversations_count: int = 0
    knowledge_count: int = 0


class ProjectDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    filename: str
    content_type: str
    file_size: int
    status: str
    error_message: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    tokens_used: int | None = None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None


class ProjectDocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    message: str = "Document queued for processing"


class ProjectKnowledgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    source_conversation_id: UUID | None = None
    title: str | None = None
    summary_text: str
    chunk_count: int | None = None
    created_at: datetime


class ProjectChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None
    include_history: bool = True
    max_history_messages: int = 20


class ProjectSummarizeRequest(BaseModel):
    conversation_id: UUID
