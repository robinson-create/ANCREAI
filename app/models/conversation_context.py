"""Conversation context model — hot memory for active conversations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConversationContext(Base):
    """Hot memory for a conversation: structured summary, constraints, decisions, facts.

    Updated every N interactions by the memory worker.
    Injected into system prompt (max ~800 tokens total).
    """

    __tablename__ = "conversation_contexts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "conversation_id",
            name="uq_conv_ctx_tenant_conversation",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    assistant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Narrative summary (max ~500 tokens)
    summary_text: Mapped[str | None] = mapped_column(Text)

    # Structured extracted fields (append-only + dedupe)
    constraints: Mapped[list | None] = mapped_column(JSONB, default=list)
    # Structure: ["Le budget ne doit pas dépasser 50k€", ...]  (max 15)

    decisions: Mapped[list | None] = mapped_column(JSONB, default=list)
    # Structure: ["On utilise Next.js", ...]  (max 20)

    open_questions: Mapped[list | None] = mapped_column(JSONB, default=list)
    # Structure: ["Quel hébergeur choisir ?", ...]  (max 10)

    facts: Mapped[list | None] = mapped_column(JSONB, default=list)
    # Structure: [{"key": "...", "value": "...", "source": "user|rag|inferred",
    #              "confidence": 0.9, "last_seen_at": "2026-02-20T..."}]  (max 20)

    # Track interaction count for summarization triggers
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
