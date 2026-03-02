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
    dossier_ids: list[UUID] | None = None,
) -> list[RetrievedChunk]:
    """Search chunks using Postgres full-text search.

    Uses OR-based tsquery + ts_rank_cd for ranking.
    Supports mixed org + personal scope:
    - collection_ids → org-scope chunks
    - dossier_ids → personal-scope chunks
    When both are provided, results from either scope are returned (OR).
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

    # Build scope filter (OR between org collections and personal dossiers)
    params: dict = {
        "tenant_id": str(tenant_id),
        "topk": topk,
    }

    scope_clauses: list[str] = []
    if collection_ids is not None and collection_ids:
        scope_clauses.append(
            "(c.scope = 'org' AND c.collection_id = ANY(CAST(:collection_ids AS uuid[])))"
        )
        params["collection_ids"] = [str(cid) for cid in collection_ids]

    if dossier_ids is not None and dossier_ids:
        scope_clauses.append(
            "(c.scope = 'personal' AND c.dossier_id = ANY(CAST(:dossier_ids AS uuid[])))"
        )
        params["dossier_ids"] = [str(did) for did in dossier_ids]

    if not scope_clauses:
        logger.warning("keyword_search_no_scope", extra={
            "tenant_id": str(tenant_id),
        })
        return []
    else:
        scope_filter = "AND (" + " OR ".join(scope_clauses) + ")"

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
          {scope_filter}
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
            document_id=row.document_id or "",
            document_filename="",  # Will be enriched later if needed
            content=row.content,
            page_number=row.page_number,
            section_title=row.section_title,
            score=float(row.rank),
        ))

    logger.debug("Keyword search returned %d results for query: %s", len(chunks), query[:80])
    return chunks
