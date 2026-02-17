"""Tests for hybrid retrieval: RRF merge, rerankers, keyword search."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.retrieval.hybrid import rrf_merge
from app.core.retrieval.reranker import RerankProviderError
from app.core.retrieval.reranker_hf import HFEndpointReranker
from app.core.retrieval.reranker_mistral import MistralReranker
from app.services.retrieval import RetrievedChunk


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _chunk(chunk_id: str, score: float = 0.5, content: str = "test") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        document_filename="test.pdf",
        content=content,
        page_number=1,
        section_title=None,
        score=score,
    )


# ─── RRF Merge Tests ─────────────────────────────────────────────────────────

class TestRRFMerge:
    def test_empty_inputs(self):
        result = rrf_merge([], [], k=60)
        assert result == []

    def test_single_source_keyword_only(self):
        keyword = [_chunk("a", 0.9), _chunk("b", 0.7)]
        result = rrf_merge(keyword, [], k=60)
        assert len(result) == 2
        assert result[0].chunk_id == "a"
        assert result[1].chunk_id == "b"
        assert result[0].fused_score > result[1].fused_score

    def test_single_source_vector_only(self):
        vector = [_chunk("x", 0.95), _chunk("y", 0.8)]
        result = rrf_merge([], vector, k=60)
        assert len(result) == 2
        assert result[0].chunk_id == "x"

    def test_overlap_boosts_score(self):
        """Chunks appearing in both sources should have higher fused score."""
        keyword = [_chunk("a"), _chunk("b"), _chunk("c")]
        vector = [_chunk("b"), _chunk("d"), _chunk("a")]

        result = rrf_merge(keyword, vector, k=60)
        ids = [c.chunk_id for c in result]

        # "a" and "b" appear in both → should be ranked higher
        # "a" is rank 1 in keyword + rank 3 in vector
        # "b" is rank 2 in keyword + rank 1 in vector
        # Both should beat single-source chunks
        assert "a" in ids[:3]
        assert "b" in ids[:3]

    def test_deterministic(self):
        """Same inputs always produce same output."""
        kw = [_chunk("a"), _chunk("b")]
        vec = [_chunk("b"), _chunk("c")]

        r1 = rrf_merge(kw, vec, k=60)
        r2 = rrf_merge(kw, vec, k=60)

        assert [c.chunk_id for c in r1] == [c.chunk_id for c in r2]
        assert [c.fused_score for c in r1] == [c.fused_score for c in r2]

    def test_fused_score_formula(self):
        """Verify RRF formula: score = sum(1/(k+rank))."""
        k = 60
        kw = [_chunk("a")]
        vec = [_chunk("a")]

        result = rrf_merge(kw, vec, k=k)
        # "a" is rank 1 in both sources
        expected = 1 / (k + 1) + 1 / (k + 1)
        assert abs(result[0].fused_score - expected) < 1e-10

    def test_prefers_vector_chunk_with_filename(self):
        """When a chunk appears in both, prefer the version with filename."""
        kw_chunk = RetrievedChunk(
            chunk_id="a", document_id="d1", document_filename="",
            content="x", page_number=1, section_title=None, score=0.5,
        )
        vec_chunk = RetrievedChunk(
            chunk_id="a", document_id="d1", document_filename="report.pdf",
            content="x", page_number=1, section_title=None, score=0.5,
        )
        result = rrf_merge([kw_chunk], [vec_chunk], k=60)
        assert result[0].document_filename == "report.pdf"


# ─── HF Reranker Tests ───────────────────────────────────────────────────────

class TestHFReranker:
    @pytest.mark.asyncio
    async def test_successful_rerank(self):
        reranker = HFEndpointReranker()
        candidates = [_chunk("a", content="Hello"), _chunk("b", content="World")]

        # TEI /rerank returns a list of {index, score}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [
            {"index": 1, "score": 0.95},
            {"index": 0, "score": 0.4},
        ]

        with patch("app.core.retrieval.reranker_hf.settings") as mock_settings:
            mock_settings.hf_rerank_url = "http://test-endpoint"
            mock_settings.hf_rerank_token = "test-token"
            mock_settings.rerank_timeout_seconds = 5
            mock_settings.rerank_retry_max = 0
            mock_settings.rerank_max_passage_chars = 1500

            with patch("app.core.retrieval.reranker_hf.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                result = await reranker.rerank("test query", candidates, topn=2)

        assert len(result) == 2
        assert result[0].chunk_id == "b"
        assert result[0].rerank_score == 0.95
        assert result[1].chunk_id == "a"

    @pytest.mark.asyncio
    async def test_no_url_raises(self):
        reranker = HFEndpointReranker()

        with patch("app.core.retrieval.reranker_hf.settings") as mock_settings:
            mock_settings.hf_rerank_url = ""

            with pytest.raises(RerankProviderError, match="not configured"):
                await reranker.rerank("query", [_chunk("a")], topn=1)

    @pytest.mark.asyncio
    async def test_invalid_schema_raises(self):
        reranker = HFEndpointReranker()

        # TEI expects a list, not a dict
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"wrong": "schema"}

        with patch("app.core.retrieval.reranker_hf.settings") as mock_settings:
            mock_settings.hf_rerank_url = "http://test"
            mock_settings.hf_rerank_token = ""
            mock_settings.rerank_timeout_seconds = 5
            mock_settings.rerank_retry_max = 0
            mock_settings.rerank_max_passage_chars = 1500

            with patch("app.core.retrieval.reranker_hf.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                with pytest.raises(RerankProviderError, match="Invalid"):
                    await reranker.rerank("query", [_chunk("a")], topn=1)


# ─── Mistral Reranker Tests ──────────────────────────────────────────────────

class TestMistralReranker:
    @pytest.mark.asyncio
    async def test_successful_rerank(self):
        reranker = MistralReranker()
        candidates = [_chunk("a"), _chunk("b")]

        ranking_json = json.dumps({
            "ranking": [
                {"chunk_id": "b", "score": 0.9},
                {"chunk_id": "a", "score": 0.3},
            ]
        })

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": ranking_json}}]
        }

        with patch("app.core.retrieval.reranker_mistral.settings") as mock_settings:
            mock_settings.mistral_api_key = "test-key"
            mock_settings.rerank_mistral_model = "mistral-small"
            mock_settings.rerank_mistral_timeout_seconds = 8
            mock_settings.rerank_max_passage_chars = 1500
            mock_settings.rerank_temperature = 0.0

            with patch("app.core.retrieval.reranker_mistral.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                result = await reranker.rerank("query", candidates, topn=2)

        assert len(result) == 2
        assert result[0].chunk_id == "b"
        assert result[0].rerank_score == 0.9

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self):
        reranker = MistralReranker()

        with patch("app.core.retrieval.reranker_mistral.settings") as mock_settings:
            mock_settings.mistral_api_key = ""

            with pytest.raises(RerankProviderError, match="not configured"):
                await reranker.rerank("query", [_chunk("a")], topn=1)

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self):
        reranker = MistralReranker()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not valid json"}}]
        }

        with patch("app.core.retrieval.reranker_mistral.settings") as mock_settings:
            mock_settings.mistral_api_key = "test-key"
            mock_settings.rerank_mistral_model = "mistral-small"
            mock_settings.rerank_mistral_timeout_seconds = 8
            mock_settings.rerank_max_passage_chars = 1500
            mock_settings.rerank_temperature = 0.0

            with patch("app.core.retrieval.reranker_mistral.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                with pytest.raises(RerankProviderError, match="invalid JSON"):
                    await reranker.rerank("query", [_chunk("a")], topn=1)


# ─── Keyword Retriever SQL Tests ─────────────────────────────────────────────

class TestKeywordSearchQuery:
    """Test that keyword_search builds valid SQL (basic smoke test)."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        from app.core.retrieval.keyword_retriever import keyword_search

        mock_db = AsyncMock()
        result = await keyword_search(
            db=mock_db,
            tenant_id="00000000-0000-0000-0000-000000000001",
            collection_ids=None,
            query="",
            topk=10,
            fts_config="simple",
        )
        assert result == []
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_db_execute(self):
        from app.core.retrieval.keyword_retriever import keyword_search

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await keyword_search(
            db=mock_db,
            tenant_id="00000000-0000-0000-0000-000000000001",
            collection_ids=None,
            query="test search",
            topk=10,
            fts_config="simple",
        )

        assert result == []
        mock_db.execute.assert_called_once()
