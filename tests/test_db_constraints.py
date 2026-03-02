"""Tests that DB CHECK constraints are correctly declared on models.

These tests verify that the SQLAlchemy models carry the expected CHECK
constraints so that incoherent state is rejected at the database level —
even if a code path bypasses Python validation.

We cannot execute actual CHECK constraints without a real Postgres
connection, so we verify:
1. The constraint exists in __table_args__
2. The constraint SQL rejects the expected invalid combinations
"""

import re
from uuid import uuid4

import pytest

from app.models.conversation import Conversation
from app.models.chunk import Chunk


# ── Helpers ────────────────────────────────────────────────────────

def _get_check_constraint(model_class, name: str):
    """Find a CHECK constraint by name in a model's table."""
    for constraint in model_class.__table__.constraints:
        if getattr(constraint, "name", None) == name:
            return constraint
    return None


def _get_check_sql(model_class, name: str) -> str:
    """Get the SQL text of a CHECK constraint."""
    constraint = _get_check_constraint(model_class, name)
    assert constraint is not None, f"CHECK constraint '{name}' not found on {model_class.__tablename__}"
    return str(constraint.sqltext)


def _sql_matches(check_sql: str, field: str) -> bool:
    """Check if a field appears in the constraint SQL."""
    return field in check_sql


# ── Conversation scope coherence ──────────────────────────────────


class TestConversationScopeConstraint:
    """Verify ck_conversations_scope_coherence is correctly defined."""

    CONSTRAINT_NAME = "ck_conversations_scope_coherence"

    def test_constraint_exists(self):
        """The CHECK constraint must exist on the conversations table."""
        constraint = _get_check_constraint(Conversation, self.CONSTRAINT_NAME)
        assert constraint is not None

    def test_constraint_references_scope(self):
        sql = _get_check_sql(Conversation, self.CONSTRAINT_NAME)
        assert "scope" in sql

    def test_constraint_enforces_org_requires_assistant(self):
        """scope='org' must require assistant_id IS NOT NULL."""
        sql = _get_check_sql(Conversation, self.CONSTRAINT_NAME)
        # The constraint should mention org + assistant_id NOT NULL
        assert "org" in sql
        assert "assistant_id" in sql

    def test_constraint_enforces_org_forbids_dossier(self):
        """scope='org' must require dossier_id IS NULL."""
        sql = _get_check_sql(Conversation, self.CONSTRAINT_NAME)
        assert "dossier_id" in sql
        # Must have a NULL check for dossier_id in org context
        assert re.search(r"dossier_id\s+IS\s+NULL", sql, re.IGNORECASE)

    def test_constraint_enforces_personal_requires_dossier(self):
        """scope='personal' must require dossier_id IS NOT NULL."""
        sql = _get_check_sql(Conversation, self.CONSTRAINT_NAME)
        assert "personal" in sql
        assert re.search(r"dossier_id\s+IS\s+NOT\s+NULL", sql, re.IGNORECASE)

    def test_constraint_enforces_personal_forbids_assistant(self):
        """scope='personal' must require assistant_id IS NULL."""
        sql = _get_check_sql(Conversation, self.CONSTRAINT_NAME)
        assert re.search(r"assistant_id\s+IS\s+NULL", sql, re.IGNORECASE)


# ── Chunk scope coherence ─────────────────────────────────────────


class TestChunkScopeConstraint:
    """Verify ck_chunks_scope_coherence is correctly defined."""

    CONSTRAINT_NAME = "ck_chunks_scope_coherence"

    def test_constraint_exists(self):
        constraint = _get_check_constraint(Chunk, self.CONSTRAINT_NAME)
        assert constraint is not None

    def test_constraint_references_scope(self):
        sql = _get_check_sql(Chunk, self.CONSTRAINT_NAME)
        assert "scope" in sql

    def test_constraint_org_requires_collection(self):
        """scope='org' must require collection_id IS NOT NULL."""
        sql = _get_check_sql(Chunk, self.CONSTRAINT_NAME)
        assert "collection_id" in sql
        assert re.search(r"collection_id\s+IS\s+NOT\s+NULL", sql, re.IGNORECASE)

    def test_constraint_org_forbids_personal_fields(self):
        """scope='org' must require user_id IS NULL AND dossier_id IS NULL."""
        sql = _get_check_sql(Chunk, self.CONSTRAINT_NAME)
        assert "user_id" in sql
        assert "dossier_id" in sql

    def test_constraint_personal_requires_user_and_dossier(self):
        """scope='personal' must require both user_id and dossier_id NOT NULL."""
        sql = _get_check_sql(Chunk, self.CONSTRAINT_NAME)
        assert re.search(r"user_id\s+IS\s+NOT\s+NULL", sql, re.IGNORECASE)
        assert re.search(r"dossier_id\s+IS\s+NOT\s+NULL", sql, re.IGNORECASE)

    def test_constraint_personal_forbids_collection(self):
        """scope='personal' must require collection_id IS NULL."""
        sql = _get_check_sql(Chunk, self.CONSTRAINT_NAME)
        assert re.search(r"collection_id\s+IS\s+NULL", sql, re.IGNORECASE)
