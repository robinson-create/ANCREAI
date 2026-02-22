"""Agent run model — tracks each agent execution."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentProfile(StrEnum):
    """Execution profile for an assistant."""

    REACTIVE = "reactive"
    BALANCED = "balanced"
    PRO = "pro"
    EXEC = "exec"


class AgentRunStatus(StrEnum):
    """Status of an agent run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    TIMEOUT = "timeout"


class AgentRun(Base):
    """Single agent execution with budget tracking and status lifecycle."""

    __tablename__ = "agent_runs"

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
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    profile: Mapped[str] = mapped_column(
        String(20),
        default=AgentProfile.REACTIVE.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=AgentRunStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str | None] = mapped_column(Text)

    # Budget & usage
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    tool_rounds: Mapped[int] = mapped_column(Integer, default=0)
    budget_tokens: Mapped[int | None] = mapped_column(Integer)
    budget_tokens_remaining: Mapped[int | None] = mapped_column(Integer)

    # Error tracking
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)

    # Flexible metadata (plan JSON, tool results summary, etc.)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    # Lifecycle timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
