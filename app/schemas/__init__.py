"""Pydantic schemas for API request/response validation."""

from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate
from app.schemas.assistant import AssistantCreate, AssistantRead, AssistantUpdate
from app.schemas.collection import CollectionCreate, CollectionRead, CollectionUpdate
from app.schemas.document import DocumentCreate, DocumentRead, DocumentStatus
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.schemas.usage import UsageRead
from app.schemas.mail import (
    MailAccountRead,
    MailAccountConnectResponse,
    MailMessageBrief,
    MailMessageRead,
    MailThreadSummary,
    MailThreadRead,
    MailSendRequestCreate,
    MailSendResponse,
    MailSendStatusRead,
)
from app.schemas.memory import (
    UserMemoryRead,
    UserMemoryUpdate,
    AssistantMemoryRead,
    AssistantMemoryUpdate,
    ConversationContextRead,
    ConversationContextUpdate,
    Fact,
)
from app.schemas.agent_run import AgentRunCreate, AgentRunRead, AgentRunStatusUpdate
from app.schemas.observability import (
    AuditLogCreate,
    AuditLogRead,
    LLMTraceCreate,
    LLMTraceRead,
)

__all__ = [
    "TenantCreate",
    "TenantRead",
    "TenantUpdate",
    "AssistantCreate",
    "AssistantRead",
    "AssistantUpdate",
    "CollectionCreate",
    "CollectionRead",
    "CollectionUpdate",
    "DocumentCreate",
    "DocumentRead",
    "DocumentStatus",
    "ChatRequest",
    "ChatResponse",
    "Citation",
    "UsageRead",
    "MailAccountRead",
    "MailAccountConnectResponse",
    "MailMessageBrief",
    "MailMessageRead",
    "MailThreadSummary",
    "MailThreadRead",
    "MailSendRequestCreate",
    "MailSendResponse",
    "MailSendStatusRead",
    "UserMemoryRead",
    "UserMemoryUpdate",
    "AssistantMemoryRead",
    "AssistantMemoryUpdate",
    "ConversationContextRead",
    "ConversationContextUpdate",
    "Fact",
    "AgentRunCreate",
    "AgentRunRead",
    "AgentRunStatusUpdate",
    "AuditLogCreate",
    "AuditLogRead",
    "LLMTraceCreate",
    "LLMTraceRead",
]
