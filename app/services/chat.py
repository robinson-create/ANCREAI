"""Chat service with RAG, streaming, Generative UI blocks, and integration tools."""

import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

from openai import AsyncOpenAI

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.schemas.chat import ChatStreamEvent, Citation
from app.services.retrieval import RetrievalService, RetrievedChunk
from app.integrations.nango.tools.registry import get_tools_for_provider, find_provider_for_tool
from app.integrations.nango.tools.executor import execute_integration_tool
from app.services.chat_tools.calendar_tools import get_calendar_tools, CALENDAR_SYSTEM_PROMPT_ADDITION
from app.services.chat_tools.calendar_handlers import (
    is_calendar_tool,
    execute_calendar_tool,
)

settings = get_settings()
logger = logging.getLogger(__name__)

# Maximum tool-calling iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 5

# ---------------------------------------------------------------------------
# Tool definitions for Generative UI blocks — one per block type
# ---------------------------------------------------------------------------
BLOCK_TOOL_KPI = {
    "type": "function",
    "function": {
        "name": "renderKpiCards",
        "strict": True,
        "description": "Affiche des cartes KPI. Utilise cet outil quand ta réponse contient des métriques, chiffres clés ou indicateurs.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": ["string", "null"], "description": "Titre optionnel du bloc KPI"},
                "items": {
                    "type": "array",
                    "description": "Liste des KPIs à afficher",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Nom du KPI"},
                            "value": {"type": "string", "description": "Valeur du KPI"},
                            "delta": {"type": ["string", "null"], "description": "Variation (ex: +5%, -2%)"},
                        },
                        "required": ["label", "value", "delta"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["title", "items"],
            "additionalProperties": False,
        },
    },
}

BLOCK_TOOL_TABLE = {
    "type": "function",
    "function": {
        "name": "renderTable",
        "strict": True,
        "description": "Affiche un tableau comparatif. Utilise cet outil quand ta réponse compare des options ou présente des données tabulaires.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": ["string", "null"], "description": "Titre optionnel du tableau"},
                "columns": {
                    "type": "array",
                    "description": "Noms des colonnes",
                    "items": {"type": "string"},
                },
                "rows": {
                    "type": "array",
                    "description": "Lignes du tableau (chaque ligne = array de strings)",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "required": ["title", "columns", "rows"],
            "additionalProperties": False,
        },
    },
}

BLOCK_TOOL_STEPS = {
    "type": "function",
    "function": {
        "name": "renderSteps",
        "strict": True,
        "description": "Affiche des étapes séquentielles. Utilise cet outil quand ta réponse décrit un plan, une procédure ou des étapes.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": ["string", "null"], "description": "Titre optionnel du bloc"},
                "steps": {
                    "type": "array",
                    "description": "Liste des étapes",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Titre de l'étape"},
                            "description": {"type": ["string", "null"], "description": "Description de l'étape"},
                        },
                        "required": ["title", "description"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["title", "steps"],
            "additionalProperties": False,
        },
    },
}

BLOCK_TOOL_CALLOUT = {
    "type": "function",
    "function": {
        "name": "renderCallout",
        "strict": True,
        "description": "Affiche une alerte ou un callout. Utilise cet outil pour alerter, avertir ou mettre en avant un point important.",
        "parameters": {
            "type": "object",
            "properties": {
                "tone": {
                    "type": "string",
                    "enum": ["info", "warning", "success", "danger"],
                    "description": "Ton du callout",
                },
                "title": {"type": ["string", "null"], "description": "Titre optionnel"},
                "message": {"type": "string", "description": "Message du callout"},
            },
            "required": ["tone", "title", "message"],
            "additionalProperties": False,
        },
    },
}

BLOCK_TOOL_EMAIL_SUGGESTION = {
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
                    "description": "Brouillon du corps de l'email en HTML compatible Gmail. Utilise uniquement : <p>, <br>, <strong>, <em>, <ul>, <ol>, <li>, <a href>. Pas de CSS, pas de Markdown. Commence directement par la salutation.",
                },
                "tone": {
                    "type": "string",
                    "enum": ["formal", "friendly", "neutral"],
                    "description": "Ton suggéré pour l'email",
                },
                "reason": {
                    "type": "string",
                    "description": "Explication courte de pourquoi cet email est suggéré (ex: 'Cette synthèse peut être envoyée à vos collaborateurs')",
                },
            },
            "required": ["subject", "body_draft", "tone", "reason"],
            "additionalProperties": False,
        },
    },
}

BLOCK_TOOLS = [BLOCK_TOOL_KPI, BLOCK_TOOL_TABLE, BLOCK_TOOL_STEPS, BLOCK_TOOL_CALLOUT, BLOCK_TOOL_EMAIL_SUGGESTION]

# Map tool function name → block type for the frontend
_TOOL_NAME_TO_BLOCK_TYPE = {
    "renderKpiCards": "kpi_cards",
    "renderTable": "table",
    "renderSteps": "steps",
    "renderCallout": "callout",
    "suggestEmail": "email_suggestion",
}

# Map calendar tool names → block types for the frontend
_CALENDAR_TOOL_TO_BLOCK_TYPE = {
    "calendar_parse_command": None,  # Returns command, not a block
    "calendar_execute_command": "calendar_event_card",  # Or other calendar blocks
    "calendar_list_events": "calendar_event_choices",
    "calendar_find_events": "calendar_event_choices",
}

BLOCK_INSTRUCTIONS = """
INSTRUCTIONS POUR LES BLOCS VISUELS :
Tu disposes de 5 outils pour afficher des blocs structurés dans le chat :
- `renderKpiCards` → quand ta réponse contient des KPIs, métriques ou chiffres comparatifs
- `renderSteps` → quand ta réponse décrit un plan, une procédure ou des étapes séquentielles
- `renderTable` → quand ta réponse compare des options ou présente des données tabulaires
- `renderCallout` → quand tu dois alerter, avertir ou mettre en avant un point important
- `suggestEmail` → quand ta réponse contient un contenu actionable que l'utilisateur pourrait envoyer par email (synthèse, suivi, relance, proposition, compte-rendu). Propose uniquement quand le contenu se prête clairement à un envoi par email. Ne suggère PAS pour des réponses purement informatives ou des questions.
Garde le texte concis et complémentaire ; mets la structure dans les blocs.
Ne pas inventer de données manquantes ; si une valeur n'est pas disponible, indique "N/A".
Tu peux combiner texte et plusieurs blocs dans une même réponse.
IMPORTANT : N'utilise JAMAIS de syntaxe markdown (**, *, #, etc.) dans les arguments des outils. Les blocs sont rendus en texte brut, pas en markdown.
"""


def _build_integration_instructions(integrations: list[dict]) -> str:
    """Build system prompt instructions for available integration tools."""
    if not integrations:
        return ""

    lines = ["\nOUTILS EXTERNES DISPONIBLES :"]
    lines.append("Tu as accès aux outils suivants pour interagir avec des systèmes externes.")
    lines.append("Utilise-les quand l'utilisateur demande des informations ou actions liées à ces systèmes.")
    lines.append("Les résultats sont renvoyés en JSON ; résume-les de façon lisible pour l'utilisateur.\n")

    for integration in integrations:
        provider = integration["provider"]
        tools = get_tools_for_provider(provider)
        for tool in tools:
            fn = tool["function"]
            lines.append(f"- `{fn['name']}` : {fn['description']}")

    return "\n".join(lines) + "\n"


class ChatService:
    """Service for RAG-powered chat with streaming."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.mistral_api_key,
            base_url="https://api.mistral.ai/v1",
        )
        self.retrieval = RetrievalService()
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    @staticmethod
    def _filter_relevant_chunks(
        chunks: list[RetrievedChunk],
        min_score: float,
    ) -> list[RetrievedChunk]:
        """Filter out chunks below the relevance threshold."""
        return [
            c for c in chunks
            if (c.rerank_score or c.fused_score or c.score) >= min_score
        ]

    def _build_system_prompt(
        self,
        custom_prompt: str | None,
        context: str,
        integrations: list[dict] | None = None,
        contact_context: str = "",
    ) -> str:
        """Build system prompt with context and integration instructions."""
        base_prompt = custom_prompt or (
            "Tu es un assistant utile et polyvalent. "
            "Tu peux répondre à des questions générales grâce à tes connaissances, "
            "ET utiliser le contexte documentaire fourni quand il est pertinent. "
            "Si un contexte documentaire est fourni, utilise-le UNIQUEMENT s'il est pertinent par rapport à la question. "
            "Si le contexte n'a aucun rapport avec la question, ignore-le complètement et réponds avec tes propres connaissances. "
            "Quand tu utilises des informations du contexte, cite tes sources (nom du document et numéro de page)."
        )

        if context:
            prompt = f"""{base_prompt}

Le contexte documentaire suivant est disponible. Utilise-le UNIQUEMENT s'il est pertinent pour répondre à la question. S'il n'a aucun rapport, ignore-le et réponds normalement.

CONTEXTE :
{context}

Rappel : cite tes sources (nom du document et page) uniquement quand tu utilises des informations du contexte."""
        else:
            prompt = base_prompt

        # Add contact context if available
        if contact_context:
            prompt += contact_context

        prompt += BLOCK_INSTRUCTIONS
        prompt += CALENDAR_SYSTEM_PROMPT_ADDITION
        prompt += _build_integration_instructions(integrations or [])

        return prompt

    def _build_tools_list(self, integrations: list[dict] | None = None) -> list[dict]:
        """Build the full tools list: block tools + calendar tools + integration tools."""
        tools = list(BLOCK_TOOLS)

        # Add calendar tools
        tools.extend(get_calendar_tools())

        # Add integration tools
        if integrations:
            for integration in integrations:
                provider = integration["provider"]
                tools.extend(get_tools_for_provider(provider))
        return tools

    def _is_block_tool(self, tool_name: str) -> bool:
        """Check if a tool name is a block (UI) tool vs an integration/calendar tool."""
        return (
            tool_name in _TOOL_NAME_TO_BLOCK_TYPE
            or tool_name in _CALENDAR_TOOL_TO_BLOCK_TYPE
        )

    def _extract_citations(
        self,
        chunks: list[RetrievedChunk],
        response_text: str,
    ) -> list[Citation]:
        """Extract citations from chunks that were likely used."""
        citations = []

        for chunk in chunks[:5]:  # Top 5 most relevant
            # Use rerank_score or fused_score if available, otherwise original score
            effective_score = chunk.rerank_score or chunk.fused_score or chunk.score
            if effective_score > 0.0:
                citations.append(Citation(
                    chunk_id=UUID(chunk.chunk_id),
                    document_id=UUID(chunk.document_id),
                    document_filename=chunk.document_filename,
                    page_number=chunk.page_number,
                    excerpt=chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                    score=effective_score,
                ))

        return citations

    @staticmethod
    def _parse_tool_calls_to_blocks(tool_calls: list) -> list[dict]:
        """Parse OpenAI tool_calls into block dicts (only for block/UI tools)."""
        blocks = []
        for tc in tool_calls:
            block_type = _TOOL_NAME_TO_BLOCK_TYPE.get(tc.function.name)
            if block_type is None:
                continue
            try:
                payload = json.loads(tc.function.arguments)
                blocks.append({
                    "id": str(uuid4()),
                    "type": block_type,
                    "payload": payload,
                })
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to parse %s args: %s", tc.function.name, e)
                blocks.append({
                    "id": str(uuid4()),
                    "type": "error",
                    "payload": {"message": str(e), "raw": tc.function.arguments[:200]},
                })
        return blocks

    @staticmethod
    async def _handle_suggest_email(
        args: dict,
        tenant_id: UUID,
        conversation_id: UUID | None = None,
        citations: list | None = None,
    ) -> dict:
        """Create an EmailDraftBundle in DB and return the block payload."""
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

    async def chat(
        self,
        message: str,
        tenant_id: UUID,
        collection_ids: list[UUID],
        system_prompt: str | None = None,
        conversation_history: list[dict] | None = None,
        integrations: list[dict] | None = None,
        db: AsyncSession | None = None,
        conversation_id: UUID | None = None,
    ) -> tuple[str, list[Citation], list[dict], int, int]:
        """
        Non-streaming chat with tool-calling loop.

        Returns:
            Tuple of (response, citations, blocks, tokens_input, tokens_output)
        """
        # Retrieve relevant chunks (hybrid if db provided, vector-only otherwise)
        chunks = []
        if collection_ids is not None and len(collection_ids) > 0:
            chunks = await self.retrieval.retrieve(
                query=message,
                tenant_id=tenant_id,
                collection_ids=collection_ids,
                db=db,
            )

        # Filter out low-relevance chunks to avoid polluting general questions
        chunks = self._filter_relevant_chunks(chunks, settings.rag_min_relevance_score)

        # Build context
        context = self.retrieval.build_context(chunks) if chunks else ""

        # Build messages
        messages = []
        messages.append({
            "role": "system",
            "content": self._build_system_prompt(system_prompt, context, integrations),
        })

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": message})

        all_tools = self._build_tools_list(integrations)
        total_input = 0
        total_output = 0
        all_blocks = []

        # Tool-calling loop
        for _ in range(MAX_TOOL_ITERATIONS):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                tools=all_tools if all_tools else None,
                # parallel_tool_calls=True,  # Not supported by Mistral API
            )

            total_input += response.usage.prompt_tokens if response.usage else 0
            total_output += response.usage.completion_tokens if response.usage else 0

            choice = response.choices[0]
            assistant_msg = choice.message

            if not assistant_msg.tool_calls:
                # No tool calls → we have the final response
                response_text = assistant_msg.content or ""
                break

            # Process tool calls
            messages.append(assistant_msg.model_dump())

            has_integration_calls = False
            for tc in assistant_msg.tool_calls:
                if tc.function.name == "suggestEmail":
                    # Email suggestion: create bundle in DB, emit block with bundle_id
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    try:
                        block = await self._handle_suggest_email(
                            args=args,
                            tenant_id=tenant_id,
                            conversation_id=conversation_id,
                        )
                        all_blocks.append(block)
                    except Exception as e:
                        logger.warning("Failed to create email bundle: %s", e)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "OK",
                    })
                elif tc.function.name in _TOOL_NAME_TO_BLOCK_TYPE:
                    # Block tools: parse as UI blocks, send dummy response
                    block_type = _TOOL_NAME_TO_BLOCK_TYPE.get(tc.function.name)
                    try:
                        payload = json.loads(tc.function.arguments)
                        all_blocks.append({
                            "id": str(uuid4()),
                            "type": block_type,
                            "payload": payload,
                        })
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning("Failed to parse %s: %s", tc.function.name, e)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "OK",
                    })
                elif is_calendar_tool(tc.function.name):
                    # Calendar tools: execute and emit calendar blocks
                    has_integration_calls = True
                    logger.info("Calling calendar tool: %s", tc.function.name)

                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    result = await execute_calendar_tool(
                        tool_name=tc.function.name,
                        arguments=args,
                        db=db,
                        current_user={"tenant_id": tenant_id, "user_id": "SYSTEM_USER"},  # TODO: Pass user_id from API layer
                    )

                    # Emit calendar block
                    try:
                        result_data = json.loads(result)
                        if result_data.get("type") in ["calendar_event_card", "calendar_event_choices", "calendar_connect_cta", "calendar_clarification"]:
                            all_blocks.append({
                                "id": str(uuid4()),
                                "type": result_data["type"],
                                "payload": result_data,
                            })
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning("Failed to parse calendar result: %s", e)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                else:
                    # Integration tool: execute via Nango
                    has_integration_calls = True
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    provider = find_provider_for_tool(tc.function.name)
                    if provider and integrations:
                        # Find the nango_connection_id for this provider
                        conn_id = next(
                            (i["nango_connection_id"] for i in integrations if i["provider"] == provider),
                            None,
                        )
                        if conn_id:
                            result = await execute_integration_tool(
                                tool_name=tc.function.name,
                                arguments=args,
                                provider=provider,
                                nango_connection_id=conn_id,
                            )
                            # Emit a tool_call block for the frontend
                            all_blocks.append({
                                "id": str(uuid4()),
                                "type": "tool_call",
                                "payload": {
                                    "provider": provider,
                                    "tool": tc.function.name,
                                    "result": json.loads(result) if result.startswith("{") or result.startswith("[") else result,
                                },
                            })
                        else:
                            result = json.dumps({"error": f"No connection found for {provider}"})
                    else:
                        result = json.dumps({"error": f"Unknown tool: {tc.function.name}"})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

            # If only block tools were called (no integration tools),
            # the LLM won't need another turn
            if not has_integration_calls:
                response_text = assistant_msg.content or ""
                break
        else:
            response_text = assistant_msg.content or ""

        # Extract citations
        citations = self._extract_citations(chunks, response_text)

        return response_text, citations, all_blocks, total_input, total_output

    async def chat_stream(
        self,
        message: str,
        tenant_id: UUID,
        collection_ids: list[UUID],
        system_prompt: str | None = None,
        conversation_history: list[dict] | None = None,
        integrations: list[dict] | None = None,
        db: AsyncSession | None = None,
        conversation_id: UUID | None = None,
    ) -> AsyncGenerator[ChatStreamEvent, None]:
        """
        Streaming chat with SSE events and tool-calling loop.

        Yields:
            ChatStreamEvent objects for SSE
        """
        # Retrieve relevant chunks (hybrid if db provided, vector-only otherwise)
        chunks = []
        if collection_ids is not None and len(collection_ids) > 0:
            chunks = await self.retrieval.retrieve(
                query=message,
                tenant_id=tenant_id,
                collection_ids=collection_ids,
                db=db,
            )

        # Filter out low-relevance chunks to avoid polluting general questions
        chunks = self._filter_relevant_chunks(chunks, settings.rag_min_relevance_score)

        # Build context
        context = self.retrieval.build_context(chunks) if chunks else ""

        # Build contact context
        contact_context = ""
        if db:
            from app.services.contact_context import contact_context_service
            contact_context = await contact_context_service.get_contact_context_for_message(
                db, tenant_id, message
            )

        # Yield start event with chunk info
        yield ChatStreamEvent(
            event="start",
            data={"chunks_found": len(chunks)},
        )

        # Build messages
        messages = []
        messages.append({
            "role": "system",
            "content": self._build_system_prompt(system_prompt, context, integrations, contact_context),
        })

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": message})

        all_tools = self._build_tools_list(integrations)
        full_response = ""
        tokens_input = 0
        tokens_output = 0

        try:
            # Tool-calling loop: stream the final response but handle
            # intermediate tool calls non-streamed
            for iteration in range(MAX_TOOL_ITERATIONS):
                tool_calls_acc: dict[int, dict] = {}
                is_final_stream = True

                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    tools=all_tools if all_tools else None,
                    # parallel_tool_calls=True,  # Not supported by Mistral API
                    stream=True,
                    # stream_options={"include_usage": True},  # Not supported by Mistral API
                )

                streamed_content = ""
                async for chunk in stream:
                    # Stream text tokens
                    if chunk.choices and chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        streamed_content += token
                        full_response += token
                        yield ChatStreamEvent(event="token", data=token)

                    # Accumulate tool call arguments
                    if chunk.choices and chunk.choices[0].delta.tool_calls:
                        for tc in chunk.choices[0].delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc.id:
                                tool_calls_acc[idx]["id"] = tc.id
                            if tc.function and tc.function.name:
                                tool_calls_acc[idx]["name"] = tc.function.name
                            if tc.function and tc.function.arguments:
                                tool_calls_acc[idx]["arguments"] += tc.function.arguments

                    # Get usage from final chunk
                    if chunk.usage:
                        tokens_input += chunk.usage.prompt_tokens
                        tokens_output += chunk.usage.completion_tokens

                if not tool_calls_acc:
                    # No tool calls, we're done
                    break

                # Process tool calls
                has_integration_calls = False
                # Build assistant message with tool_calls for the messages list
                assistant_tool_calls = []
                for tc_data in tool_calls_acc.values():
                    assistant_tool_calls.append({
                        "id": tc_data["id"],
                        "type": "function",
                        "function": {
                            "name": tc_data["name"],
                            "arguments": tc_data["arguments"],
                        },
                    })

                messages.append({
                    "role": "assistant",
                    "content": streamed_content or None,
                    "tool_calls": assistant_tool_calls,
                })

                for tc_data in tool_calls_acc.values():
                    if tc_data["name"] == "suggestEmail":
                        # Email suggestion: create bundle in DB, emit block with bundle_id
                        try:
                            args = json.loads(tc_data["arguments"])
                        except json.JSONDecodeError:
                            args = {}
                        try:
                            block = await self._handle_suggest_email(
                                args=args,
                                tenant_id=tenant_id,
                                conversation_id=conversation_id,
                            )
                            yield ChatStreamEvent(event="block", data=block)
                        except Exception as e:
                            logger.warning("Failed to create email bundle: %s", e)
                            yield ChatStreamEvent(event="block", data={
                                "id": str(uuid4()),
                                "type": "error",
                                "payload": {"message": f"Email suggestion failed: {e}"},
                            })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_data["id"],
                            "content": "OK",
                        })
                    elif tc_data["name"] in _TOOL_NAME_TO_BLOCK_TYPE:
                        # Block/UI tool: emit as block
                        block_type = _TOOL_NAME_TO_BLOCK_TYPE.get(tc_data["name"])
                        try:
                            payload = json.loads(tc_data["arguments"])
                            block = {
                                "id": str(uuid4()),
                                "type": block_type,
                                "payload": payload,
                            }
                            yield ChatStreamEvent(event="block", data=block)
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning("Failed to parse %s: %s", tc_data["name"], e)
                            yield ChatStreamEvent(event="block", data={
                                "id": str(uuid4()),
                                "type": "error",
                                "payload": {"message": str(e), "raw": tc_data["arguments"][:200]},
                            })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_data["id"],
                            "content": "OK",
                        })
                    elif is_calendar_tool(tc_data["name"]):
                        # Calendar tools: execute and emit calendar blocks
                        has_integration_calls = True
                        logger.info("Calling calendar tool (streaming): %s", tc_data["name"])

                        # Emit tool_call block (in progress)
                        yield ChatStreamEvent(event="block", data={
                            "id": str(uuid4()),
                            "type": "tool_call",
                            "payload": {
                                "provider": "calendar",
                                "tool": tc_data["name"],
                                "status": "calling",
                            },
                        })

                        try:
                            args = json.loads(tc_data["arguments"])
                        except json.JSONDecodeError:
                            args = {}

                        result = await execute_calendar_tool(
                            tool_name=tc_data["name"],
                            arguments=args,
                            db=db,
                            current_user={"tenant_id": tenant_id, "user_id": "SYSTEM_USER"},  # TODO: Pass user_id from API layer
                        )

                        # Parse result and emit appropriate block
                        try:
                            result_data = json.loads(result)
                            if result_data.get("type") in ["calendar_event_card", "calendar_event_choices", "calendar_connect_cta", "calendar_clarification"]:
                                yield ChatStreamEvent(event="block", data={
                                    "id": str(uuid4()),
                                    "type": result_data["type"],
                                    "payload": result_data,
                                })
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning("Failed to parse calendar result: %s", e)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_data["id"],
                            "content": result,
                        })
                    else:
                        # Integration tool: execute and continue loop
                        has_integration_calls = True
                        try:
                            args = json.loads(tc_data["arguments"])
                        except json.JSONDecodeError:
                            args = {}

                        provider = find_provider_for_tool(tc_data["name"])
                        result = json.dumps({"error": f"Unknown tool: {tc_data['name']}"})

                        if provider and integrations:
                            conn_id = next(
                                (i["nango_connection_id"] for i in integrations if i["provider"] == provider),
                                None,
                            )
                            if conn_id:
                                # Emit tool_call block to show the user what's happening
                                yield ChatStreamEvent(event="block", data={
                                    "id": str(uuid4()),
                                    "type": "tool_call",
                                    "payload": {
                                        "provider": provider,
                                        "tool": tc_data["name"],
                                        "status": "calling",
                                    },
                                })

                                result = await execute_integration_tool(
                                    tool_name=tc_data["name"],
                                    arguments=args,
                                    provider=provider,
                                    nango_connection_id=conn_id,
                                )

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_data["id"],
                            "content": result,
                        })

                # If only block tools, we're done
                if not has_integration_calls:
                    break

            # Yield citations
            citations = self._extract_citations(chunks, full_response)
            yield ChatStreamEvent(
                event="citations",
                data=[c.model_dump() for c in citations],
            )

            # Yield done event
            yield ChatStreamEvent(
                event="done",
                data={
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                },
            )

        except Exception as e:
            yield ChatStreamEvent(event="error", data=str(e))


# Singleton instance
chat_service = ChatService()
