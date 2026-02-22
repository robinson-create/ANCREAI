"""Retrieval orchestrator: hybrid search + rerank pipeline."""

import asyncio
import logging
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.retrieval.hybrid import rrf_merge
from app.core.retrieval.keyword_retriever import keyword_search
from app.core.retrieval.reranker import RerankProviderError
from app.core.retrieval.reranker_factory import get_fallback_reranker, get_reranker
from app.core.retrieval.vector_retriever import vector_search
from app.services.embedding import embedding_service
from app.services.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)
settings = get_settings()


async def retrieve_context(
    db: AsyncSession,
    tenant_id: UUID,
    collection_ids: list[UUID] | None,
    query: str,
    include_web: bool = False,
) -> list[RetrievedChunk]:
    """Full hybrid retrieval pipeline: keyword + vector [+ web] -> RRF -> rerank.

    Steps:
    1) Embed query
    2) Keyword search + Vector search [+ Web search] in parallel
    3) RRF merge (2 or 3 sources)
    4) Rerank (with fallback), or just take top-N from RRF
    """
    t0 = time.perf_counter()

    # 1) Embed query
    query_embedding = await embedding_service.embed_query(query)
    t_embed = time.perf_counter()

    # 2) Run searches in parallel
    keyword_task = keyword_search(
        db=db,
        tenant_id=tenant_id,
        collection_ids=collection_ids,
        query=query,
        topk=settings.hybrid_keyword_topk,
        fts_config=settings.postgres_fts_config,
    )
    vector_task = vector_search(
        tenant_id=tenant_id,
        collection_ids=collection_ids,
        query_embedding=query_embedding,
        topk=settings.hybrid_vector_topk,
    )

    tasks: list = [keyword_task, vector_task]

    # Optional web search as third source
    web_chunks: list[RetrievedChunk] = []
    if include_web and settings.web_search_enabled:
        from app.core.tools.web_search_tool import web_results_to_chunks
        from app.services.web_search import search_web

        async def _web_task() -> list[RetrievedChunk]:
            resp = await search_web(query=query, db=db)
            return web_results_to_chunks(resp.results)

        tasks.append(_web_task())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    keyword_results = results[0] if not isinstance(results[0], Exception) else []
    vector_results = results[1] if not isinstance(results[1], Exception) else []
    if len(results) > 2 and not isinstance(results[2], Exception):
        web_chunks = results[2]

    t_search = time.perf_counter()

    if isinstance(results[0], Exception):
        logger.warning("keyword_search_failed", error=str(results[0]))
    if isinstance(results[1], Exception):
        logger.warning("vector_search_failed", error=str(results[1]))
    if len(results) > 2 and isinstance(results[2], Exception):
        logger.warning("web_search_failed", error=str(results[2]))

    logger.info(
        "Hybrid search: %d keyword + %d vector + %d web results",
        len(keyword_results),
        len(vector_results),
        len(web_chunks),
    )

    # 3) RRF merge (2 or 3 sources)
    merged = rrf_merge(
        keyword_results, vector_results,
        k=settings.hybrid_rrf_k,
        web_results=web_chunks or None,
    )
    candidates = merged[: settings.rerank_max_candidates]

    # 4) Rerank (with fallback)
    if not settings.rerank_enabled or not candidates:
        t_end = time.perf_counter()
        logger.info(
            "Retrieval timing: embed=%.0fms search=%.0fms total=%.0fms (no rerank)",
            (t_embed - t0) * 1000, (t_search - t_embed) * 1000, (t_end - t0) * 1000,
        )
        return candidates[: settings.rerank_final_topn]

    reranker = get_reranker()
    if reranker:
        try:
            reranked = await reranker.rerank(query, candidates, topn=settings.rerank_final_topn)
            t_rerank = time.perf_counter()
            logger.info(
                "Retrieval timing: embed=%.0fms search=%.0fms rerank=%.0fms total=%.0fms (provider=%s)",
                (t_embed - t0) * 1000, (t_search - t_embed) * 1000,
                (t_rerank - t_search) * 1000, (t_rerank - t0) * 1000, reranker.name(),
            )
            return reranked
        except RerankProviderError as e:
            logger.warning("Primary reranker (%s) failed: %s", reranker.name(), e)

            fallback = get_fallback_reranker()
            if fallback:
                try:
                    reranked = await fallback.rerank(
                        query, candidates, topn=settings.rerank_final_topn
                    )
                    t_rerank = time.perf_counter()
                    logger.info(
                        "Retrieval timing: embed=%.0fms search=%.0fms rerank=%.0fms total=%.0fms (fallback=%s)",
                        (t_embed - t0) * 1000, (t_search - t_embed) * 1000,
                        (t_rerank - t_search) * 1000, (t_rerank - t0) * 1000, fallback.name(),
                    )
                    return reranked
                except RerankProviderError as e2:
                    logger.warning("Fallback reranker (%s) failed: %s", fallback.name(), e2)

    # Ultimate fallback: RRF order
    t_end = time.perf_counter()
    logger.info(
        "Retrieval timing: embed=%.0fms search=%.0fms total=%.0fms (rrf fallback)",
        (t_embed - t0) * 1000, (t_search - t_embed) * 1000, (t_end - t0) * 1000,
    )
    return candidates[: settings.rerank_final_topn]
