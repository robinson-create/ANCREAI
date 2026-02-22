"""Audit log model — immutable event log for agent actions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """Immutable audit trail for agent actions, tool calls, and system events.

    No FK on tenant_id/run_id for flexibility (system-level events may lack them).
    """

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        index=True,
    )
    run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. "tool_called", "delegation_started", "memory_updated", "run_completed"

    entity_type: Mapped[str | None] = mapped_column(String(50))
    # e.g. "assistant", "document", "collection"

    entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    detail: Mapped[dict | None] = mapped_column(JSONB)
    # Flexible payload: tool name, error info, before/after, etc.

    level: Mapped[str] = mapped_column(String(10), default="info")
    # info | warn | error

    message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
