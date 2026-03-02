"""Chunk model.

Chunks carry an explicit `scope` discriminator so that org-level and
personal-level chunks are structurally separated in the DB.  A CHECK
constraint enforces the invariant:
  scope='org'      → collection_id set, user_id/dossier_id NULL
  scope='personal' → user_id + dossier_id set, collection_id NULL
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Chunk(Base):
    """Chunk represents an indexed text segment (org or personal scope)."""

    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint(
            """
            (scope = 'org' AND collection_id IS NOT NULL
                          AND user_id IS NULL AND dossier_id IS NULL)
            OR
            (scope = 'personal' AND user_id IS NOT NULL AND dossier_id IS NOT NULL
                                AND collection_id IS NULL)
            """,
            name="ck_chunks_scope_coherence",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # --- Explicit scope (first-class citizen) ---
    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="org",
        index=True,
    )

    # Denormalized for FTS query performance (avoids JOINs)
    tenant_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    collection_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    # --- Personal scope fields ---
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    dossier_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True, index=True)
    dossier_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dossier_documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Multi-source support (document, email, etc.)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Full-text search vector (stored, updated on insert)
    content_tsv: Mapped[None] = mapped_column(TSVECTOR, nullable=True)

    # Location metadata
    page_number: Mapped[int | None] = mapped_column(Integer)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))

    # Vector store reference
    qdrant_id: Mapped[str | None] = mapped_column(String(100), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    document: Mapped["Document | None"] = relationship("Document", back_populates="chunks")
