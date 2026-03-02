"""AssistantPermission model — controls which org members can use which assistants."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.assistant import Assistant
    from app.models.org_member import OrgMember


class AssistantPermission(Base):
    """Grants an org member access to a specific assistant.

    If no row exists for a (member, assistant) pair, the member cannot use
    that assistant. Admins bypass this check.
    """

    __tablename__ = "assistant_permissions"
    __table_args__ = (
        UniqueConstraint(
            "assistant_id", "member_id",
            name="uq_assistant_permissions_assistant_member",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    assistant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("org_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    assistant: Mapped["Assistant"] = relationship("Assistant")
    member: Mapped["OrgMember"] = relationship("OrgMember")
