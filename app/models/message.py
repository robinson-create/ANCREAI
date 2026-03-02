"""Message model for chat history."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.assistant import Assistant
    from app.models.conversation import Conversation


class MessageRole(str, Enum):
    """Message role in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(Base):
    """Message in a conversation.

    Transition note: messages are being migrated from the old
    (assistant_id + bare conversation_id UUID) model to a proper FK
    to the conversations table.  During the transition both columns
    coexist:
      - conversation_ref_id  → FK to conversations (new, nullable during migration)
      - assistant_id         → kept for backward compat (will be removed later)
      - conversation_id      → bare UUID, kept for backward compat (will be removed later)
    """

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # --- NEW: proper FK to conversations table ---
    conversation_ref_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,  # nullable during migration, will become NOT NULL
        index=True,
    )

    # --- LEGACY: kept during transition, will be dropped later ---
    # nullable=True to support personal dossier messages (no assistant)
    assistant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Citations for assistant messages
    citations: Mapped[list | None] = mapped_column(JSONB)
    # Structure: [{"chunk_id": "...", "document_id": "...", "page": 1, "excerpt": "..."}]

    # Generative UI blocks (tool call results)
    blocks: Mapped[list | None] = mapped_column(JSONB)
    # Structure: [{"id": "...", "type": "kpi_cards", "payload": {...}}]

    # Token tracking
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    assistant: Mapped["Assistant | None"] = relationship("Assistant", back_populates="messages")
    conversation: Mapped["Conversation | None"] = relationship(
        "Conversation", back_populates="messages",
    )
