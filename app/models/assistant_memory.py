"""Assistant memory model — persistent per-assistant learned context."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AssistantMemory(Base):
    """Cold memory scoped to a tenant + assistant pair.

    Stores stable assistant-level knowledge compressed into bullets.
    Injected into system prompt (max ~300 tokens).
    """

    __tablename__ = "assistant_memories"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "assistant_id",
            name="uq_assistant_memory_tenant_assistant",
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
    assistant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    compressed_text: Mapped[str | None] = mapped_column(Text)
    compressed_token_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
