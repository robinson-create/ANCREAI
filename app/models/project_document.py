"""ProjectDocument model — files uploaded into a project.

Separate from org-level Document and personal DossierDocument.
Structural guarantee: no reference to Collection or Dossier.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class ProjectDocumentStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ProjectDocument(Base):
    __tablename__ = "project_documents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=ProjectDocumentStatus.PENDING, index=True,
    )
    error_message: Mapped[str | None] = mapped_column(String(2000))
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    doc_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    user: Mapped["User"] = relationship("User")
