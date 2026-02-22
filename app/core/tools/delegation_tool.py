"""Delegation tool — delegate a sub-query to another assistant.

The parent agent calls `delegate_to_assistant` when it needs specialized
knowledge from a different assistant (e.g., a finance assistant asking a
legal assistant for contract details).

The delegation runs inline: it queries the target assistant's collections
and synthesizes a response, consuming budget from the parent's reservation.

Delegation constraints per profile:
- balanced: 1 delegation max, 600-800 tokens budget
- pro/exec: 2 delegations max, 800-1200 tokens each
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.budget import BudgetManager
from app.core.logging import get_logger
from app.core.tool_registry import ToolCategory, ToolDefinition, tool_registry

logger = get_logger(__name__)
settings = get_settings()

# ── Delegation budget caps per profile ───────────────────────────

_DELEGATION_CAPS: dict[str, dict] = {
    "balanced": {"max_delegations": 1, "max_tokens_per": 800},
    "pro": {"max_delegations": 2, "max_tokens_per": 1200},
    "exec": {"max_delegations": 2, "max_tokens_per": 1200},
}


def delegation_budget_cap(profile: str) -> dict:
    """Return delegation constraints for a profile."""
    return _DELEGATION_CAPS.get(profile, {"max_delegations": 0, "max_tokens_per": 0})


# ── OpenAI function-calling schema ──────────────────────────────────

DELEGATE_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "delegate_to_assistant",
        "description": (
            "Délègue une sous-question à un autre assistant spécialisé. "
            "Utilise cet outil quand tu as besoin d'informations provenant "
            "des documents d'un autre assistant (ex: poser une question juridique "
            "à l'assistant juridique, ou financière à l'assistant finance)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_assistant_id": {
                    "type": "string",
                    "description": "L'ID de l'assistant cible à qui déléguer la question.",
                },
                "query": {
                    "type": "string",
                    "description": "La question à poser à l'assistant cible.",
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Contexte court pour aider l'assistant cible "
                        "(ex: 'Dans le cadre du projet X, je cherche...')."
                    ),
                },
                "expected_output": {
                    "type": "string",
                    "description": (
                        "Description de ce que tu attends comme réponse "
                        "(ex: 'Un résumé des clauses pertinentes')."
                    ),
                },
            },
            "required": ["target_assistant_id", "query"],
        },
    },
}


# ── Handler ─────────────────────────────────────────────────────────


async def handle_delegate_to_assistant(
    *,
    args: dict,
    tenant_id: UUID,
    assistant_id: UUID | None = None,
    budget: BudgetManager | None = None,
    profile: str = "balanced",
    db: AsyncSession | None = None,
) -> dict:
    """Execute a delegation to another assistant.

    Steps:
    1. Validate delegation constraints (profile limits, budget)
    2. Load target assistant and its collections
    3. Reserve budget from parent
    4. Run retrieval on target's collections
    5. Synthesize response via LLM
    6. Release unused budget
    7. Return normalized result with citations
    """
    from app.database import async_session_maker
    from app.models.assistant import Assistant
    from app.services.retrieval import retrieval_service

    target_id_str = args.get("target_assistant_id", "")
    query = args.get("query", "")
    context = args.get("context", "")
    expected_output = args.get("expected_output", "")

    if not target_id_str or not query:
        return _error_result("Missing target_assistant_id or query")

    try:
        target_id = UUID(target_id_str)
    except ValueError:
        return _error_result(f"Invalid assistant ID: {target_id_str}")

    # Validate delegation is allowed for this profile
    caps = delegation_budget_cap(profile)
    if caps["max_delegations"] == 0:
        return _error_result(f"Profile '{profile}' does not support delegation")

    # Reserve budget
    reservation = None
    if budget:
        token_cap = caps["max_tokens_per"]
        try:
            reservation = budget.reserve(f"delegate_{target_id_str[:8]}", token_cap)
        except Exception as e:
            return _error_result(f"Budget reservation failed: {e}")

    try:
        # Load target assistant
        if db is not None:
            session = db
        else:
            session = await async_session_maker().__aenter__()

        try:
            result = await session.execute(
                select(Assistant)
                .options(selectinload(Assistant.collections))
                .where(Assistant.id == target_id)
                .where(Assistant.tenant_id == tenant_id)
            )
            target_assistant = result.scalar_one_or_none()

            if not target_assistant:
                return _error_result(f"Target assistant not found: {target_id_str}")

            collection_ids = [c.id for c in target_assistant.collections]

            if not collection_ids:
                return _error_result("Target assistant has no collections")

            # Run retrieval on target's collections
            chunks = await retrieval_service.retrieve(
                query=query,
                tenant_id=tenant_id,
                collection_ids=collection_ids,
                top_k=5,
                db=session,
            )

            if not chunks:
                return _delegation_result(
                    target_id=target_id_str,
                    target_name=target_assistant.name,
                    answer="Aucune information pertinente trouvée dans les documents de cet assistant.",
                    citations=[],
                    confidence=0.0,
                )

            # Build context and synthesize via LLM
            context_text = retrieval_service.build_context(chunks, max_tokens=2000)

            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.mistral_api_key,
                base_url="https://api.mistral.ai/v1",
            )

            synthesis_prompt = (
                f"Tu es l'assistant '{target_assistant.name}'. "
                f"Réponds à la question suivante en te basant uniquement sur le contexte fourni.\n\n"
            )
            if context:
                synthesis_prompt += f"Contexte de la demande: {context}\n\n"
            if expected_output:
                synthesis_prompt += f"Format attendu: {expected_output}\n\n"
            synthesis_prompt += f"Contexte documentaire:\n{context_text}"

            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": synthesis_prompt},
                    {"role": "user", "content": query},
                ],
                max_tokens=caps["max_tokens_per"],
                temperature=0.2,
            )

            answer = response.choices[0].message.content or ""
            tokens_used = (response.usage.total_tokens or 0) if response.usage else 0

            # Consume from reservation
            if reservation:
                reservation.consume(min(tokens_used, reservation.remaining))

            # Build citations from chunks
            citations = [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "document_filename": c.document_filename,
                    "page_number": c.page_number,
                    "excerpt": c.content[:200],
                    "score": c.score,
                    "source_assistant_id": target_id_str,
                }
                for c in chunks
            ]

            logger.info(
                "delegation_completed",
                target_id=target_id_str,
                target_name=target_assistant.name,
                chunks_found=len(chunks),
                tokens_used=tokens_used,
            )

            return _delegation_result(
                target_id=target_id_str,
                target_name=target_assistant.name,
                answer=answer,
                citations=citations,
                confidence=chunks[0].score if chunks else 0.0,
                tokens_used=tokens_used,
            )

        finally:
            if db is None:
                await session.__aexit__(None, None, None)

    finally:
        # Release unused budget
        if reservation and budget:
            budget.release(reservation)


# ── Result helpers ──────────────────────────────────────────────────


def _delegation_result(
    *,
    target_id: str,
    target_name: str,
    answer: str,
    citations: list[dict],
    confidence: float = 0.0,
    tokens_used: int = 0,
    notes: str = "",
) -> dict:
    """Build normalized delegation result."""
    return {
        "target_assistant_id": target_id,
        "target_assistant_name": target_name,
        "answer_text": answer,
        "citations": citations,
        "confidence": confidence,
        "tokens_used": tokens_used,
        "notes": notes,
    }


def _error_result(message: str) -> dict:
    """Build delegation error result."""
    return {
        "error": message,
        "answer_text": "",
        "citations": [],
        "confidence": 0.0,
    }


# ── Registration ────────────────────────────────────────────────────


def register_delegation_tool() -> None:
    """Register the delegate_to_assistant tool in the global registry."""
    tool_registry.register(
        ToolDefinition(
            name="delegate_to_assistant",
            category=ToolCategory.DELEGATION,
            description="Delegate a sub-query to another specialized assistant",
            openai_schema=DELEGATE_SCHEMA,
            continues_loop=True,
            min_profile="balanced",
            timeout_seconds=60,
        ),
        handler=handle_delegate_to_assistant,
    )
