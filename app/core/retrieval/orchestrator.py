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
) -> list[RetrievedChunk]:
    """Full hybrid retrieval pipeline: keyword + vector -> RRF -> rerank.

    Steps:
    1) Embed query
    2) Keyword search (Postgres FTS) + Vector search (Qdrant) in parallel
    3) RRF merge
    4) Rerank (with fallback), or just take top-N from RRF
    """
    t0 = time.perf_counter()

    # 1) Embed query
    query_embedding = await embedding_service.embed_query(query)
    t_embed = time.perf_counter()

    # 2) Run keyword + vector search in parallel
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

    keyword_results, vector_results = await asyncio.gather(keyword_task, vector_task)
    t_search = time.perf_counter()

    logger.info(
        "Hybrid search: %d keyword + %d vector results",
        len(keyword_results),
        len(vector_results),
    )

    # 3) RRF merge
    merged = rrf_merge(keyword_results, vector_results, k=settings.hybrid_rrf_k)
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
