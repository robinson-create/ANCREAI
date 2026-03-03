"""Allow personal-global conversations and memory chunks without dossier.

- Relax conversation CHECK: scope='personal' allows dossier_id IS NULL
- Relax chunk CHECK: scope='personal' allows dossier_id IS NULL (memory chunks)
- Add partial composite index on chunks for user-scoped keyword search

Revision ID: 033
Revises: 032
Create Date: 2026-03-04
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic
revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Relax conversation CHECK constraint ────────────────────────
    # Allow scope='personal' with dossier_id IS NULL (global personal chat)
    op.drop_constraint(
        "ck_conversations_scope_coherence", "conversations", type_="check"
    )
    op.create_check_constraint(
        "ck_conversations_scope_coherence",
        "conversations",
        """
        (scope = 'org' AND assistant_id IS NOT NULL
                       AND dossier_id IS NULL AND project_id IS NULL)
        OR
        (scope = 'personal' AND assistant_id IS NULL AND project_id IS NULL)
        OR
        (scope = 'project' AND project_id IS NOT NULL
                           AND assistant_id IS NULL AND dossier_id IS NULL)
        """,
    )

    # ── 2. Relax chunk CHECK constraint ───────────────────────────────
    # Allow scope='personal' with dossier_id IS NULL (memory/summary chunks)
    op.drop_constraint("ck_chunks_scope_coherence", "chunks", type_="check")
    op.create_check_constraint(
        "ck_chunks_scope_coherence",
        "chunks",
        """
        (scope = 'org' AND collection_id IS NOT NULL
                      AND user_id IS NULL AND dossier_id IS NULL
                      AND project_id IS NULL)
        OR
        (scope = 'personal' AND user_id IS NOT NULL
                            AND collection_id IS NULL AND project_id IS NULL)
        OR
        (scope = 'project' AND project_id IS NOT NULL AND user_id IS NOT NULL
                           AND collection_id IS NULL AND dossier_id IS NULL)
        """,
    )

    # ── 3. Partial composite index for user-scoped keyword search ─────
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chunks_tenant_user_scope
        ON chunks (tenant_id, user_id, scope)
        WHERE user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_tenant_user_scope")

    # Restore old chunk CHECK
    op.drop_constraint("ck_chunks_scope_coherence", "chunks", type_="check")
    op.create_check_constraint(
        "ck_chunks_scope_coherence",
        "chunks",
        """
        (scope = 'org' AND collection_id IS NOT NULL
                      AND user_id IS NULL AND dossier_id IS NULL
                      AND project_id IS NULL)
        OR
        (scope = 'personal' AND user_id IS NOT NULL AND dossier_id IS NOT NULL
                            AND collection_id IS NULL AND project_id IS NULL)
        OR
        (scope = 'project' AND project_id IS NOT NULL AND user_id IS NOT NULL
                           AND collection_id IS NULL AND dossier_id IS NULL)
        """,
    )

    # Restore old conversation CHECK
    op.drop_constraint(
        "ck_conversations_scope_coherence", "conversations", type_="check"
    )
    op.create_check_constraint(
        "ck_conversations_scope_coherence",
        "conversations",
        """
        (scope = 'org' AND assistant_id IS NOT NULL
                       AND dossier_id IS NULL AND project_id IS NULL)
        OR
        (scope = 'personal' AND dossier_id IS NOT NULL
                            AND assistant_id IS NULL AND project_id IS NULL)
        OR
        (scope = 'project' AND project_id IS NOT NULL
                           AND assistant_id IS NULL AND dossier_id IS NULL)
        """,
    )
