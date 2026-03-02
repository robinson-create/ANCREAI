"""OrgMember model — links a User to a Tenant (organization) with role and status."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import MemberStatus, OrgRole

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class OrgMember(Base):
    """Membership of a user within an organization (tenant).

    This replaces the 1:1 User→Tenant link with a proper N:M model
    supporting roles, invitations, and seat management.
    """

    __tablename__ = "org_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_org_members_tenant_user"),
    )

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
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OrgRole.MEMBER.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MemberStatus.INVITED.value,
    )
    invited_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    invited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    inviter: Mapped["User | None"] = relationship("User", foreign_keys=[invited_by])

    @property
    def is_admin(self) -> bool:
        return self.role == OrgRole.ADMIN.value

    @property
    def is_active(self) -> bool:
        return self.status == MemberStatus.ACTIVE.value
