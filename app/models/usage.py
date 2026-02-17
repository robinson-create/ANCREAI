"""Usage tracking model."""

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class Usage(Base):
    """Usage tracking per tenant per period."""

    __tablename__ = "usage"

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
    
    # Period (monthly billing)
    period: Mapped[date] = mapped_column(Date, nullable=False)  # First day of month
    
    # Counters
    ingestion_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    chat_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    chat_output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    storage_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    documents_count: Mapped[int] = mapped_column(default=0)
    messages_count: Mapped[int] = mapped_column(default=0)
    transcription_seconds: Mapped[int] = mapped_column(default=0)

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
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="usage_records")

    __table_args__ = (
        UniqueConstraint("tenant_id", "period", name="uq_usage_tenant_period"),
    )
