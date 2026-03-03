"""Conversation model — explicit scope (org/personal/project) with DB-level constraints.

A Conversation is the first-class entity that owns messages. It carries an
explicit `scope` discriminator enforced by CHECK constraints so that:
  - scope='org'      → assistant_id IS NOT NULL, dossier_id/project_id IS NULL
  - scope='personal' → assistant_id/project_id IS NULL
                        dossier_id may be NULL (global personal) or NOT NULL (dossier-scoped)
  - scope='project'  → project_id  IS NOT NULL, assistant_id/dossier_id IS NULL

This makes it impossible to create an ambiguous conversation at the DB level.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ContentScope

if TYPE_CHECKING:
    from app.models.assistant import Assistant
    from app.models.dossier import Dossier
    from app.models.message import Message
    from app.models.project import Project
    from app.models.tenant import Tenant
    from app.models.user import User


class Conversation(Base):
    """A conversation thread with explicit org/personal/project scope.

    Scope rules enforced at DB level:
    - ORG: must have assistant_id, must NOT have dossier_id/project_id
    - PERSONAL: must NOT have assistant_id/project_id
                dossier_id may be NULL (global personal chat) or NOT NULL (dossier-scoped)
    - PROJECT: must have project_id, must NOT have assistant_id/dossier_id
    """

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            """
            (scope = 'org' AND assistant_id IS NOT NULL
                           AND dossier_id IS NULL AND project_id IS NULL)
            OR
            (scope = 'personal' AND assistant_id IS NULL AND project_id IS NULL)
            OR
            (scope = 'project' AND project_id IS NOT NULL
                               AND assistant_id IS NULL AND dossier_id IS NULL)
            """,
            name="ck_conversations_scope_coherence",
        ),
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
    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Conditional links (exactly one must be set, enforced by CHECK) ---

    assistant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    dossier_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dossiers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
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
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped["User"] = relationship("User")
    assistant: Mapped["Assistant | None"] = relationship("Assistant")
    dossier: Mapped["Dossier | None"] = relationship("Dossier")
    project: Mapped["Project | None"] = relationship("Project")
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    @property
    def is_org(self) -> bool:
        return self.scope == ContentScope.ORG.value

    @property
    def is_personal(self) -> bool:
        return self.scope == ContentScope.PERSONAL.value

    @property
    def is_project(self) -> bool:
        return self.scope == ContentScope.PROJECT.value
