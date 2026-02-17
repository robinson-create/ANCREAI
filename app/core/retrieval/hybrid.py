"""Reciprocal Rank Fusion (RRF) for hybrid search."""

from app.services.retrieval import RetrievedChunk


def rrf_merge(
    keyword_results: list[RetrievedChunk],
    vector_results: list[RetrievedChunk],
    k: int = 60,
) -> list[RetrievedChunk]:
    """Merge keyword and vector search results using Reciprocal Rank Fusion.

    fused_score = sum( 1/(k + rank) ) across sources, rank starting at 1.
    Returns merged list sorted descending by fused_score.
    """
    # Build map: chunk_id -> RetrievedChunk (keep the one with more info)
    chunk_map: dict[str, RetrievedChunk] = {}
    score_map: dict[str, float] = {}

    # Process keyword results
    for rank, chunk in enumerate(keyword_results, start=1):
        cid = chunk.chunk_id
        score_map[cid] = score_map.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in chunk_map:
            chunk_map[cid] = chunk

    # Process vector results
    for rank, chunk in enumerate(vector_results, start=1):
        cid = chunk.chunk_id
        score_map[cid] = score_map.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in chunk_map:
            chunk_map[cid] = chunk
        elif not chunk_map[cid].document_filename and chunk.document_filename:
            # Prefer the version with filename (from Qdrant payload)
            chunk_map[cid] = chunk

    # Sort by fused score descending
    sorted_ids = sorted(score_map, key=lambda cid: score_map[cid], reverse=True)

    merged = []
    for cid in sorted_ids:
        chunk = chunk_map[cid]
        chunk.fused_score = score_map[cid]
        merged.append(chunk)

    return merged
