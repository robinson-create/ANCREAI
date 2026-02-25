"""Presentation models — AI-generated slide decks with export support."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref

from app.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant


# ── Enums ──


class PresentationStatus(str, Enum):
    DRAFT = "draft"
    GENERATING_OUTLINE = "generating_outline"
    OUTLINE_READY = "outline_ready"
    GENERATING_SLIDES = "generating_slides"
    READY = "ready"
    EXPORTING = "exporting"
    ERROR = "error"


class AssetStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    ERROR = "error"


class AssetKind(str, Enum):
    IMAGE = "image"
    SVG = "svg"
    FONT = "font"
    BG = "bg"


class RunPurpose(str, Enum):
    OUTLINE = "outline"
    SLIDE_GEN = "slide_gen"
    REPAIR = "repair"
    REGENERATE = "regenerate"
    IMAGE_PROMPT = "image_prompt"
    EXPORT_COPY = "export_copy"


# ── Tables ──


class Presentation(Base):
    __tablename__ = "presentations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="Sans titre")
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default=PresentationStatus.DRAFT.value, index=True,
    )
    theme_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("presentation_themes.id", ondelete="SET NULL"),
        nullable=True,
    )
    outline: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    slide_order: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    theme: Mapped["PresentationTheme | None"] = relationship(
        "PresentationTheme", foreign_keys=[theme_id],
    )
    slides: Mapped[list["PresentationSlide"]] = relationship(
        "PresentationSlide",
        back_populates="presentation",
        cascade="all, delete-orphan",
        order_by="PresentationSlide.position",
    )
    exports: Mapped[list["PresentationExport"]] = relationship(
        "PresentationExport",
        back_populates="presentation",
        cascade="all, delete-orphan",
    )
    assets: Mapped[list["PresentationAsset"]] = relationship(
        "PresentationAsset",
        back_populates="presentation",
        cascade="all, delete-orphan",
    )


class PresentationSlide(Base):
    __tablename__ = "presentation_slides"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    presentation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("presentations.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    layout_type: Mapped[str] = mapped_column(String(20), default="vertical")
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    root_image: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    bg_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    speaker_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    presentation: Mapped["Presentation"] = relationship(
        "Presentation", back_populates="slides",
    )

    __table_args__ = (
        # Composite index for ordered slide retrieval
        {"comment": "Individual slides for a presentation"},
    )


class PresentationTheme(Base):
    __tablename__ = "presentation_themes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,  # NULL = built-in theme
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    theme_data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )


class PresentationAsset(Base):
    __tablename__ = "presentation_assets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    presentation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("presentations.id", ondelete="CASCADE"),
        nullable=False,
    )
    slide_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("presentation_slides.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        String(10), default=AssetStatus.PENDING.value, nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    mime: Mapped[str | None] = mapped_column(String(100), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # Relationships
    presentation: Mapped["Presentation"] = relationship(
        "Presentation", back_populates="assets",
    )


class PresentationExport(Base):
    __tablename__ = "presentation_exports"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    presentation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("presentations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True,
    )
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    s3_key: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Snapshot for traceability
    presentation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    slide_count: Mapped[int] = mapped_column(Integer, nullable=False)
    theme_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # Relationships
    presentation: Mapped["Presentation"] = relationship(
        "Presentation", back_populates="exports",
    )


class PresentationGenerationRun(Base):
    __tablename__ = "presentation_generation_runs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True,
    )
    presentation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("presentations.id", ondelete="CASCADE"),
        nullable=False,
    )
    slide_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("presentation_slides.id", ondelete="SET NULL"),
        nullable=True,
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    repair_attempts: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
