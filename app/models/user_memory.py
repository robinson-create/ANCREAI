"""User memory model — persistent per-user facts across conversations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserMemory(Base):
    """Cold memory scoped to a tenant + user pair.

    Stores stable user preferences and facts compressed into bullets.
    Injected into system prompt (max ~200 tokens).
    """

    __tablename__ = "user_memories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_user_memory_tenant_user"),
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
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
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
