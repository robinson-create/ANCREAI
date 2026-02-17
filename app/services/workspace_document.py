"""Workspace document service — CRUD + AI actions."""

from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.assistant import Assistant
from app.models.workspace_document import WorkspaceDocument
from app.schemas.workspace_document import (
    AiActionResponse,
    AddLineItemRequest,
    CheckDocumentRequest,
    DocModel,
    DocPatch,
    DocSource,
    GenerateRequest,
    RewriteBlockRequest,
    WorkspaceDocumentCreate,
    WorkspaceDocumentUpdate,
)
from app.services.retrieval import RetrievalService, RetrievedChunk

settings = get_settings()
logger = logging.getLogger(__name__)

_GENERATE_MAX_TOKENS = 16_384


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to repair JSON truncated by max_tokens.

    Walks the string tracking open braces/brackets while respecting
    strings, then appends the missing closers.  Returns the parsed
    dict on success, or None if repair fails.
    """
    open_stack: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            # Skip entire string (handle escapes)
            i += 1
            while i < n:
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
        elif c in ('{', '['):
            open_stack.append('}' if c == '{' else ']')
        elif c in ('}', ']'):
            if open_stack:
                open_stack.pop()
        i += 1

    if not open_stack:
        return None  # Nothing to repair (or not truncated)

    # Remove a possible trailing incomplete value (e.g. cut-off string)
    # by trimming back to last comma, colon, or opener
    trimmed = text.rstrip()
    while trimmed and trimmed[-1] not in (',', ':', '{', '[', '}', ']', '"'):
        trimmed = trimmed[:-1]
    # If we're mid-string, close it
    if trimmed and trimmed[-1] == '"':
        pass  # string is closed
    elif trimmed and trimmed[-1] == ':':
        trimmed += '""'  # add empty value
    elif trimmed and trimmed[-1] == ',':
        trimmed = trimmed[:-1]  # remove dangling comma

    # Recount after trimming
    open_stack = []
    i = 0
    n2 = len(trimmed)
    while i < n2:
        c = trimmed[i]
        if c == '"':
            i += 1
            while i < n2:
                if trimmed[i] == '\\':
                    i += 2
                    continue
                if trimmed[i] == '"':
                    break
                i += 1
        elif c in ('{', '['):
            open_stack.append('}' if c == '{' else ']')
        elif c in ('}', ']'):
            if open_stack:
                open_stack.pop()
        i += 1

    suffix = "".join(reversed(open_stack))
    try:
        return json.loads(trimmed + suffix)
    except json.JSONDecodeError:
        return None


class WorkspaceDocumentService:
    """Service for workspace document CRUD and AI-assisted editing."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.mistral_api_key,
            base_url="https://api.mistral.ai/v1",
        )
        self.retrieval = RetrievalService()
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    # ── CRUD ──

    async def create(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        data: WorkspaceDocumentCreate,
    ) -> WorkspaceDocument:
        content = data.content_json.model_dump() if data.content_json else {}
        doc = WorkspaceDocument(
            tenant_id=tenant_id,
            assistant_id=data.assistant_id,
            title=data.title,
            doc_type=data.doc_type,
            status=data.status,
            content_json=content,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        return doc

    async def get(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
    ) -> WorkspaceDocument | None:
        result = await db.execute(
            select(WorkspaceDocument).where(
                WorkspaceDocument.id == doc_id,
                WorkspaceDocument.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkspaceDocument]:
        q = (
            select(WorkspaceDocument)
            .where(WorkspaceDocument.tenant_id == tenant_id)
            .order_by(WorkspaceDocument.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            q = q.where(WorkspaceDocument.status == status)
        result = await db.execute(q)
        return list(result.scalars().all())

    async def update(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
        data: WorkspaceDocumentUpdate,
    ) -> WorkspaceDocument | None:
        doc = await self.get(db, tenant_id, doc_id)
        if not doc:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if "content_json" in update_data and update_data["content_json"] is not None:
            update_data["content_json"] = data.content_json.model_dump()  # type: ignore[union-attr]

        for key, value in update_data.items():
            setattr(doc, key, value)

        await db.flush()
        await db.refresh(doc)
        return doc

    async def patch_content(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
        content: DocModel,
    ) -> WorkspaceDocument | None:
        doc = await self.get(db, tenant_id, doc_id)
        if not doc:
            return None

        doc.content_json = content.model_dump()
        doc.version = doc.version + 1
        await db.flush()
        await db.refresh(doc)
        return doc

    async def delete(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
    ) -> bool:
        doc = await self.get(db, tenant_id, doc_id)
        if not doc:
            return False
        await db.delete(doc)
        await db.flush()
        return True

    async def duplicate(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
    ) -> WorkspaceDocument | None:
        """Duplicate a workspace document as a new draft."""
        source = await self.get(db, tenant_id, doc_id)
        if not source:
            return None

        new_doc = WorkspaceDocument(
            tenant_id=tenant_id,
            assistant_id=source.assistant_id,
            title=f"{source.title} (copie)",
            doc_type=source.doc_type,
            status="draft",
            content_json=source.content_json,
        )
        db.add(new_doc)
        await db.flush()
        await db.refresh(new_doc)
        return new_doc

    # ── Helpers ──

    async def _get_assistant_collection_ids(
        self, db: AsyncSession, assistant_id: UUID | None, tenant_id: UUID
    ) -> list[UUID]:
        """Get collection IDs from the assistant linked to the document."""
        if not assistant_id:
            return []
        result = await db.execute(
            select(Assistant)
            .where(Assistant.id == assistant_id, Assistant.tenant_id == tenant_id)
            .options(selectinload(Assistant.collections))
        )
        assistant = result.scalar_one_or_none()
        if not assistant:
            return []
        return [c.id for c in assistant.collections]

    def _chunks_to_sources(self, chunks: list[RetrievedChunk]) -> list[DocSource]:
        """Convert retrieved chunks to DocSource list."""
        sources = []
        for chunk in chunks[:5]:
            score = chunk.rerank_score or chunk.fused_score or chunk.score
            sources.append(
                DocSource(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_filename=chunk.document_filename,
                    page_number=chunk.page_number,
                    excerpt=chunk.content[:200],
                    score=score,
                )
            )
        return sources

    def _build_context(self, chunks: list[RetrievedChunk]) -> str:
        """Build context string from retrieved chunks."""
        return self.retrieval.build_context(chunks)

    async def _llm_call(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        """Make a single LLM call and return the content."""
        kwargs: dict = dict(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    # ── JSON helpers ──

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """Extract and parse a JSON object from an LLM response.

        Handles: markdown code blocks, surrounding text, and truncated output.
        Raises json.JSONDecodeError if nothing works.
        """
        text = raw.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rsplit("```", 1)[0].strip()

        # Find the first '{' to locate JSON start
        start = text.find("{")
        if start < 0:
            raise json.JSONDecodeError("No JSON object found", text, 0)
        text = text[start:]

        # Try parsing as-is first (fast path)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to repair truncated JSON by closing open structures
        repaired = _repair_truncated_json(text)
        if repaired is not None:
            return repaired

        # Last resort: let json.loads raise with the original text
        return json.loads(text)

    # ── AI Actions ──

    async def generate(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
        request: GenerateRequest,
    ) -> AiActionResponse:
        """Generate document content using RAG."""
        doc = await self.get(db, tenant_id, doc_id)
        if not doc:
            return AiActionResponse(message="Document introuvable.")

        # Get collection IDs
        collection_ids = list(request.collection_ids)
        if not collection_ids:
            collection_ids = await self._get_assistant_collection_ids(
                db, doc.assistant_id, tenant_id
            )

        # Retrieve RAG context
        chunks: list[RetrievedChunk] = []
        if collection_ids:
            chunks = await self.retrieval.retrieve(
                query=request.prompt,
                tenant_id=tenant_id,
                collection_ids=collection_ids,
                db=db,
            )
        context = self._build_context(chunks)
        sources = self._chunks_to_sources(chunks)

        doc_type = request.doc_type or doc.doc_type

        system_prompt = f"""Tu es un assistant spécialisé dans la rédaction de documents professionnels.
Tu dois générer le contenu d'un document de type "{doc_type}".

INSTRUCTIONS :
- Génère le contenu sous forme de blocs JSON compatibles avec le format DocModel.
- Chaque bloc a un "type" parmi : rich_text, line_items, clause, terms, signature.
- Pour les blocs rich_text/clause/terms, le "content" est du JSON ProseMirror (Tiptap).
  IMPORTANT : utilise les noms de nœuds Tiptap en camelCase : "bulletList", "orderedList", "listItem", "codeBlock", "hardBreak", "horizontalRule" (PAS "bullet_list", "list_item", etc.).
- Pour les blocs line_items, fournis des "items" structurés.
- Cite tes sources quand tu utilises le contexte.
- Réponds UNIQUEMENT avec un JSON valide, sans texte autour.

FORMAT DE RÉPONSE (JSON) :
{{
  "patches": [
    {{"op": "add_block", "value": {{"type": "rich_text", "id": "<uuid>", "label": "Introduction", "content": {{"type": "doc", "content": [{{"type": "paragraph", "content": [{{"type": "text", "text": "..."}}]}}]}}}}}}
  ],
  "message": "Document généré avec succès."
}}

{f"CONTEXTE (sources RAG) :{chr(10)}{context}" if context else "Aucun contexte RAG disponible."}"""

        user_prompt = request.prompt

        max_attempts = 2
        raw_response = ""
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                raw_response = await self._llm_call(
                    system_prompt,
                    user_prompt,
                    json_mode=True,
                    max_tokens=_GENERATE_MAX_TOKENS,
                )
                logger.info(
                    "LLM raw response (attempt %d, first 500 chars): %s",
                    attempt + 1,
                    raw_response[:500],
                )

                parsed = self._parse_json_response(raw_response)

                patches = [
                    DocPatch(
                        op=p.get("op", "add_block"),
                        block_id=p.get("block_id"),
                        value=p.get("value", {}),
                    )
                    for p in parsed.get("patches", [])
                ]
                message = parsed.get("message", "Document généré.")

                if not patches:
                    logger.warning("LLM returned valid JSON but no patches")

                return AiActionResponse(patches=patches, sources=sources, message=message)
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(
                    "JSON parse error (attempt %d/%d): %s — raw: %s",
                    attempt + 1,
                    max_attempts,
                    e,
                    raw_response[:300],
                )
                continue
            except Exception as e:
                logger.exception("Error in generate action: %s", e)
                return AiActionResponse(
                    message=f"Erreur lors de la génération : {e}",
                    sources=sources,
                )

        logger.error("All %d generate attempts failed. Last error: %s", max_attempts, last_error)
        return AiActionResponse(
            message="Erreur lors de la génération : le modèle n'a pas renvoyé un JSON valide.",
            sources=sources,
        )

    async def rewrite_block(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
        request: RewriteBlockRequest,
    ) -> AiActionResponse:
        """Rewrite a specific block with AI assistance."""
        doc = await self.get(db, tenant_id, doc_id)
        if not doc:
            return AiActionResponse(message="Document introuvable.")

        # Find the block to rewrite
        doc_model = DocModel.model_validate(doc.content_json)
        target_block = None
        for block in doc_model.blocks:
            if block.id == request.block_id:
                target_block = block
                break

        if not target_block:
            return AiActionResponse(message=f"Bloc {request.block_id} introuvable.")

        # Get collection IDs for RAG
        collection_ids = list(request.collection_ids)
        if not collection_ids:
            collection_ids = await self._get_assistant_collection_ids(
                db, doc.assistant_id, tenant_id
            )

        chunks: list[RetrievedChunk] = []
        if collection_ids:
            chunks = await self.retrieval.retrieve(
                query=request.instruction,
                tenant_id=tenant_id,
                collection_ids=collection_ids,
                db=db,
            )
        context = self._build_context(chunks)
        sources = self._chunks_to_sources(chunks)

        block_json = json.dumps(target_block.model_dump(), ensure_ascii=False)

        system_prompt = f"""Tu es un assistant spécialisé dans la rédaction de documents professionnels.
Tu dois réécrire un bloc de document selon les instructions de l'utilisateur.

BLOC ACTUEL :
{block_json}

INSTRUCTIONS :
- Réécris le contenu du bloc selon l'instruction de l'utilisateur.
- Conserve le même type de bloc et le même id.
- Pour rich_text/clause/terms, le "content" est du JSON ProseMirror (Tiptap).
  IMPORTANT : utilise les noms de nœuds Tiptap en camelCase : "bulletList", "orderedList", "listItem", "codeBlock", "hardBreak", "horizontalRule" (PAS "bullet_list", "list_item", etc.).
- Réponds UNIQUEMENT avec un JSON valide.

FORMAT DE RÉPONSE (JSON) :
{{
  "patches": [
    {{"op": "replace_block", "block_id": "{request.block_id}", "value": {{...bloc réécrit...}}}}
  ],
  "message": "Bloc réécrit."
}}

{f"CONTEXTE (sources RAG) :{chr(10)}{context}" if context else ""}"""

        user_prompt = request.instruction

        try:
            raw_response = await self._llm_call(system_prompt, user_prompt, json_mode=True)
            parsed = json.loads(raw_response.strip())

            patches = [
                DocPatch(
                    op=p.get("op", "replace_block"),
                    block_id=p.get("block_id"),
                    value=p.get("value", {}),
                )
                for p in parsed.get("patches", [])
            ]
            return AiActionResponse(
                patches=patches,
                sources=sources,
                message=parsed.get("message", "Bloc réécrit."),
            )
        except Exception as e:
            logger.exception("Error in rewrite_block action: %s", e)
            return AiActionResponse(
                message=f"Erreur lors de la réécriture : {e}",
                sources=sources,
            )

    async def check_document(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
        request: CheckDocumentRequest,
    ) -> AiActionResponse:
        """Check document for consistency / compliance issues."""
        doc = await self.get(db, tenant_id, doc_id)
        if not doc:
            return AiActionResponse(message="Document introuvable.")

        doc_model = DocModel.model_validate(doc.content_json)
        doc_json = json.dumps(doc_model.model_dump(), ensure_ascii=False, indent=2)

        # Get collection IDs for RAG
        collection_ids = list(request.collection_ids)
        if not collection_ids:
            collection_ids = await self._get_assistant_collection_ids(
                db, doc.assistant_id, tenant_id
            )

        chunks: list[RetrievedChunk] = []
        if collection_ids:
            summary_query = f"Vérification du document: {doc.title} ({doc.doc_type})"
            chunks = await self.retrieval.retrieve(
                query=summary_query,
                tenant_id=tenant_id,
                collection_ids=collection_ids,
                db=db,
            )
        context = self._build_context(chunks)
        sources = self._chunks_to_sources(chunks)

        check_instructions = {
            "general": "Vérifie la cohérence générale, les doublons, les sections manquantes, et la qualité rédactionnelle.",
            "legal": "Vérifie les mentions légales obligatoires, les clauses potentiellement abusives, et la conformité juridique.",
            "financial": "Vérifie les calculs, totaux, TVA, et la cohérence des montants.",
        }
        check_instruction = check_instructions.get(
            request.check_type, check_instructions["general"]
        )

        system_prompt = f"""Tu es un assistant expert en vérification de documents professionnels.

DOCUMENT À VÉRIFIER :
{doc_json}

INSTRUCTION :
{check_instruction}

Réponds avec un résumé clair des problèmes trouvés, suggestions d'amélioration, et un JSON de patches si des corrections sont nécessaires.

FORMAT DE RÉPONSE (JSON) :
{{
  "patches": [],
  "message": "Résumé des vérifications effectuées..."
}}

{f"CONTEXTE (sources RAG) :{chr(10)}{context}" if context else ""}"""

        try:
            raw_response = await self._llm_call(
                system_prompt, "Effectue la vérification.", json_mode=True
            )
            parsed = json.loads(raw_response.strip())

            patches = [
                DocPatch(
                    op=p.get("op", "replace_block"),
                    block_id=p.get("block_id"),
                    value=p.get("value", {}),
                )
                for p in parsed.get("patches", [])
            ]
            return AiActionResponse(
                patches=patches,
                sources=sources,
                message=parsed.get("message", "Vérification terminée."),
            )
        except Exception as e:
            logger.exception("Error in check_document action: %s", e)
            return AiActionResponse(
                message=f"Erreur lors de la vérification : {e}",
                sources=sources,
            )

    async def add_line_item(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
        request: AddLineItemRequest,
    ) -> AiActionResponse:
        """Add a line item to a line_items block using AI."""
        doc = await self.get(db, tenant_id, doc_id)
        if not doc:
            return AiActionResponse(message="Document introuvable.")

        doc_model = DocModel.model_validate(doc.content_json)

        # Find the target line_items block
        target_block = None
        for block in doc_model.blocks:
            if block.id == request.block_id and block.type == "line_items":
                target_block = block
                break

        if not target_block:
            return AiActionResponse(
                message=f"Bloc line_items {request.block_id} introuvable."
            )

        # Get collection IDs for RAG (to find pricing, etc.)
        collection_ids = list(request.collection_ids)
        if not collection_ids:
            collection_ids = await self._get_assistant_collection_ids(
                db, doc.assistant_id, tenant_id
            )

        chunks: list[RetrievedChunk] = []
        if collection_ids:
            chunks = await self.retrieval.retrieve(
                query=request.description,
                tenant_id=tenant_id,
                collection_ids=collection_ids,
                db=db,
            )
        context = self._build_context(chunks)
        sources = self._chunks_to_sources(chunks)

        existing_items_json = json.dumps(
            target_block.items if hasattr(target_block, "items") else [],  # type: ignore[union-attr]
            default=str,
            ensure_ascii=False,
        )

        system_prompt = f"""Tu es un assistant spécialisé dans la création de lignes de devis/facture.

LIGNES EXISTANTES :
{existing_items_json}

INSTRUCTIONS :
- Crée une nouvelle ligne d'après la description de l'utilisateur.
- Utilise le contexte RAG pour trouver des prix/tarifs si disponibles.
- Réponds UNIQUEMENT avec un JSON valide.

FORMAT DE RÉPONSE (JSON) :
{{
  "patches": [
    {{"op": "add_line_item", "block_id": "{request.block_id}", "value": {{
      "id": "<uuid>",
      "description": "...",
      "quantity": 1,
      "unit": "unité",
      "unit_price": 0,
      "tax_rate": 20,
      "total": 0
    }}}}
  ],
  "message": "Ligne ajoutée."
}}

{f"CONTEXTE (sources RAG) :{chr(10)}{context}" if context else ""}"""

        user_prompt = request.description

        try:
            raw_response = await self._llm_call(system_prompt, user_prompt, json_mode=True)
            parsed = json.loads(raw_response.strip())

            patches = [
                DocPatch(
                    op=p.get("op", "add_line_item"),
                    block_id=p.get("block_id", request.block_id),
                    value=p.get("value", {}),
                )
                for p in parsed.get("patches", [])
            ]
            return AiActionResponse(
                patches=patches,
                sources=sources,
                message=parsed.get("message", "Ligne ajoutée."),
            )
        except Exception as e:
            logger.exception("Error in add_line_item action: %s", e)
            return AiActionResponse(
                message=f"Erreur lors de l'ajout de la ligne : {e}",
                sources=sources,
            )


# Singleton
workspace_document_service = WorkspaceDocumentService()
