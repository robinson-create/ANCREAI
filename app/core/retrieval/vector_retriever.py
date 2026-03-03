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
    dossier_ids: list[UUID] | None = None,
    project_ids: list[UUID] | None = None,
    user_id: UUID | None = None,
) -> list[RetrievedChunk]:
    """Search chunks using Qdrant vector similarity.

    Supports org, personal, project, and personal-global scopes via
    collection_ids, dossier_ids, project_ids, and user_id.
    """
    results = await vector_store.search(
        query_vector=query_embedding,
        tenant_id=tenant_id,
        collection_ids=collection_ids,
        dossier_ids=dossier_ids,
        project_ids=project_ids,
        user_id=user_id,
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
