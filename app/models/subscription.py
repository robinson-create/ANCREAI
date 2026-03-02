"""Subscription model for Stripe billing.

Transition: subscription is moving from user-scoped (user_id) to
org-scoped (tenant_id).  During the transition both columns coexist.
New code should read/write tenant_id; user_id is kept for backward compat.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class SubscriptionPlan(str, Enum):
    """Available subscription plans."""

    FREE = "free"
    PRO = "pro"


class SubscriptionStatus(str, Enum):
    """Subscription status values."""

    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"


class Subscription(Base):
    """Subscription tracks an organization's billing status.

    Transition: tenant_id is the new primary key for lookups.
    user_id is kept for backward compat during migration.
    """

    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # --- NEW: org-scoped (the source of truth going forward) ---
    tenant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=True,  # nullable during transition, will become NOT NULL
        index=True,
    )

    # --- LEGACY: kept during transition, will be dropped later ---
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    plan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=SubscriptionPlan.FREE.value,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=SubscriptionStatus.ACTIVE.value,
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )
    stripe_price_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Seat & assistant limits (driven by Stripe subscription items)
    max_seats: Mapped[int] = mapped_column(Integer, default=1)
    max_assistants: Mapped[int] = mapped_column(Integer, default=1)
    max_org_documents: Mapped[int] = mapped_column(Integer, default=10)

    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
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
    tenant: Mapped["Tenant | None"] = relationship("Tenant")
    user: Mapped["User"] = relationship("User", back_populates="subscription")

    @property
    def is_pro(self) -> bool:
        """Check if org has active pro subscription."""
        return (
            self.plan == SubscriptionPlan.PRO.value
            and self.status in (SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value)
        )
