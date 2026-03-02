"""Tests for cross-tenant isolation.

The most critical security boundary in B2B SaaS: tenant A must NEVER
see, modify, or delete tenant B's resources. These tests verify
isolation at the retrieval, API, and deletion layers.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    TENANT_A_ID,
    TENANT_B_ID,
    USER_A_ID,
    USER_B_ID,
    DOSSIER_A_ID,
    DOSSIER_B_ID,
    ASSISTANT_ID,
    COLLECTION_ID,
    fake_user,
    fake_member,
    fake_dossier,
    mock_db,
)

from app.main import app
from app.deps import get_current_user, get_current_member, get_db


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


def _setup_tenant_user(tenant_id: UUID, user_id: UUID, role: str = "admin"):
    """Configure dependency overrides for a specific tenant/user."""
    user = fake_user(tenant_id=tenant_id, user_id=user_id)
    member = fake_member(role=role, status="active", tenant_id=tenant_id, user_id=user_id)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_member] = lambda: member
    return user, member


# ── API Level: Dossier Cross-Tenant ──────────────────────────────


class TestDossierCrossTenant:
    """Tenant A cannot see or manipulate tenant B's dossiers."""

    def test_tenant_b_cannot_see_tenant_a_dossier(self):
        """User from tenant B listing dossiers sees nothing from tenant A."""
        _setup_tenant_user(TENANT_B_ID, USER_B_ID)

        db = mock_db()
        # The DB returns no dossiers because query filters by user.id
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        async def _fake_db():
            yield db
        app.dependency_overrides[get_db] = _fake_db

        with TestClient(app) as client:
            response = client.get("/api/v1/dossiers")
        assert response.status_code == 200
        assert response.json() == []

    def test_tenant_b_cannot_get_tenant_a_dossier_by_id(self):
        """Tenant B user requesting tenant A's dossier -> 404."""
        _setup_tenant_user(TENANT_B_ID, USER_B_ID)

        db = mock_db()
        # Dossier belongs to USER_A in TENANT_A
        dossier_a = fake_dossier(user_id=USER_A_ID, tenant_id=TENANT_A_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dossier_a
        db.execute.return_value = mock_result

        async def _fake_db():
            yield db
        app.dependency_overrides[get_db] = _fake_db

        with TestClient(app) as client:
            response = client.get(f"/api/v1/dossiers/{DOSSIER_A_ID}")
        # _ensure_owner checks user_id -> 404
        assert response.status_code == 404


# ── Retrieval Level: Keyword Search Cross-Tenant ─────────────────


class TestKeywordSearchCrossTenant:
    """Keyword search always filters by tenant_id in the SQL query."""

    @pytest.mark.asyncio
    async def test_keyword_search_filters_by_tenant(self):
        """The SQL query must include tenant_id = <requesting tenant>."""
        from app.core.retrieval.keyword_retriever import keyword_search

        db = mock_db()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result

        await keyword_search(
            db=db,
            tenant_id=TENANT_A_ID,
            collection_ids=[COLLECTION_ID],
            query="secret project",
            topk=10,
        )

        assert db.execute.called
        called_sql = str(db.execute.call_args[0][0])
        assert "tenant_id" in called_sql

    @pytest.mark.asyncio
    async def test_keyword_search_uses_requesting_tenant_not_hardcoded(self):
        """Different tenant_id must produce different SQL parameter."""
        from app.core.retrieval.keyword_retriever import keyword_search

        db = mock_db()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result

        await keyword_search(
            db=db,
            tenant_id=TENANT_B_ID,
            collection_ids=[COLLECTION_ID],
            query="secret",
            topk=10,
        )

        # The params should contain TENANT_B_ID
        call_params = db.execute.call_args[0][1] if len(db.execute.call_args[0]) > 1 else db.execute.call_args[1]
        assert str(TENANT_B_ID) in str(call_params)


# ── Retrieval Level: Vector Search Cross-Tenant ──────────────────


class TestVectorSearchCrossTenant:
    """Vector store search always includes tenant_id in the Qdrant filter."""

    @pytest.mark.asyncio
    async def test_vector_search_includes_tenant_filter(self):
        """The Qdrant query must include a tenant_id FieldCondition."""
        from app.core.vector_store import VectorStore
        from qdrant_client.models import FieldCondition

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        mock_response = MagicMock()
        mock_response.points = []
        vs.client.query_points.return_value = mock_response

        await vs.search(
            query_vector=[0.1] * 10,
            tenant_id=TENANT_A_ID,
            collection_ids=[COLLECTION_ID],
        )

        call_kwargs = vs.client.query_points.call_args
        query_filter = call_kwargs.kwargs.get("query_filter") or call_kwargs[1].get("query_filter")
        # First must condition should be tenant_id
        tenant_filter = query_filter.must[0]
        assert tenant_filter.key == "tenant_id"
        assert tenant_filter.match.value == str(TENANT_A_ID)

    @pytest.mark.asyncio
    async def test_vector_search_tenant_b_uses_different_filter(self):
        """Searching as tenant B must use TENANT_B_ID in the filter."""
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        mock_response = MagicMock()
        mock_response.points = []
        vs.client.query_points.return_value = mock_response

        await vs.search(
            query_vector=[0.1] * 10,
            tenant_id=TENANT_B_ID,
            collection_ids=[COLLECTION_ID],
        )

        call_kwargs = vs.client.query_points.call_args
        query_filter = call_kwargs.kwargs.get("query_filter") or call_kwargs[1].get("query_filter")
        tenant_filter = query_filter.must[0]
        assert tenant_filter.match.value == str(TENANT_B_ID)


# ── Deletion Level: Cross-Tenant Vector Deletion ─────────────────


class TestDeletionCrossTenant:
    """Deletion methods now require tenant_id, preventing cross-tenant deletion."""

    @pytest.mark.asyncio
    async def test_delete_by_document_scoped_to_tenant(self):
        """delete_by_document only deletes vectors matching both document_id AND tenant_id."""
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        doc_id = uuid4()
        await vs.delete_by_document(doc_id, TENANT_A_ID)

        filter_arg = vs.client.delete.call_args.kwargs["points_selector"]
        filter_keys = {c.key for c in filter_arg.must}
        assert "document_id" in filter_keys
        assert "tenant_id" in filter_keys

        # Verify the tenant_id value is correct
        tenant_cond = next(c for c in filter_arg.must if c.key == "tenant_id")
        assert tenant_cond.match.value == str(TENANT_A_ID)

    @pytest.mark.asyncio
    async def test_delete_by_dossier_scoped_to_tenant(self):
        """delete_by_dossier only deletes vectors matching both dossier_id AND tenant_id."""
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        await vs.delete_by_dossier(DOSSIER_A_ID, TENANT_A_ID)

        filter_arg = vs.client.delete.call_args.kwargs["points_selector"]
        tenant_cond = next(c for c in filter_arg.must if c.key == "tenant_id")
        assert tenant_cond.match.value == str(TENANT_A_ID)

    @pytest.mark.asyncio
    async def test_delete_by_collection_scoped_to_tenant(self):
        """delete_by_collection only deletes vectors matching both collection_id AND tenant_id."""
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        await vs.delete_by_collection(COLLECTION_ID, TENANT_B_ID)

        filter_arg = vs.client.delete.call_args.kwargs["points_selector"]
        tenant_cond = next(c for c in filter_arg.must if c.key == "tenant_id")
        assert tenant_cond.match.value == str(TENANT_B_ID)


# ── Conversation Level: Cross-Tenant ─────────────────────────────


class TestConversationCrossTenant:
    """Conversations are filtered by user_id which is tenant-scoped."""

    def test_dossier_conversations_filtered_by_user(self):
        """GET /dossiers/{id}/conversations only returns requesting user's conversations."""
        _setup_tenant_user(TENANT_B_ID, USER_B_ID)

        db = mock_db()
        # Dossier ownership check: dossier belongs to another user
        dossier_b_other = fake_dossier(user_id=USER_A_ID, tenant_id=TENANT_B_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dossier_b_other
        db.execute.return_value = mock_result

        async def _fake_db():
            yield db
        app.dependency_overrides[get_db] = _fake_db

        with TestClient(app) as client:
            response = client.get(f"/api/v1/dossiers/{DOSSIER_A_ID}/conversations")
        # _ensure_owner blocks access
        assert response.status_code == 404
