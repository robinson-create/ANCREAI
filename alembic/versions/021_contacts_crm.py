"""Add contacts CRM tables.

Revision ID: 021
Revises: 020
Create Date: 2026-02-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── companies ──
    op.create_table(
        "companies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("company_domain", sa.String(255), nullable=True),
        sa.Column("company_industry", sa.String(100), nullable=True),
        sa.Column("company_size", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_companies_tenant_id", "companies", ["tenant_id"])
    # Unique constraint on (tenant_id, LOWER(company_name))
    op.execute(
        """
        CREATE UNIQUE INDEX uq_companies_tenant_name
        ON companies (tenant_id, LOWER(company_name))
        """
    )

    # ── contacts ──
    op.create_table(
        "contacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Person fields
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("primary_email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("contact_type", sa.String(50), nullable=False, server_default="autre"),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=True),
        # Company reference
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Location
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        # Metadata
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True, server_default="[]"),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=False, server_default="1.0"),
        sa.Column("field_confidence", postgresql.JSONB(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # Add full-text search column
    op.execute("""
        ALTER TABLE contacts ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('french', COALESCE(first_name, '')), 'A') ||
            setweight(to_tsvector('french', COALESCE(last_name, '')), 'A') ||
            setweight(to_tsvector('simple', COALESCE(primary_email, '')), 'B') ||
            setweight(to_tsvector('french', COALESCE(notes, '')), 'C')
        ) STORED
    """)

    # Indexes
    op.create_index("ix_contacts_tenant_id", "contacts", ["tenant_id"])
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])
    op.create_index("ix_contacts_type", "contacts", ["contact_type"])
    op.create_index("ix_contacts_source", "contacts", ["source"])
    op.create_index("ix_contacts_tags", "contacts", ["tags"], postgresql_using="gin")
    op.create_index("ix_contacts_search_vector", "contacts", ["search_vector"], postgresql_using="gin")

    # Unique constraint on tenant + email (case-insensitive)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_contacts_tenant_email
        ON contacts (tenant_id, LOWER(primary_email))
        """
    )

    # Check constraint for contact_type enum
    op.create_check_constraint(
        "ck_contact_type",
        "contacts",
        "contact_type IN ('client', 'prospect', 'partenaire', 'fournisseur', 'candidat', 'interne', 'autre')",
    )

    # ── contact_updates ──
    op.create_table(
        "contact_updates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("update_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_contact_updates_tenant_id", "contact_updates", ["tenant_id"])
    op.create_index("ix_contact_updates_contact_id", "contact_updates", ["contact_id"])
    op.create_index("ix_contact_updates_created_at", "contact_updates", [sa.text("created_at DESC")])

    # ── contact_email_links ──
    op.create_table(
        "contact_email_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mail_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mail_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("link_type", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_contact_email_links_contact_id", "contact_email_links", ["contact_id"])
    op.create_index("ix_contact_email_links_message_id", "contact_email_links", ["mail_message_id"])
    op.create_unique_constraint(
        "uq_contact_email_link",
        "contact_email_links",
        ["contact_id", "mail_message_id", "link_type"],
    )


def downgrade() -> None:
    op.drop_table("contact_email_links")
    op.drop_table("contact_updates")
    op.drop_table("contacts")
    op.drop_table("companies")
