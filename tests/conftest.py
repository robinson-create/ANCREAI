"""Shared test fixtures for org/personal scope security tests."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.retrieval import RetrievedChunk


# ── Constants ──────────────────────────────────────────────────────

TENANT_A_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_B_ID = UUID("22222222-2222-2222-2222-222222222222")
DOSSIER_A_ID = UUID("dddddddd-0001-0001-0001-000000000001")
DOSSIER_B_ID = UUID("dddddddd-0002-0002-0002-000000000002")
ASSISTANT_ID = UUID("aaaa0000-0000-0000-0000-000000000001")
COLLECTION_ID = UUID("cccccccc-0001-0001-0001-000000000001")


# ── Fake models ────────────────────────────────────────────────────

def fake_user(
    tenant_id: UUID = TENANT_A_ID,
    user_id: UUID = USER_A_ID,
    email: str = "user@test.com",
) -> SimpleNamespace:
    """Return a lightweight User-like object."""
    return SimpleNamespace(
        id=user_id,
        tenant_id=tenant_id,
        email=email,
        name="Test User",
        clerk_user_id="clerk_test",
    )


def fake_member(
    role: str = "admin",
    status: str = "active",
    tenant_id: UUID = TENANT_A_ID,
    user_id: UUID = USER_A_ID,
    member_id: UUID | None = None,
) -> SimpleNamespace:
    """Return a lightweight OrgMember-like object."""
    return SimpleNamespace(
        id=member_id or uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        status=status,
        is_admin=(role == "admin"),
        is_active=(status == "active"),
    )


def fake_dossier(
    user_id: UUID = USER_A_ID,
    tenant_id: UUID = TENANT_A_ID,
    dossier_id: UUID = DOSSIER_A_ID,
    name: str = "Test Dossier",
) -> SimpleNamespace:
    """Return a lightweight Dossier-like object."""
    return SimpleNamespace(
        id=dossier_id,
        tenant_id=tenant_id,
        user_id=user_id,
        name=name,
        description=None,
        color=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def fake_chunk(
    chunk_id: str | None = None,
    scope: str = "org",
    collection_id: str | None = None,
    dossier_id: str | None = None,
    tenant_id: str | None = None,
    content: str = "test content",
    score: float = 0.5,
) -> RetrievedChunk:
    """Return a RetrievedChunk with scope metadata."""
    return RetrievedChunk(
        chunk_id=chunk_id or str(uuid4()),
        document_id=str(uuid4()),
        document_filename="test.pdf",
        content=content,
        page_number=1,
        section_title=None,
        score=score,
    )


# ── Mock DB session ────────────────────────────────────────────────

def mock_db() -> AsyncMock:
    """Return an AsyncMock that mimics an async SQLAlchemy session.

    Usage in tests:
        db = mock_db()
        db.execute.return_value.scalar_one_or_none.return_value = some_obj
    """
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.refresh = AsyncMock()
    return session
