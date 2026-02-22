"""Internal retrieval tool — wraps hybrid search as an agent-callable tool.

Registered in the tool registry with category=RETRIEVAL.
The agent loop calls this tool when the LLM emits a `search_documents`
function call, returning context chunks that feed back into the next turn.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.tool_registry import ToolCategory, ToolDefinition, tool_registry
from app.services.retrieval import RetrievedChunk, retrieval_service

logger = get_logger(__name__)

# ── OpenAI function-calling schema ──────────────────────────────────

RETRIEVAL_TOOL_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Search the knowledge base for relevant documents. "
            "Use this when you need information from uploaded documents "
            "to answer the user's question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant documents.",
                },
            },
            "required": ["query"],
        },
    },
}


# ── Handler ─────────────────────────────────────────────────────────


async def handle_search_documents(
    *,
    query: str,
    tenant_id: UUID,
    collection_ids: list[UUID] | None = None,
    db: AsyncSession | None = None,
    top_k: int = 10,
) -> list[RetrievedChunk]:
    """Execute the retrieval pipeline and return chunks.

    This is the handler invoked by the agent loop when the LLM calls
    `search_documents`.
    """
    logger.info(
        "retrieval_tool_invoked",
        query=query[:100],
        collection_count=len(collection_ids) if collection_ids else 0,
    )

    chunks = await retrieval_service.retrieve(
        query=query,
        tenant_id=tenant_id,
        collection_ids=collection_ids,
        top_k=top_k,
        db=db,
    )

    logger.info(
        "retrieval_tool_completed",
        chunks_returned=len(chunks),
        top_score=chunks[0].score if chunks else 0.0,
    )

    return chunks


def format_chunks_for_llm(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks into a context string for the LLM."""
    return retrieval_service.build_context(chunks)


# ── Registration ────────────────────────────────────────────────────


def register_retrieval_tool() -> None:
    """Register the search_documents tool in the global registry."""
    tool_registry.register(
        ToolDefinition(
            name="search_documents",
            category=ToolCategory.RETRIEVAL,
            description="Search the knowledge base for relevant documents",
            openai_schema=RETRIEVAL_TOOL_SCHEMA,
            continues_loop=True,
            min_profile="reactive",
            timeout_seconds=30,
        ),
    )
