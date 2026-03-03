"""DossierItem model — generic item linked to a personal dossier.

Allows linking presentations, workspace documents, emails, etc. to a dossier
for organisation purposes. Upload documents are handled separately via
DossierDocument (with S3 storage and RAG processing).
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dossier import Dossier


class DossierItem(Base):
    """A generic item reference linked to a dossier."""

    __tablename__ = "dossier_items"

    __table_args__ = (
        UniqueConstraint(
            "dossier_id",
            "item_type",
            "item_id",
            name="uq_dossier_items_dossier_type_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    dossier_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dossiers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    dossier: Mapped["Dossier"] = relationship("Dossier")
