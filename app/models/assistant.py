"""Assistant model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.collection import Collection
    from app.models.message import Message
    from app.integrations.nango.models import NangoConnection


class Assistant(Base):
    """Assistant with custom prompt and associated collections."""

    __tablename__ = "assistants"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100), default="mistral-medium-latest")
    settings: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="assistants")
    collections: Mapped[list["Collection"]] = relationship(
        "Collection",
        secondary="assistant_collections",
        back_populates="assistants",
    )
    integrations: Mapped[list["NangoConnection"]] = relationship(
        "NangoConnection",
        secondary="assistant_integrations",
        back_populates="assistants",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="assistant",
        cascade="all, delete-orphan",
    )
