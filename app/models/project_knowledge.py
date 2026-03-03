"""ProjectKnowledge model — conversation summaries indexed into project RAG."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.project import Project


class ProjectKnowledge(Base):
    """A conversation summary stored as project knowledge.

    When a user triggers "summarize conversation", the LLM generates
    a structured summary which is stored here AND chunked/embedded
    into the project's RAG scope.
    """

    __tablename__ = "project_knowledge"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True,
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    tokens_used: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    source_conversation: Mapped["Conversation | None"] = relationship("Conversation")
