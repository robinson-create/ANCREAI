"""Qdrant vector retriever wrapper."""

import logging
from uuid import UUID

from app.core.vector_store import vector_store
from app.services.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)


async def vector_search(
    tenant_id: UUID,
    collection_ids: list[UUID] | None,
    query_embedding: list[float],
    topk: int,
) -> list[RetrievedChunk]:
    """Search chunks using Qdrant vector similarity.

    Wraps the existing VectorStore.search() and maps results to RetrievedChunk.
    """
    results = await vector_store.search(
        query_vector=query_embedding,
        tenant_id=tenant_id,
        collection_ids=collection_ids,
        limit=topk,
        score_threshold=0.0,
    )

    chunks = []
    for result in results:
        payload = result["payload"]
        chunks.append(RetrievedChunk(
            chunk_id=result["id"],
            document_id=payload.get("document_id", ""),
            document_filename=payload.get("document_filename", ""),
            content=payload.get("content", ""),
            page_number=payload.get("page_number"),
            section_title=payload.get("section_title"),
            score=result["score"],
        ))

    logger.debug("Vector search returned %d results", len(chunks))
    return chunks
