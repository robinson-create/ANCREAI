"""SQLAlchemy models package."""

from app.models.tenant import Tenant
from app.models.assistant import Assistant
from app.models.collection import Collection, assistant_collections
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.document_page import DocumentPage
from app.models.message import Message
from app.models.usage import Usage
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.daily_usage import DailyUsage
from app.integrations.nango.models import NangoConnection, assistant_integrations
from app.models.workspace_document import WorkspaceDocument, WorkspaceDocStatus
from app.models.document_template import DocumentTemplate
from app.models.mail import MailAccount, MailMessage, MailSyncState, MailSendRequest
from app.models.web_source import WebSource

__all__ = [
    "Tenant",
    "Assistant",
    "Collection",
    "assistant_collections",
    "Document",
    "Chunk",
    "DocumentPage",
    "Message",
    "Usage",
    "User",
    "Subscription",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "DailyUsage",
    "NangoConnection",
    "assistant_integrations",
    "WorkspaceDocument",
    "WorkspaceDocStatus",
    "DocumentTemplate",
    "MailAccount",
    "MailMessage",
    "MailSyncState",
    "MailSendRequest",
    "WebSource",
]
