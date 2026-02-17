"""
Calendar models for Ancre.

Stores:
- CalendarEventLink: Mapping between Ancre and external calendar events
- CalendarOperationLog: Audit log for calendar operations

Note: NangoConnection is imported from app.integrations.nango.models
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, DateTime, func, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Import existing NangoConnection model
from app.integrations.nango.models import NangoConnection  # noqa: F401


class CalendarEventLink(Base):
    """
    Link between Ancre and external calendar event.

    Allows tracking, updating, and deleting events created via Ancre.
    Stores snapshot of event data for quick access and conflict detection.
    """
    __tablename__ = "calendar_event_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    assistant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assistants.id", ondelete="SET NULL"),
        nullable=True
    )

    # External provider info
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # 'google', 'microsoft'
    external_event_id: Mapped[str] = mapped_column(String(500), nullable=False)
    external_calendar_id: Mapped[str] = mapped_column(String(500), nullable=False, server_default="primary")

    # Event snapshot (for quick access and search)
    title_snapshot: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, server_default="Europe/Paris")
    attendees_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    has_video_conference: Mapped[bool] = mapped_column(Boolean, default=False)

    # Sync tracking
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    tenant = relationship("Tenant")
    assistant = relationship("Assistant")

    __table_args__ = (
        Index("ix_calendar_event_links_tenant_user", "tenant_id", "user_id"),
        Index("ix_calendar_event_links_starts_at", "starts_at"),
        UniqueConstraint(
            "tenant_id", "user_id", "provider", "external_event_id",
            name="uq_calendar_event_links_external"
        ),
    )


class CalendarOperationLog(Base):
    """
    Audit log for calendar operations.

    Tracks all calendar actions for debugging, analytics, and compliance.
    Payloads are sanitized to remove sensitive data (full emails, etc.)
    """
    __tablename__ = "calendar_operation_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    assistant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Operation details
    op_type: Mapped[str] = mapped_column(String(50), nullable=False)  # create, update, delete, list, find
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, error, pending
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Payloads (sanitized)
    request_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Performance tracking
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant")

    __table_args__ = (
        Index("ix_calendar_operation_logs_tenant_user", "tenant_id", "user_id"),
        Index("ix_calendar_operation_logs_created_at", "created_at"),
    )
