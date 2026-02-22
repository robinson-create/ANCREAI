"""Tests for PR6: Web search service, RRF cross-merge, web search tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.retrieval.hybrid import rrf_merge
from app.services.retrieval import RetrievedChunk
from app.services.web_search import (
    WebSearchResponse,
    WebSearchResult,
    _query_hash,
)

# ── Helper ─────────────────────────────────────────────────────────


def _make_chunk(chunk_id: str, score: float = 0.5, filename: str = "doc.pdf") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=f"doc_{chunk_id}",
        document_filename=filename,
        content=f"Content for {chunk_id}",
        page_number=1,
        section_title=None,
        score=score,
    )


def _make_web_result(url: str = "https://example.com", title: str = "Example", snippet: str = "Snippet text") -> WebSearchResult:
    return WebSearchResult(
        url=url,
        title=title,
        snippet=snippet,
        domain="example.com",
        score=0.9,
    )


# ── WebSearchResult model ─────────────────────────────────────────


class TestWebSearchResult:
    def test_source_label_from_domain(self):
        r = WebSearchResult(url="https://example.com/page", title="T", snippet="S", domain="example.com")
        assert r.source_label == "example.com"

    def test_source_label_fallback_from_url(self):
        r = WebSearchResult(url="https://test.org/path", title="T", snippet="S")
        assert r.source_label == "test.org"

    def test_defaults(self):
        r = WebSearchResult(url="https://a.com", title="A", snippet="B")
        assert r.domain == ""
        assert r.published_date is None
        assert r.score == 0.0


# ── Query hash ────────────────────────────────────────────────────


class TestQueryHash:
    def test_deterministic(self):
        h1 = _query_hash("test query")
        h2 = _query_hash("test query")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = _query_hash("Test Query")
        h2 = _query_hash("test query")
        assert h1 == h2

    def test_strips_whitespace(self):
        h1 = _query_hash("  test query  ")
        h2 = _query_hash("test query")
        assert h1 == h2

    def test_is_sha256(self):
        h = _query_hash("hello")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ── RRF merge with web results ───────────────────────────────────


class TestRRFMergeWithWeb:
    def test_two_sources_still_works(self):
        kw = [_make_chunk("c1"), _make_chunk("c2")]
        vec = [_make_chunk("c2"), _make_chunk("c3")]
        merged = rrf_merge(kw, vec, k=60)
        ids = [c.chunk_id for c in merged]
        assert "c1" in ids
        assert "c2" in ids
        assert "c3" in ids
        # c2 appears in both → highest fused score
        assert merged[0].chunk_id == "c2"

    def test_three_sources_merges_correctly(self):
        kw = [_make_chunk("c1"), _make_chunk("c2")]
        vec = [_make_chunk("c2"), _make_chunk("c3")]
        web = [_make_chunk("c4", filename="web.com"), _make_chunk("c2", filename="web.com")]
        merged = rrf_merge(kw, vec, k=60, web_results=web)
        ids = [c.chunk_id for c in merged]
        assert "c1" in ids
        assert "c2" in ids
        assert "c3" in ids
        assert "c4" in ids
        # c2 in all 3 sources → highest fused score
        assert merged[0].chunk_id == "c2"
        assert merged[0].fused_score is not None

    def test_web_only_results(self):
        kw: list[RetrievedChunk] = []
        vec: list[RetrievedChunk] = []
        web = [_make_chunk("w1"), _make_chunk("w2")]
        merged = rrf_merge(kw, vec, k=60, web_results=web)
        assert len(merged) == 2
        assert merged[0].fused_score > 0

    def test_none_web_results(self):
        kw = [_make_chunk("c1")]
        vec = [_make_chunk("c2")]
        merged = rrf_merge(kw, vec, k=60, web_results=None)
        assert len(merged) == 2

    def test_three_sources_fused_score_higher(self):
        """A chunk in 3 sources should score higher than one in 2."""
        kw = [_make_chunk("a"), _make_chunk("b")]
        vec = [_make_chunk("a"), _make_chunk("b")]
        web = [_make_chunk("a")]
        merged = rrf_merge(kw, vec, k=60, web_results=web)
        scores = {c.chunk_id: c.fused_score for c in merged}
        assert scores["a"] > scores["b"]


# ── Web search service ────────────────────────────────────────────


class TestSearchWeb:
    @pytest.mark.asyncio
    async def test_disabled_returns_empty(self):
        from app.services.web_search import search_web

        with patch("app.services.web_search.settings") as mock_settings:
            mock_settings.web_search_enabled = False
            mock_settings.web_search_api_key = "key"
            result = await search_web("test query")

        assert result.results == []
        assert result.provider == "none"

    @pytest.mark.asyncio
    async def test_no_api_key_returns_empty(self):
        from app.services.web_search import search_web

        with patch("app.services.web_search.settings") as mock_settings:
            mock_settings.web_search_enabled = True
            mock_settings.web_search_api_key = ""
            result = await search_web("test query")

        assert result.results == []

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_empty(self):
        from app.services.web_search import search_web

        with patch("app.services.web_search.settings") as mock_settings:
            mock_settings.web_search_enabled = True
            mock_settings.web_search_api_key = "key"
            mock_settings.web_search_provider = "unknown_provider"
            mock_settings.web_search_topk = 5
            result = await search_web("test query")

        assert result.results == []
        assert result.provider == "unknown_provider"

    @pytest.mark.asyncio
    async def test_brave_provider_success(self):
        from app.services.web_search import search_web

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {
                        "url": "https://example.com/1",
                        "title": "Result 1",
                        "description": "Snippet 1",
                        "meta_url": {"hostname": "example.com"},
                    },
                    {
                        "url": "https://example.com/2",
                        "title": "Result 2",
                        "description": "Snippet 2",
                        "meta_url": {"hostname": "example.com"},
                    },
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.web_search.settings") as mock_settings,
            patch("app.services.web_search.httpx.AsyncClient", return_value=mock_client),
        ):
            mock_settings.web_search_enabled = True
            mock_settings.web_search_api_key = "test-key"
            mock_settings.web_search_provider = "brave"
            mock_settings.web_search_topk = 5
            mock_settings.web_search_timeout_seconds = 8
            result = await search_web("test query")

        assert len(result.results) == 2
        assert result.results[0].url == "https://example.com/1"
        assert result.results[0].title == "Result 1"
        assert result.provider == "brave"

    @pytest.mark.asyncio
    async def test_provider_failure_returns_empty(self):
        from app.services.web_search import search_web

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.web_search.settings") as mock_settings,
            patch("app.services.web_search.httpx.AsyncClient", return_value=mock_client),
        ):
            mock_settings.web_search_enabled = True
            mock_settings.web_search_api_key = "key"
            mock_settings.web_search_provider = "brave"
            mock_settings.web_search_topk = 5
            mock_settings.web_search_timeout_seconds = 8
            result = await search_web("test query")

        assert result.results == []


# ── Web search tool ───────────────────────────────────────────────


class TestWebSearchTool:
    def test_schema_structure(self):
        from app.core.tools.web_search_tool import WEB_SEARCH_SCHEMA

        assert WEB_SEARCH_SCHEMA["type"] == "function"
        func = WEB_SEARCH_SCHEMA["function"]
        assert func["name"] == "search_web"
        assert "query" in func["parameters"]["properties"]
        assert func["parameters"]["required"] == ["query"]

    def test_registration(self):
        from app.core.tool_registry import ToolCategory, ToolRegistry
        from app.core.tools.web_search_tool import register_web_search_tool

        reg = ToolRegistry()
        import app.core.tools.web_search_tool as mod
        original = mod.tool_registry
        mod.tool_registry = reg

        try:
            register_web_search_tool()
            tool = reg.get("search_web")
            assert tool is not None
            assert tool.category == ToolCategory.RETRIEVAL
            assert tool.continues_loop is True
            assert tool.min_profile == "balanced"
            assert reg.get_handler("search_web") is not None
        finally:
            mod.tool_registry = original


class TestWebResultsToChunks:
    def test_conversion(self):
        from app.core.tools.web_search_tool import web_results_to_chunks

        results = [
            _make_web_result("https://a.com/page1", "Title A", "Snippet A"),
            _make_web_result("https://b.com/page2", "Title B", "Snippet B"),
        ]
        chunks = web_results_to_chunks(results)
        assert len(chunks) == 2
        assert chunks[0].chunk_id.startswith("web_")
        assert chunks[0].document_id == "web:https://a.com/page1"
        assert "Title A" in chunks[0].content
        assert "Snippet A" in chunks[0].content
        assert chunks[0].page_number is None

    def test_empty_results(self):
        from app.core.tools.web_search_tool import web_results_to_chunks

        chunks = web_results_to_chunks([])
        assert chunks == []


class TestFormatWebResults:
    def test_format(self):
        from app.core.tools.web_search_tool import format_web_results_for_llm

        results = [_make_web_result("https://a.com", "Title", "Snippet")]
        text = format_web_results_for_llm(results)
        assert "Source web 1" in text
        assert "Title" in text
        assert "Snippet" in text
        assert "https://a.com" in text

    def test_empty(self):
        from app.core.tools.web_search_tool import format_web_results_for_llm

        text = format_web_results_for_llm([])
        assert "Aucun résultat" in text


class TestBuildWebVerifyBlock:
    def test_structure(self):
        from app.core.tools.web_search_tool import build_web_verify_block

        results = [
            _make_web_result("https://a.com", "A", "Snippet A"),
            _make_web_result("https://b.com", "B", "Snippet B"),
        ]
        block = build_web_verify_block(results, "test query")
        assert block["type"] == "web_verify"
        assert block["payload"]["query"] == "test query"
        assert block["payload"]["source_count"] == 2
        assert len(block["payload"]["sources"]) == 2
        assert block["payload"]["sources"][0]["url"] == "https://a.com"
        assert "id" in block


class TestWebSearchHandler:
    @pytest.mark.asyncio
    async def test_handler_with_results(self):
        from app.core.tools.web_search_tool import handle_search_web

        mock_response = WebSearchResponse(
            query="test",
            results=[
                _make_web_result("https://a.com", "A", "Snippet A"),
            ],
            provider="brave",
        )

        with patch("app.services.web_search.search_web", AsyncMock(return_value=mock_response)):
            result = await handle_search_web(query="test", tenant_id=uuid4())

        assert result["type"] == "web_verify"
        assert result["payload"]["source_count"] == 1
        assert "_formatted" in result
        assert "_web_results" in result
        assert len(result["_web_results"]) == 1

    @pytest.mark.asyncio
    async def test_handler_no_results(self):
        from app.core.tools.web_search_tool import handle_search_web

        mock_response = WebSearchResponse(query="nope", results=[], provider="brave")

        with patch("app.services.web_search.search_web", AsyncMock(return_value=mock_response)):
            result = await handle_search_web(query="nope", tenant_id=uuid4())

        assert result["type"] == "web_verify"
        assert result["payload"]["source_count"] == 0
        assert result["_web_results"] == []


# ── WebCache model ────────────────────────────────────────────────


class TestWebCacheModel:
    def test_model_import(self):
        from app.models.web_cache import WebCache

        assert WebCache.__tablename__ == "web_cache"

    def test_fields(self):
        from app.models.web_cache import WebCache

        columns = {c.name for c in WebCache.__table__.columns}
        assert "id" in columns
        assert "query_hash" in columns
        assert "query" in columns
        assert "provider" in columns
        assert "results_json" in columns
        assert "result_count" in columns
        assert "fetched_at" in columns
        assert "expires_at" in columns
