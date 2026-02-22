"""Pydantic schemas for the mail integration."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ── Mail Account ──


class MailAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    provider: str
    email_address: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class MailAccountConnectResponse(BaseModel):
    account_id: UUID
    connect_url: str
    provider: str


class MailAccountSmtpConnectRequest(BaseModel):
    """Credentials for SMTP connection (Gmail, Outlook, or custom)."""

    host: str
    port: int = 587
    user: str
    password: str
    use_tls: bool = True
    email_address: str | None = None  # Display email; default to user


# ── Mail Message ──


class MailMessageBrief(BaseModel):
    """Lightweight message for thread listings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_message_id: str
    provider_thread_id: str | None = None
    sender: dict
    to_recipients: list[dict]
    subject: str | None = None
    date: datetime
    snippet: str | None = None
    is_read: bool = False
    is_sent: bool = False
    has_attachments: bool = False


class MailMessageRead(MailMessageBrief):
    """Full message with body."""

    cc_recipients: list[dict] | None = None
    bcc_recipients: list[dict] | None = None
    body_text: str | None = None
    body_html: str | None = None
    internet_message_id: str | None = None
    raw_headers: dict | None = None
    is_draft: bool = False
    created_at: datetime
    updated_at: datetime


# ── Contacts ──


class MailContactSummary(BaseModel):
    """Contact summary grouped by sender/recipient."""

    email: str
    name: str | None = None
    total_threads: int
    unread_count: int
    last_date: datetime


# ── Threads ──


class MailThreadSummary(BaseModel):
    """Thread summary for listing."""

    thread_key: str
    subject: str | None = None
    last_date: datetime
    snippet: str | None = None
    message_count: int
    participants: list[dict]
    has_unread: bool = False


class MailThreadRead(BaseModel):
    """Full thread with messages."""

    thread_key: str
    subject: str | None = None
    messages: list[MailMessageRead]


# ── Send Request ──


class MailSendRequestCreate(BaseModel):
    client_send_id: UUID
    mail_account_id: UUID
    mode: str = "new"  # new | reply | forward
    to_recipients: list[dict]
    cc_recipients: list[dict] | None = None
    bcc_recipients: list[dict] | None = None
    subject: str
    body_text: str | None = None
    body_html: str | None = None
    in_reply_to_message_id: UUID | None = None
    provider_thread_id: str | None = None


class MailSendResponse(BaseModel):
    id: UUID
    client_send_id: UUID
    status: str


class MailSendStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_send_id: UUID
    status: str
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


# ── Drafts ──


class MailDraftCreate(BaseModel):
    """Create or update a local draft."""

    mail_account_id: UUID
    to_recipients: list[dict] = []  # [{"name": "", "email": "..."}]
    subject: str = ""
    body_html: str = ""
    instruction: str = ""
    draft_id: UUID | None = None  # If provided, update existing draft


class MailDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    mail_account_id: UUID
    to_recipients: list[dict]
    subject: str | None
    body_html: str | None
    instruction: str | None
    created_at: datetime
    updated_at: datetime


# ── Email Draft Bundles (chat → email suggestion) ──


class EmailDraftBundleCreate(BaseModel):
    """Created internally by the suggestEmail tool handler."""

    conversation_id: UUID | None = None
    subject: str | None = None
    body_draft: str | None = None
    tone: str | None = None
    reason: str | None = None
    citations: list[dict] | None = None


class EmailDraftBundleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    conversation_id: UUID | None = None
    subject: str | None = None
    body_draft: str | None = None
    tone: str | None = None
    reason: str | None = None
    citations: list[dict] | None = None
    created_at: datetime
