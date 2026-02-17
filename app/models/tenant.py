"""Tenant model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.assistant import Assistant
    from app.models.collection import Collection
    from app.models.usage import Usage
    from app.models.user import User


class Tenant(Base):
    """Tenant represents a customer workspace."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    
    # Quota limits
    max_assistants: Mapped[int] = mapped_column(default=3)
    max_ingestion_tokens: Mapped[int] = mapped_column(default=1_000_000)  # per month
    max_chat_tokens: Mapped[int] = mapped_column(default=500_000)  # per month
    max_storage_bytes: Mapped[int] = mapped_column(default=1_073_741_824)  # 1GB
    max_transcription_seconds: Mapped[int] = mapped_column(default=120)  # free: 2min/month

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
    assistants: Mapped[list["Assistant"]] = relationship(
        "Assistant",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    collections: Mapped[list["Collection"]] = relationship(
        "Collection",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    usage_records: Mapped[list["Usage"]] = relationship(
        "Usage",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="tenant",
        uselist=False,
    )
