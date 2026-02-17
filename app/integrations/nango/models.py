"""SQLAlchemy model for Nango connection references.

We store a reference to each Nango connection in our DB to:
1. Associate connections with tenants (multi-tenant isolation)
2. Track which providers a tenant has connected
3. Store metadata (connection status, timestamps)

We do NOT store OAuth tokens. Nango manages those.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.assistant import Assistant

# M2M junction table
assistant_integrations = Table(
    "assistant_integrations",
    Base.metadata,
    Column("assistant_id", PG_UUID(as_uuid=True), ForeignKey("assistants.id", ondelete="CASCADE"), primary_key=True),
    Column("nango_connection_id", PG_UUID(as_uuid=True), ForeignKey("nango_connections.id", ondelete="CASCADE"), primary_key=True),
)


class NangoConnection(Base):
    """Reference to a Nango-managed OAuth connection."""

    __tablename__ = "nango_connections"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Provider key (e.g. hubspot, salesforce)"
    )
    nango_connection_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Connection ID used in Nango (typically tenant_id:provider)",
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", comment="pending | connected | error"
    )
    connection_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Optional JSON metadata"
    )
    user_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    assistants: Mapped[list["Assistant"]] = relationship(
        "Assistant",
        secondary=assistant_integrations,
        back_populates="integrations",
    )
