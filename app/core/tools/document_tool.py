"""Document creation tool — creates a workspace document from chat context.

The agent calls `createDocument` when the conversation produces structured
content that would benefit from being persisted as a workspace document
(proposals, reports, summaries, contracts, etc.).

The tool creates a WorkspaceDocument with initial content blocks generated
from the chat context and RAG sources, then returns a block payload for
the frontend to render a DocSuggestionCard.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.tool_registry import ToolCategory, ToolDefinition, tool_registry

logger = get_logger(__name__)

# ── OpenAI function-calling schema ──────────────────────────────────

CREATE_DOCUMENT_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "createDocument",
        "strict": True,
        "description": (
            "Crée un document structuré à partir du contexte de la conversation. "
            "Utilise cet outil quand la réponse contient du contenu structuré "
            "qui gagnerait à être sauvegardé comme document de travail : "
            "proposition commerciale, compte-rendu, synthèse, contrat, rapport."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Titre du document à créer",
                },
                "doc_type": {
                    "type": "string",
                    "enum": [
                        "generic",
                        "proposal",
                        "report",
                        "summary",
                        "contract",
                        "meeting_notes",
                        "letter",
                    ],
                    "description": "Type de document",
                },
                "content_html": {
                    "type": "string",
                    "description": (
                        "Contenu initial du document en HTML structuré. "
                        "Utilise : <h1>, <h2>, <h3>, <p>, <ul>, <ol>, <li>, "
                        "<strong>, <em>, <blockquote>, <table>, <tr>, <td>, <th>. "
                        "Structure le contenu avec des titres et sections claires."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "Explication courte de pourquoi ce document est suggéré "
                        "(ex: 'Cette synthèse peut être transformée en document de travail')"
                    ),
                },
            },
            "required": ["title", "doc_type", "content_html", "reason"],
            "additionalProperties": False,
        },
    },
}


# ── Handler ─────────────────────────────────────────────────────────


def _html_to_prosemirror(html: str) -> dict:
    """Convert simple HTML content to a minimal ProseMirror/TipTap doc.

    This is a lightweight conversion for initial document creation.
    The frontend TipTap editor will normalize the structure on load.
    """
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": html}],
            }
        ],
    }


async def handle_create_document(
    *,
    args: dict,
    tenant_id: UUID,
    assistant_id: UUID | None = None,
    conversation_id: UUID | None = None,
    citations: list | None = None,
    db: AsyncSession | None = None,
) -> dict:
    """Create a WorkspaceDocument and return the block payload.

    This handler is invoked by the agent loop when the LLM emits a
    `createDocument` function call. It persists the document server-side
    and returns a block for the frontend to render a DocSuggestionCard.
    """
    from app.database import async_session_maker
    from app.models.workspace_document import WorkspaceDocument

    title = args.get("title", "Sans titre")
    doc_type = args.get("doc_type", "generic")
    content_html = args.get("content_html", "")
    reason = args.get("reason", "")

    # Build initial DocModel content
    content_json = {
        "version": 1,
        "meta": {"doc_type": doc_type},
        "blocks": [
            {
                "type": "rich_text",
                "id": str(uuid4()),
                "label": title,
                "content": _html_to_prosemirror(content_html),
            }
        ],
        "variables": {},
        "sources": [
            {
                "chunk_id": c.get("chunk_id", ""),
                "document_id": c.get("document_id", ""),
                "document_filename": c.get("document_filename", ""),
                "page_number": c.get("page_number"),
                "excerpt": c.get("excerpt", ""),
                "score": c.get("score", 0),
            }
            for c in (citations or [])
            if isinstance(c, dict)
        ],
    }

    doc = WorkspaceDocument(
        tenant_id=tenant_id,
        assistant_id=assistant_id,
        title=title,
        doc_type=doc_type,
        content_json=content_json,
    )

    if db is not None:
        db.add(doc)
        await db.flush()
        doc_id = doc.id
    else:
        async with async_session_maker() as session:
            session.add(doc)
            await session.commit()
            doc_id = doc.id

    logger.info(
        "document_created_from_chat",
        doc_id=str(doc_id),
        title=title[:80],
        doc_type=doc_type,
    )

    return {
        "id": str(uuid4()),
        "type": "doc_suggestion",
        "payload": {
            "document_id": str(doc_id),
            "title": title,
            "doc_type": doc_type,
            "reason": reason,
        },
    }


# ── Registration ────────────────────────────────────────────────────


def register_document_tool() -> None:
    """Register the createDocument tool in the global registry."""
    tool_registry.register(
        ToolDefinition(
            name="createDocument",
            category=ToolCategory.BLOCK,
            description="Create a workspace document from chat context",
            openai_schema=CREATE_DOCUMENT_SCHEMA,
            block_type="doc_suggestion",
            continues_loop=False,
            min_profile="reactive",
        ),
        handler=handle_create_document,
    )
