"""SQLAlchemy models for the mail integration.

Tables:
- mail_accounts: OAuth-connected email accounts (Gmail, Microsoft)
- mail_messages: Synced email messages with parsed content
- mail_drafts: Local drafts from the email composer (not synced from provider)
- mail_sync_state: Incremental sync cursors per account
- mail_send_requests: Outbox with idempotency for reliable sending
- email_draft_bundles: Server-side context bundles for chat-to-email suggestions
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.integrations.nango.models import NangoConnection
    from app.models.tenant import Tenant
    from app.models.user import User


class MailAccount(Base):
    """An OAuth-connected email account (Gmail or Microsoft)."""

    __tablename__ = "mail_accounts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="gmail | microsoft | smtp"
    )
    email_address: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Filled after get_profile() on finalize"
    )
    nango_conn_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("nango_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | connected | error | revoked",
    )
    scopes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    smtp_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='{"host","port","user","password_encrypted","use_tls"} for smtp provider',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped["User"] = relationship("User")
    nango_connection: Mapped["NangoConnection | None"] = relationship(
        "NangoConnection"
    )
    sync_state: Mapped["MailSyncState | None"] = relationship(
        "MailSyncState",
        back_populates="mail_account",
        uselist=False,
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["MailMessage"]] = relationship(
        "MailMessage",
        back_populates="mail_account",
        cascade="all, delete-orphan",
    )
    send_requests: Mapped[list["MailSendRequest"]] = relationship(
        "MailSendRequest",
        back_populates="mail_account",
        cascade="all, delete-orphan",
    )


class MailMessage(Base):
    """A synced email message."""

    __tablename__ = "mail_messages"
    __table_args__ = (
        UniqueConstraint(
            "mail_account_id",
            "provider_message_id",
            name="uq_mail_msg_account_provider",
        ),
        Index("ix_mail_messages_thread", "mail_account_id", "provider_thread_id"),
        Index("ix_mail_messages_date", "mail_account_id", "date"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mail_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_message_id: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Gmail message ID or Graph message ID"
    )
    provider_thread_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Gmail threadId or Graph conversationId",
    )
    internet_message_id: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="RFC 2822 Message-ID header"
    )
    sender: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment='{"name": "...", "email": "..."}'
    )
    to_recipients: Mapped[list] = mapped_column(
        JSONB, nullable=False, comment='[{"name": "...", "email": "..."}]'
    )
    cc_recipients: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    bcc_recipients: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    is_indexed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false",
        comment="Whether this message has been indexed into RAG",
    )
    raw_headers: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="References, In-Reply-To for threading"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    mail_account: Mapped["MailAccount"] = relationship(
        "MailAccount", back_populates="messages"
    )


class MailDraft(Base):
    """Local draft from the email composer. Visible in the mail list."""

    __tablename__ = "mail_drafts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mail_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_recipients: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )  # [{"name": "", "email": "..."}]
    subject: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MailSyncState(Base):
    """Incremental sync cursor for a mail account."""

    __tablename__ = "mail_sync_state"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mail_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    gmail_history_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Gmail incremental sync cursor"
    )
    graph_delta_link: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Microsoft Graph delta link"
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="idle",
        comment="idle | syncing | error",
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    mail_account: Mapped["MailAccount"] = relationship(
        "MailAccount", back_populates="sync_state"
    )


class MailSendRequest(Base):
    """Outbox entry for reliable, idempotent email sending."""

    __tablename__ = "mail_send_requests"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "client_send_id", name="uq_send_tenant_client"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mail_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mail_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_send_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="Idempotency key from frontend (unique per tenant)",
    )
    mode: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="new | reply | forward"
    )
    to_recipients: Mapped[list] = mapped_column(JSONB, nullable=False)
    cc_recipients: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    bcc_recipients: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    subject: Mapped[str] = mapped_column(String(1000), nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    in_reply_to_message_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mail_messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="Our internal message ID for replies",
    )
    provider_thread_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Provider thread ID for replies"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        comment="queued | sending | sent | failed",
    )
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Filled after successful send"
    )
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    mail_account: Mapped["MailAccount"] = relationship(
        "MailAccount", back_populates="send_requests"
    )
    in_reply_to: Mapped["MailMessage | None"] = relationship("MailMessage")


class EmailDraftBundle(Base):
    """Server-side context bundle for chat-to-email suggestions.

    Created by the suggestEmail tool handler during chat.
    Retrieved by the email composer to hydrate the compose form.
    """

    __tablename__ = "email_draft_bundles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    subject: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    body_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="formal | friendly | neutral"
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Why the email was suggested"
    )
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
