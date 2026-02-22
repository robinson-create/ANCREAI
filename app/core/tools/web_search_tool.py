"""Web search tool — agent-callable web search with WebVerifyCard output.

The agent calls `search_web` when it needs information beyond the
internal knowledge base. Results are converted to RetrievedChunks for
cross-merge with RAG results, and a WebVerifyCard block is emitted
for the frontend.
"""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from app.core.logging import get_logger
from app.core.tool_registry import ToolCategory, ToolDefinition, tool_registry
from app.services.retrieval import RetrievedChunk

logger = get_logger(__name__)

# ── OpenAI function-calling schema ──────────────────────────────────

WEB_SEARCH_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": (
            "Recherche sur le web pour trouver des informations récentes ou "
            "complémentaires non disponibles dans la base documentaire interne. "
            "Utilise cet outil quand la base interne ne contient pas assez "
            "d'information pour répondre, ou quand l'utilisateur demande "
            "explicitement des données web/actuelles."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La requête de recherche web.",
                },
            },
            "required": ["query"],
        },
    },
}


# ── Convert web results to RetrievedChunks ───────────────────────


def web_results_to_chunks(
    results: list,
) -> list[RetrievedChunk]:
    """Convert WebSearchResult objects to RetrievedChunks for RRF merge."""
    chunks = []
    for r in results:
        # Synthetic chunk_id from URL hash
        url_hash = hashlib.sha256(r.url.encode()).hexdigest()[:16]
        chunk_id = f"web_{url_hash}"

        chunks.append(RetrievedChunk(
            chunk_id=chunk_id,
            document_id=f"web:{r.url}",
            document_filename=r.source_label,
            content=f"{r.title}\n\n{r.snippet}",
            page_number=None,
            section_title=r.title,
            score=r.score,
        ))

    return chunks


# ── Format web results for LLM context ──────────────────────────


def format_web_results_for_llm(results: list) -> str:
    """Format web search results into a context string for the LLM."""
    if not results:
        return "Aucun résultat web trouvé."

    parts = []
    for i, r in enumerate(results, 1):
        source = r.source_label
        part = f"[Source web {i}: {source}]\n{r.title}\n{r.snippet}\nURL: {r.url}"
        parts.append(part)

    return "\n\n---\n\n".join(parts)


# ── Build WebVerifyCard block ────────────────────────────────────


def build_web_verify_block(results: list, query: str) -> dict:
    """Build a WebVerifyCard block payload for the frontend."""
    return {
        "id": str(uuid4()),
        "type": "web_verify",
        "payload": {
            "query": query,
            "sources": [
                {
                    "url": r.url,
                    "title": r.title,
                    "domain": r.source_label,
                    "snippet": r.snippet[:200],
                }
                for r in results
            ],
            "source_count": len(results),
        },
    }


# ── Handler ─────────────────────────────────────────────────────────


async def handle_search_web(
    *,
    query: str,
    tenant_id: UUID,
    **kwargs,
) -> dict:
    """Execute web search and return results + block.

    Returns a dict with:
    - type: "web_verify"
    - payload: WebVerifyCard data
    - _web_results: raw results for cross-merge (internal, not sent to frontend)
    """
    from app.services.web_search import search_web

    response = await search_web(query=query)

    if not response.results:
        logger.info("web_search_no_results", query=query[:80])
        return {
            "type": "web_verify",
            "payload": {
                "query": query,
                "sources": [],
                "source_count": 0,
            },
            "_web_results": [],
            "_formatted": "Aucun résultat web trouvé pour cette requête.",
        }

    block = build_web_verify_block(response.results, query)

    logger.info(
        "web_search_tool_completed",
        query=query[:80],
        result_count=len(response.results),
        cached=response.cached,
    )

    return {
        **block,
        "_web_results": response.results,
        "_formatted": format_web_results_for_llm(response.results),
    }


# ── Registration ────────────────────────────────────────────────────


def register_web_search_tool() -> None:
    """Register the search_web tool in the global registry."""
    tool_registry.register(
        ToolDefinition(
            name="search_web",
            category=ToolCategory.RETRIEVAL,
            description="Search the web for recent or complementary information",
            openai_schema=WEB_SEARCH_SCHEMA,
            continues_loop=True,
            min_profile="balanced",
            timeout_seconds=15,
        ),
        handler=handle_search_web,
    )
