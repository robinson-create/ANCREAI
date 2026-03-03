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
    project_ids: list[UUID] | None = None,
    user_id: UUID | None = None,
) -> list[RetrievedChunk]:
    """Search chunks using Postgres full-text search.

    Uses OR-based tsquery + ts_rank_cd for ranking.
    Supports org, personal, project, and personal-global scopes:
    - collection_ids → org-scope chunks
    - dossier_ids → personal-scope chunks
    - project_ids → project-scope chunks
    - user_id (alone) → personal-global: ALL user chunks (personal + project)

    Scopes are mutually exclusive: user_id cannot be combined with
    collection_ids, dossier_ids, or project_ids.
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

    has_specific_scope = (
        (collection_ids is not None and len(collection_ids) > 0)
        or (dossier_ids is not None and len(dossier_ids) > 0)
        or (project_ids is not None and len(project_ids) > 0)
    )

    # Invariant #4: scopes mutually exclusive
    if user_id is not None and has_specific_scope:
        raise ValueError(
            "user_id (personal-global) cannot be combined with "
            "collection_ids, dossier_ids, or project_ids"
        )

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

    if project_ids is not None and project_ids:
        scope_clauses.append(
            "(c.scope = 'project' AND c.project_id = ANY(CAST(:project_ids AS uuid[])))"
        )
        params["project_ids"] = [str(pid) for pid in project_ids]

    # Personal-global: all user chunks (personal + project), invariants #5, #7, #8
    if user_id is not None and not scope_clauses:
        scope_clauses.append(
            "(c.user_id = CAST(:user_id AS uuid) AND c.scope IN ('personal', 'project'))"
        )
        params["user_id"] = str(user_id)

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
