"""Postgres Full-Text Search keyword retriever."""

import logging
import re
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)


def _build_or_tsquery(query: str, fts_config: str) -> str:
    """Build an OR-based tsquery from user query words.

    Using OR instead of AND so that chunks matching any query term
    are returned, with ranking favoring chunks matching more terms.
    """
    words = re.findall(r"\w+", query.lower())
    if not words:
        return ""
    # Sanitize: only keep alphanumeric words (no SQL injection)
    safe_words = [w for w in words if re.match(r"^[\w]+$", w)]
    if not safe_words:
        return ""
    return " | ".join(safe_words)


async def keyword_search(
    db: AsyncSession,
    tenant_id: UUID,
    collection_ids: list[UUID] | None,
    query: str,
    topk: int,
    fts_config: str = "simple",
) -> list[RetrievedChunk]:
    """Search chunks using Postgres full-text search.

    Uses OR-based tsquery + ts_rank_cd for ranking.
    Chunks matching any query word are returned; more matches = higher rank.
    Filters on denormalized tenant_id and collection_id columns.
    """
    if not query.strip():
        return []

    # Validate fts_config to prevent SQL injection (must be a known PG text search config)
    allowed_configs = {"simple", "english", "french", "german", "spanish", "pg_catalog.simple"}
    if fts_config not in allowed_configs:
        fts_config = "simple"

    or_tsquery = _build_or_tsquery(query, fts_config)
    if not or_tsquery:
        return []

    # Build the collection filter clause
    if collection_ids is not None:
        collection_filter = "AND c.collection_id = ANY(CAST(:collection_ids AS uuid[]))"
        params: dict = {
            "tenant_id": str(tenant_id),
            "collection_ids": [str(cid) for cid in collection_ids],
            "topk": topk,
        }
    else:
        collection_filter = ""
        params = {
            "tenant_id": str(tenant_id),
            "topk": topk,
        }

    # or_tsquery is built from sanitized words above (no user-controlled SQL).
    sql = text(f"""
        SELECT
            CAST(c.id AS text) AS chunk_id,
            CAST(c.document_id AS text) AS document_id,
            c.content,
            c.page_number,
            c.start_offset,
            c.end_offset,
            c.section_title,
            ts_rank_cd(c.content_tsv, to_tsquery('{fts_config}', '{or_tsquery}')) AS rank
        FROM chunks c
        WHERE c.tenant_id = CAST(:tenant_id AS uuid)
          {collection_filter}
          AND c.content_tsv @@ to_tsquery('{fts_config}', '{or_tsquery}')
        ORDER BY rank DESC
        LIMIT :topk
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    chunks = []
    for row in rows:
        chunks.append(RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_filename="",  # Will be enriched later if needed
            content=row.content,
            page_number=row.page_number,
            section_title=row.section_title,
            score=float(row.rank),
        ))

    logger.debug("Keyword search returned %d results for query: %s", len(chunks), query[:80])
    return chunks
