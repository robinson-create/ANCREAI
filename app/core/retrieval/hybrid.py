"""Reciprocal Rank Fusion (RRF) for hybrid search."""

from __future__ import annotations

from app.services.retrieval import RetrievedChunk


def rrf_merge(
    keyword_results: list[RetrievedChunk],
    vector_results: list[RetrievedChunk],
    k: int = 60,
    web_results: list[RetrievedChunk] | None = None,
) -> list[RetrievedChunk]:
    """Merge search results using Reciprocal Rank Fusion.

    fused_score = sum( 1/(k + rank) ) across sources, rank starting at 1.
    Supports 2 sources (keyword + vector) or 3 sources (+ web).
    Returns merged list sorted descending by fused_score.
    """
    chunk_map: dict[str, RetrievedChunk] = {}
    score_map: dict[str, float] = {}

    def _accumulate(results: list[RetrievedChunk]) -> None:
        for rank, chunk in enumerate(results, start=1):
            cid = chunk.chunk_id
            score_map[cid] = score_map.get(cid, 0.0) + 1.0 / (k + rank)
            if cid not in chunk_map or (not chunk_map[cid].document_filename and chunk.document_filename):
                chunk_map[cid] = chunk

    _accumulate(keyword_results)
    _accumulate(vector_results)
    if web_results:
        _accumulate(web_results)

    # Sort by fused score descending
    sorted_ids = sorted(score_map, key=lambda cid: score_map[cid], reverse=True)

    merged = []
    for cid in sorted_ids:
        chunk = chunk_map[cid]
        chunk.fused_score = score_map[cid]
        merged.append(chunk)

    return merged
