"""Tests for scope isolation in the retrieval pipeline.

Verifies that org/personal boundaries are never leaked:
- Empty scope returns nothing (not a tenant-wide search)
- collection_ids filter only org chunks
- dossier_ids filter only personal chunks
- Mixed scope produces correct OR filter
"""

from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import UUID, uuid4

import pytest

from tests.conftest import (
    TENANT_A_ID,
    COLLECTION_ID,
    DOSSIER_A_ID,
    fake_chunk,
    mock_db,
)


# ── Keyword Retriever ─────────────────────────────────────────────


class TestKeywordSearchScope:
    """Tests for keyword_retriever scope filtering."""

    @pytest.mark.asyncio
    async def test_empty_scope_returns_empty(self):
        """No collection_ids and no dossier_ids must return [] (not search all)."""
        from app.core.retrieval.keyword_retriever import keyword_search

        db = mock_db()
        result = await keyword_search(
            db=db,
            tenant_id=TENANT_A_ID,
            collection_ids=None,
            query="test query",
            topk=10,
            dossier_ids=None,
        )
        assert result == []
        # DB should NOT be queried
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_lists_returns_empty(self):
        """Empty lists (not None) must also return []."""
        from app.core.retrieval.keyword_retriever import keyword_search

        db = mock_db()
        result = await keyword_search(
            db=db,
            tenant_id=TENANT_A_ID,
            collection_ids=[],
            query="test query",
            topk=10,
            dossier_ids=[],
        )
        assert result == []
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_org_only_includes_collection_filter(self):
        """collection_ids only must produce scope='org' filter in SQL."""
        from app.core.retrieval.keyword_retriever import keyword_search

        db = mock_db()
        # Return empty result set
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result

        await keyword_search(
            db=db,
            tenant_id=TENANT_A_ID,
            collection_ids=[COLLECTION_ID],
            query="test",
            topk=5,
        )

        # Verify the SQL was executed and contains scope='org'
        assert db.execute.called
        called_sql = str(db.execute.call_args[0][0])
        assert "scope = 'org'" in called_sql
        assert "collection_id" in called_sql

    @pytest.mark.asyncio
    async def test_personal_only_includes_dossier_filter(self):
        """dossier_ids only must produce scope='personal' filter."""
        from app.core.retrieval.keyword_retriever import keyword_search

        db = mock_db()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result

        await keyword_search(
            db=db,
            tenant_id=TENANT_A_ID,
            collection_ids=None,
            query="test",
            topk=5,
            dossier_ids=[DOSSIER_A_ID],
        )

        called_sql = str(db.execute.call_args[0][0])
        assert "scope = 'personal'" in called_sql
        assert "dossier_id" in called_sql

    @pytest.mark.asyncio
    async def test_mixed_scope_produces_or(self):
        """Both collection_ids and dossier_ids must produce OR clause."""
        from app.core.retrieval.keyword_retriever import keyword_search

        db = mock_db()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result

        await keyword_search(
            db=db,
            tenant_id=TENANT_A_ID,
            collection_ids=[COLLECTION_ID],
            query="test",
            topk=5,
            dossier_ids=[DOSSIER_A_ID],
        )

        called_sql = str(db.execute.call_args[0][0])
        assert "scope = 'org'" in called_sql
        assert "scope = 'personal'" in called_sql
        assert "OR" in called_sql


# ── Vector Store Search ───────────────────────────────────────────


class TestVectorStoreSearchScope:
    """Tests for vector_store.search() scope filtering."""

    @pytest.mark.asyncio
    async def test_empty_scope_returns_empty(self):
        """No collection_ids and no dossier_ids must return [] (safe default)."""
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        result = await vs.search(
            query_vector=[0.1] * 10,
            tenant_id=TENANT_A_ID,
            collection_ids=None,
            dossier_ids=None,
        )
        assert result == []
        vs.client.query_points.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_lists_returns_empty(self):
        """Empty lists must also return []."""
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        result = await vs.search(
            query_vector=[0.1] * 10,
            tenant_id=TENANT_A_ID,
            collection_ids=[],
            dossier_ids=[],
        )
        assert result == []
        vs.client.query_points.assert_not_called()

    @pytest.mark.asyncio
    async def test_dossier_filter_in_query(self):
        """dossier_ids must appear in the Qdrant query filter."""
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        mock_response = MagicMock()
        mock_response.points = []
        vs.client.query_points.return_value = mock_response

        await vs.search(
            query_vector=[0.1] * 10,
            tenant_id=TENANT_A_ID,
            dossier_ids=[DOSSIER_A_ID],
        )

        assert vs.client.query_points.called
        call_kwargs = vs.client.query_points.call_args
        query_filter = call_kwargs.kwargs.get("query_filter") or call_kwargs[1].get("query_filter")
        # The filter should have must conditions including tenant_id + scope
        assert query_filter is not None

    @pytest.mark.asyncio
    async def test_mixed_scope_produces_should_filter(self):
        """Both collection_ids and dossier_ids must produce a 'should' filter."""
        from app.core.vector_store import VectorStore
        from qdrant_client.models import Filter

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
            dossier_ids=[DOSSIER_A_ID],
        )

        assert vs.client.query_points.called
        call_kwargs = vs.client.query_points.call_args
        query_filter = call_kwargs.kwargs.get("query_filter") or call_kwargs[1].get("query_filter")
        # Must have 2 must conditions: tenant_id + Filter(should=[...])
        assert len(query_filter.must) == 2
        # The second must is a Filter with should conditions
        scope_filter = query_filter.must[1]
        assert isinstance(scope_filter, Filter)
        assert len(scope_filter.should) == 2  # one for collection, one for dossier


# ── Vector Store Deletion Tenant Isolation ────────────────────────


class TestVectorStoreDeletionTenantId:
    """Tests that all deletion methods require and use tenant_id."""

    @pytest.mark.asyncio
    async def test_delete_by_document_includes_tenant_filter(self):
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        doc_id = uuid4()
        await vs.delete_by_document(doc_id, TENANT_A_ID)

        assert vs.client.delete.called
        filter_arg = vs.client.delete.call_args.kwargs["points_selector"]
        must_keys = [c.key for c in filter_arg.must]
        assert "document_id" in must_keys
        assert "tenant_id" in must_keys

    @pytest.mark.asyncio
    async def test_delete_by_collection_includes_tenant_filter(self):
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        await vs.delete_by_collection(COLLECTION_ID, TENANT_A_ID)

        filter_arg = vs.client.delete.call_args.kwargs["points_selector"]
        must_keys = [c.key for c in filter_arg.must]
        assert "collection_id" in must_keys
        assert "tenant_id" in must_keys

    @pytest.mark.asyncio
    async def test_delete_by_dossier_includes_tenant_filter(self):
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        await vs.delete_by_dossier(DOSSIER_A_ID, TENANT_A_ID)

        filter_arg = vs.client.delete.call_args.kwargs["points_selector"]
        must_keys = [c.key for c in filter_arg.must]
        assert "dossier_id" in must_keys
        assert "tenant_id" in must_keys

    @pytest.mark.asyncio
    async def test_delete_by_dossier_document_includes_tenant_filter(self):
        from app.core.vector_store import VectorStore

        vs = VectorStore.__new__(VectorStore)
        vs.client = AsyncMock()
        vs.collection_name = "test"

        dossier_doc_id = uuid4()
        await vs.delete_by_dossier_document(dossier_doc_id, TENANT_A_ID)

        filter_arg = vs.client.delete.call_args.kwargs["points_selector"]
        must_keys = [c.key for c in filter_arg.must]
        assert "dossier_document_id" in must_keys
        assert "tenant_id" in must_keys


# ── Orchestrator passes dossier_ids ───────────────────────────────


class TestOrchestratorDossierPropagation:
    """Verify dossier_ids is passed through the retrieval chain."""

    @pytest.mark.asyncio
    async def test_orchestrator_passes_dossier_ids(self):
        """dossier_ids must be forwarded to both keyword and vector retrievers."""
        with patch("app.core.retrieval.orchestrator.keyword_search", new_callable=AsyncMock) as mock_kw, \
             patch("app.core.retrieval.orchestrator.vector_search", new_callable=AsyncMock) as mock_vec:

            mock_kw.return_value = []
            mock_vec.return_value = []

            from app.core.retrieval.orchestrator import retrieve_context

            db = mock_db()
            await retrieve_context(
                db=db,
                query="test",
                tenant_id=TENANT_A_ID,
                collection_ids=[COLLECTION_ID],
                dossier_ids=[DOSSIER_A_ID],
            )

            # Both retrievers must receive dossier_ids
            kw_kwargs = mock_kw.call_args.kwargs
            assert kw_kwargs.get("dossier_ids") == [DOSSIER_A_ID]

            vec_kwargs = mock_vec.call_args.kwargs
            assert vec_kwargs.get("dossier_ids") == [DOSSIER_A_ID]
