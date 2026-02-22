"""Email suggestion tool — creates an EmailDraftBundle from chat context.

The agent calls `suggestEmail` when the response contains actionable content
the user may want to send as an email (summary, follow-up, proposal, etc.).
The tool creates a server-side bundle and returns a block payload for the
frontend to render an EmailSuggestionCard.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.core.logging import get_logger
from app.core.tool_registry import ToolCategory, ToolDefinition, tool_registry

logger = get_logger(__name__)

# ── OpenAI function-calling schema ──────────────────────────────────

SUGGEST_EMAIL_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "suggestEmail",
        "strict": True,
        "description": (
            "Suggère la création d'un email à partir de ta réponse. "
            "Utilise cet outil quand ta réponse contient un contenu actionable "
            "que l'utilisateur pourrait vouloir envoyer par email : suivi, "
            "synthèse, relance, proposition commerciale, compte-rendu, "
            "ou quand l'utilisateur demande explicitement d'écrire/envoyer un email."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Sujet proposé pour l'email",
                },
                "body_draft": {
                    "type": "string",
                    "description": (
                        "Brouillon du corps de l'email en HTML compatible Gmail. "
                        "Utilise uniquement : <p>, <br>, <strong>, <em>, <ul>, "
                        "<ol>, <li>, <a href>. Pas de CSS, pas de Markdown. "
                        "Commence directement par la salutation."
                    ),
                },
                "tone": {
                    "type": "string",
                    "enum": ["formal", "friendly", "neutral"],
                    "description": "Ton suggéré pour l'email",
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "Explication courte de pourquoi cet email est suggéré "
                        "(ex: 'Cette synthèse peut être envoyée à vos collaborateurs')"
                    ),
                },
            },
            "required": ["subject", "body_draft", "tone", "reason"],
            "additionalProperties": False,
        },
    },
}


# ── Handler ─────────────────────────────────────────────────────────


async def handle_suggest_email(
    *,
    args: dict,
    tenant_id: UUID,
    conversation_id: UUID | None = None,
    citations: list | None = None,
) -> dict:
    """Create an EmailDraftBundle in DB and return the block payload.

    This handler is invoked by the agent loop when the LLM emits a
    `suggestEmail` function call. It persists the suggestion server-side
    and returns a block for the frontend to render.
    """
    from app.database import async_session_maker
    from app.models.mail import EmailDraftBundle

    bundle = EmailDraftBundle(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        subject=args.get("subject"),
        body_draft=args.get("body_draft"),
        tone=args.get("tone"),
        reason=args.get("reason"),
        citations=citations,
    )
    async with async_session_maker() as db:
        db.add(bundle)
        await db.commit()
        bundle_id = bundle.id

    logger.info(
        "email_bundle_created",
        bundle_id=str(bundle_id),
        subject=args.get("subject", "")[:80],
    )

    return {
        "id": str(uuid4()),
        "type": "email_suggestion",
        "payload": {
            "bundle_id": str(bundle_id),
            "subject": args.get("subject", ""),
            "reason": args.get("reason", ""),
            "tone": args.get("tone", "neutral"),
        },
    }


# ── Registration ────────────────────────────────────────────────────


def register_email_tool() -> None:
    """Register the suggestEmail tool in the global registry."""
    tool_registry.register(
        ToolDefinition(
            name="suggestEmail",
            category=ToolCategory.EMAIL,
            description="Suggest transforming response into an email",
            openai_schema=SUGGEST_EMAIL_SCHEMA,
            block_type="email_suggestion",
            continues_loop=False,
            min_profile="reactive",
        ),
        handler=handle_suggest_email,
    )
