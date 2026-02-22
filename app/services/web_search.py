"""Web search service — query external search APIs with caching.

Supports multiple providers (Brave, Serper, Tavily) behind a unified
interface. Results are cached in web_cache table with configurable TTL.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ── Result model ──────────────────────────────────────────────────


@dataclass
class WebSearchResult:
    """A single web search result."""

    url: str
    title: str
    snippet: str
    domain: str = ""
    published_date: str | None = None
    score: float = 0.0  # Provider relevance score (normalized 0-1)

    @property
    def source_label(self) -> str:
        return self.domain or self.url.split("/")[2] if "/" in self.url else self.url


@dataclass
class WebSearchResponse:
    """Full response from a web search query."""

    query: str
    results: list[WebSearchResult] = field(default_factory=list)
    provider: str = ""
    cached: bool = False
    fetched_at: datetime | None = None


# ── Cache helpers ─────────────────────────────────────────────────


def _query_hash(query: str) -> str:
    """Deterministic hash for cache lookup."""
    normalized = query.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


async def _get_cached(
    db: AsyncSession,
    query: str,
    provider: str,
) -> WebSearchResponse | None:
    """Check web_cache for a valid (non-expired) result."""
    from app.models.web_cache import WebCache

    qh = _query_hash(query)
    now = datetime.now(UTC)

    result = await db.execute(
        select(WebCache)
        .where(WebCache.query_hash == qh)
        .where(WebCache.provider == provider)
        .where(WebCache.expires_at > now)
    )
    cached = result.scalar_one_or_none()
    if not cached:
        return None

    # Deserialize cached results
    results = [
        WebSearchResult(**r) for r in cached.results_json.get("results", [])
    ]

    return WebSearchResponse(
        query=query,
        results=results,
        provider=provider,
        cached=True,
        fetched_at=cached.fetched_at,
    )


async def _save_cache(
    db: AsyncSession,
    query: str,
    provider: str,
    response: WebSearchResponse,
) -> None:
    """Save search results to web_cache (upsert by query_hash + provider)."""
    from app.models.web_cache import WebCache

    qh = _query_hash(query)
    ttl_hours = settings.web_cache_ttl_hours
    now = datetime.now(UTC)

    # Check if exists
    result = await db.execute(
        select(WebCache)
        .where(WebCache.query_hash == qh)
        .where(WebCache.provider == provider)
    )
    existing = result.scalar_one_or_none()

    serialized = {
        "results": [
            {
                "url": r.url,
                "title": r.title,
                "snippet": r.snippet,
                "domain": r.domain,
                "published_date": r.published_date,
                "score": r.score,
            }
            for r in response.results
        ]
    }

    if existing:
        existing.results_json = serialized
        existing.result_count = len(response.results)
        existing.fetched_at = now
        existing.expires_at = now + timedelta(hours=ttl_hours)
    else:
        entry = WebCache(
            query_hash=qh,
            query=query,
            provider=provider,
            results_json=serialized,
            result_count=len(response.results),
            fetched_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
        db.add(entry)

    await db.flush()


# ── Provider clients ──────────────────────────────────────────────


async def _search_brave(
    query: str,
    top_k: int,
) -> list[WebSearchResult]:
    """Search via Brave Search API."""
    async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": settings.web_search_api_key,
            },
            params={
                "q": query,
                "count": top_k,
                "text_decorations": "false",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for i, item in enumerate(data.get("web", {}).get("results", [])[:top_k]):
        results.append(WebSearchResult(
            url=item.get("url", ""),
            title=item.get("title", ""),
            snippet=item.get("description", ""),
            domain=item.get("meta_url", {}).get("hostname", ""),
            published_date=item.get("page_age"),
            score=1.0 - (i / max(top_k, 1)),  # Rank-based score
        ))

    return results


async def _search_serper(
    query: str,
    top_k: int,
) -> list[WebSearchResult]:
    """Search via Serper.dev API."""
    async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": settings.web_search_api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": top_k},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for i, item in enumerate(data.get("organic", [])[:top_k]):
        results.append(WebSearchResult(
            url=item.get("link", ""),
            title=item.get("title", ""),
            snippet=item.get("snippet", ""),
            domain=item.get("domain", ""),
            score=1.0 - (i / max(top_k, 1)),
        ))

    return results


async def _search_tavily(
    query: str,
    top_k: int,
) -> list[WebSearchResult]:
    """Search via Tavily API."""
    async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.web_search_api_key,
                "query": query,
                "max_results": top_k,
                "include_answer": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for i, item in enumerate(data.get("results", [])[:top_k]):
        url = item.get("url", "")
        results.append(WebSearchResult(
            url=url,
            title=item.get("title", ""),
            snippet=item.get("content", ""),
            domain=url.split("/")[2] if url.count("/") >= 2 else "",
            published_date=item.get("published_date"),
            score=item.get("score", 1.0 - (i / max(top_k, 1))),
        ))

    return results


_PROVIDERS = {
    "brave": _search_brave,
    "serper": _search_serper,
    "tavily": _search_tavily,
}


# ── Main entry point ─────────────────────────────────────────────


async def search_web(
    query: str,
    *,
    top_k: int | None = None,
    db: AsyncSession | None = None,
) -> WebSearchResponse:
    """Search the web with caching.

    Args:
        query: Search query string.
        top_k: Max results (defaults to settings.web_search_topk).
        db: DB session for cache read/write. If None, skips cache.

    Returns:
        WebSearchResponse with results and metadata.
    """
    if not settings.web_search_enabled or not settings.web_search_api_key:
        logger.debug("web_search_disabled")
        return WebSearchResponse(query=query, provider="none")

    provider = settings.web_search_provider
    k = top_k or settings.web_search_topk

    # Check cache
    if db is not None:
        cached = await _get_cached(db, query, provider)
        if cached:
            logger.info(
                "web_search_cache_hit",
                query=query[:80],
                result_count=len(cached.results),
            )
            return cached

    # Call provider
    search_fn = _PROVIDERS.get(provider)
    if not search_fn:
        logger.error("web_search_unknown_provider", provider=provider)
        return WebSearchResponse(query=query, provider=provider)

    try:
        results = await search_fn(query, k)
    except Exception as e:
        logger.warning("web_search_failed", provider=provider, error=str(e))
        return WebSearchResponse(query=query, provider=provider)

    response = WebSearchResponse(
        query=query,
        results=results,
        provider=provider,
        fetched_at=datetime.now(UTC),
    )

    # Save to cache
    if db is not None and results:
        try:
            await _save_cache(db, query, provider, response)
        except Exception as e:
            logger.warning("web_cache_save_failed", error=str(e))

    logger.info(
        "web_search_completed",
        query=query[:80],
        provider=provider,
        result_count=len(results),
    )

    return response
