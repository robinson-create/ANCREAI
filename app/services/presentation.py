"""Presentation service — CRUD, AI generation (outline + slides), export orchestration."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from uuid import UUID, uuid4

from openai import AsyncOpenAI
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.presentation import (
    Presentation,
    PresentationAsset,
    PresentationExport,
    PresentationGenerationRun,
    PresentationSlide,
    PresentationStatus,
    PresentationTheme,
    AssetStatus,
    RunPurpose,
)
from app.schemas.presentation import (
    ExportRequest,
    GenerateOutlineRequest,
    GenerateSlidesRequest,
    OutlineItem,
    PresentationCreate,
    PresentationUpdate,
    RegenerateSlideRequest,
    SlideContent,
    SlideUpdate,
    ThemeCreate,
    ThemeData,
)
from app.services.presentation_prompts import (
    OUTLINE_SYSTEM_PROMPT,
    REPAIR_SYSTEM_PROMPT,
    REPAIR_USER_TEMPLATE,
    SLIDE_SYSTEM_PROMPT,
)
from app.services.retrieval import RetrievalService, RetrievedChunk

settings = get_settings()
logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = 2
_OUTLINE_MAX_TOKENS = 4096
_SLIDE_MAX_TOKENS = 4096


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to repair JSON truncated by max_tokens."""
    open_stack: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
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
        return None

    trimmed = text.rstrip()
    while trimmed and trimmed[-1] not in (',', ':', '{', '[', '}', ']', '"'):
        trimmed = trimmed[:-1]
    if trimmed and trimmed[-1] == ':':
        trimmed += '""'
    elif trimmed and trimmed[-1] == ',':
        trimmed = trimmed[:-1]

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


class PresentationService:
    """Service for presentation CRUD and AI-assisted slide generation."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.mistral_api_key,
            base_url="https://api.mistral.ai/v1",
        )
        self.retrieval = RetrievalService()
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    # ══════════════════════════════════════════════
    #  CRUD — Presentations
    # ══════════════════════════════════════════════

    async def create(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        data: PresentationCreate,
    ) -> Presentation:
        pres = Presentation(
            tenant_id=tenant_id,
            title=data.title,
            prompt=data.prompt,
            settings=data.settings,
            theme_id=data.theme_id,
        )
        db.add(pres)
        await db.flush()
        await db.refresh(pres, attribute_names=["id", "tenant_id", "title", "prompt", "status", "outline", "settings", "slide_order", "version", "theme_id", "error_message", "created_at", "updated_at"])
        return pres

    async def get(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        *,
        with_slides: bool = False,
    ) -> Presentation | None:
        q = select(Presentation).where(
            Presentation.id == pres_id,
            Presentation.tenant_id == tenant_id,
        )
        if with_slides:
            q = q.options(
                selectinload(Presentation.slides),
                selectinload(Presentation.theme),
            )
        result = await db.execute(q)
        return result.scalar_one_or_none()

    async def list(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Presentation]:
        q = (
            select(Presentation)
            .where(Presentation.tenant_id == tenant_id)
            .order_by(Presentation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            q = q.where(Presentation.status == status)
        result = await db.execute(q)
        return list(result.scalars().all())

    async def update(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        data: PresentationUpdate,
    ) -> Presentation | None:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(pres, key, value)

        await db.flush()
        await db.refresh(pres)
        return pres

    async def delete(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
    ) -> bool:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return False
        await db.delete(pres)
        await db.flush()
        return True

    async def duplicate(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
    ) -> Presentation | None:
        source = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not source:
            return None

        new_pres = Presentation(
            tenant_id=tenant_id,
            title=f"{source.title} (copie)",
            prompt=source.prompt,
            status=PresentationStatus.READY.value,
            theme_id=source.theme_id,
            outline=source.outline,
            settings=source.settings,
        )
        db.add(new_pres)
        await db.flush()

        slide_ids = []
        for slide in source.slides:
            new_slide = PresentationSlide(
                presentation_id=new_pres.id,
                position=slide.position,
                layout_type=slide.layout_type,
                content_json=slide.content_json,
                root_image=slide.root_image,
                bg_color=slide.bg_color,
                speaker_notes=slide.speaker_notes,
            )
            db.add(new_slide)
            await db.flush()
            slide_ids.append(str(new_slide.id))

        new_pres.slide_order = slide_ids
        await db.flush()
        await db.refresh(new_pres)
        return new_pres

    # ══════════════════════════════════════════════
    #  CRUD — Slides
    # ══════════════════════════════════════════════

    async def get_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
    ) -> PresentationSlide | None:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return None
        result = await db.execute(
            select(PresentationSlide).where(
                PresentationSlide.id == slide_id,
                PresentationSlide.presentation_id == pres_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
        data: SlideUpdate,
    ) -> PresentationSlide | None:
        slide = await self.get_slide(db, tenant_id, pres_id, slide_id)
        if not slide:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(slide, key, value)

        # Bump presentation version
        pres = await self.get(db, tenant_id, pres_id)
        if pres:
            pres.version = pres.version + 1

        await db.flush()
        await db.refresh(slide)
        return slide

    async def add_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
    ) -> PresentationSlide | None:
        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not pres:
            return None

        position = len(pres.slides)
        slide = PresentationSlide(
            presentation_id=pres_id,
            position=position,
            layout_type="vertical",
            content_json=[
                {"type": "h2", "children": [{"text": "Nouveau slide"}]},
                {"type": "p", "children": [{"text": ""}]},
            ],
        )
        db.add(slide)
        await db.flush()

        pres.slide_order = [*pres.slide_order, str(slide.id)]
        pres.version = pres.version + 1
        await db.flush()
        await db.refresh(slide)
        return slide

    async def delete_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
    ) -> bool:
        slide = await self.get_slide(db, tenant_id, pres_id, slide_id)
        if not slide:
            return False

        pres = await self.get(db, tenant_id, pres_id)
        if pres:
            pres.slide_order = [
                sid for sid in pres.slide_order if sid != str(slide_id)
            ]
            pres.version = pres.version + 1

        await db.delete(slide)
        await db.flush()
        return True

    async def reorder_slides(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_ids: list[UUID],
    ) -> Presentation | None:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return None

        pres.slide_order = [str(sid) for sid in slide_ids]
        # Update positions to match
        for i, sid in enumerate(slide_ids):
            result = await db.execute(
                select(PresentationSlide).where(
                    PresentationSlide.id == sid,
                    PresentationSlide.presentation_id == pres_id,
                )
            )
            slide = result.scalar_one_or_none()
            if slide:
                slide.position = i

        pres.version = pres.version + 1
        await db.flush()
        await db.refresh(pres)
        return pres

    # ══════════════════════════════════════════════
    #  CRUD — Themes
    # ══════════════════════════════════════════════

    async def list_themes(
        self,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> list[PresentationTheme]:
        """List built-in themes + tenant's custom themes."""
        result = await db.execute(
            select(PresentationTheme).where(
                (PresentationTheme.tenant_id == tenant_id)
                | (PresentationTheme.is_builtin == True)  # noqa: E712
            ).order_by(PresentationTheme.is_builtin.desc(), PresentationTheme.name)
        )
        return list(result.scalars().all())

    async def create_theme(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        data: ThemeCreate,
    ) -> PresentationTheme:
        theme = PresentationTheme(
            tenant_id=tenant_id,
            name=data.name,
            is_builtin=False,
            theme_data=data.theme_data.model_dump(),
        )
        db.add(theme)
        await db.flush()
        await db.refresh(theme)
        return theme

    # ══════════════════════════════════════════════
    #  Outline update
    # ══════════════════════════════════════════════

    async def update_outline(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        outline: list[OutlineItem],
    ) -> Presentation | None:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return None
        pres.outline = [item.model_dump() for item in outline]
        pres.status = PresentationStatus.OUTLINE_READY.value
        pres.version = pres.version + 1
        await db.flush()
        await db.refresh(pres)
        return pres

    # ══════════════════════════════════════════════
    #  AI Generation — called from Arq workers
    # ══════════════════════════════════════════════

    async def generate_outline(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        request: GenerateOutlineRequest,
    ) -> list[OutlineItem]:
        """Generate presentation outline via LLM. Called from Arq worker."""
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            raise ValueError(f"Presentation {pres_id} not found")

        pres.status = PresentationStatus.GENERATING_OUTLINE.value
        pres.prompt = request.prompt
        pres.settings = {
            **pres.settings,
            "language": request.language,
            "style": request.style,
            "slide_count": request.slide_count,
        }
        await db.flush()

        # Optional RAG context
        rag_context = "Aucun contexte additionnel."
        if request.collection_ids:
            chunks = await self.retrieval.retrieve(
                query=request.prompt,
                tenant_id=tenant_id,
                collection_ids=request.collection_ids,
                db=db,
            )
            rag_context = self.retrieval.build_context(chunks)

        system_prompt = OUTLINE_SYSTEM_PROMPT.format(
            slide_count=request.slide_count,
            language=request.language,
            style=request.style,
            rag_context=rag_context,
        )

        raw = await self._tracked_llm_call(
            db=db,
            tenant_id=tenant_id,
            presentation_id=pres_id,
            slide_id=None,
            purpose=RunPurpose.OUTLINE.value,
            system_prompt=system_prompt,
            user_prompt=request.prompt,
            max_tokens=_OUTLINE_MAX_TOKENS,
        )

        # Parse outline JSON
        parsed = self._parse_json(raw)
        if not parsed:
            raise ValueError("Failed to parse outline JSON from LLM response")

        outline_items = []
        for item in parsed.get("outline", []):
            outline_items.append(
                OutlineItem(
                    title=item.get("title", ""),
                    bullets=item.get("bullets", []),
                )
            )

        pres.title = parsed.get("title", pres.title)
        pres.outline = [item.model_dump() for item in outline_items]
        pres.status = PresentationStatus.OUTLINE_READY.value
        await db.flush()

        return outline_items

    async def generate_slides(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        request: GenerateSlidesRequest,
        on_slide_progress: Any | None = None,
    ) -> list[PresentationSlide]:
        """Generate slides one by one from outline. Called from Arq worker."""
        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not pres:
            raise ValueError(f"Presentation {pres_id} not found")
        if not pres.outline:
            raise ValueError("No outline — generate outline first")

        pres.status = PresentationStatus.GENERATING_SLIDES.value
        await db.flush()

        # Optional RAG context
        rag_context = "Aucun contexte additionnel."
        if request.collection_ids:
            chunks = await self.retrieval.retrieve(
                query=pres.prompt or pres.title,
                tenant_id=tenant_id,
                collection_ids=request.collection_ids,
                db=db,
            )
            rag_context = self.retrieval.build_context(chunks)

        lang = pres.settings.get("language", "fr-FR")
        style = pres.settings.get("style", "professional")

        # Delete existing slides if regenerating
        for existing in pres.slides:
            await db.delete(existing)
        await db.flush()

        slides: list[PresentationSlide] = []
        slide_ids: list[str] = []
        prev_layout = ""

        for i, outline_item in enumerate(pres.outline):
            slide_data = await self._generate_and_validate_slide(
                db=db,
                tenant_id=tenant_id,
                presentation_id=pres_id,
                outline_item=outline_item,
                slide_index=i,
                total_slides=len(pres.outline),
                prev_layout=prev_layout,
                rag_context=rag_context,
                language=lang,
                style=style,
            )

            slide = PresentationSlide(
                presentation_id=pres_id,
                position=i,
                layout_type=slide_data.get("layout_type", "vertical"),
                content_json=slide_data.get("content_json", []),
                root_image=slide_data.get("root_image"),
                bg_color=slide_data.get("bg_color"),
            )
            db.add(slide)
            await db.flush()
            await db.refresh(slide)

            slides.append(slide)
            slide_ids.append(str(slide.id))
            prev_layout = slide.layout_type

            logger.info(f"Generated slide {i + 1}/{len(pres.outline)} for presentation {pres_id}")

            if on_slide_progress:
                await on_slide_progress(slide, i, len(pres.outline))

        pres.slide_order = slide_ids
        pres.status = PresentationStatus.READY.value
        pres.version = pres.version + 1
        await db.flush()

        return slides

    async def regenerate_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
        request: RegenerateSlideRequest,
    ) -> PresentationSlide | None:
        """Regenerate a single slide."""
        slide = await self.get_slide(db, tenant_id, pres_id, slide_id)
        if not slide:
            return None

        pres = await self.get(db, tenant_id, pres_id)
        if not pres or not pres.outline:
            return None

        # Find matching outline item by position
        outline_item = (
            pres.outline[slide.position]
            if slide.position < len(pres.outline)
            else {"title": "Slide", "bullets": []}
        )

        rag_context = "Aucun contexte additionnel."
        if request.collection_ids:
            chunks = await self.retrieval.retrieve(
                query=request.instruction or pres.prompt or pres.title,
                tenant_id=tenant_id,
                collection_ids=request.collection_ids,
                db=db,
            )
            rag_context = self.retrieval.build_context(chunks)

        lang = pres.settings.get("language", "fr-FR")
        style = pres.settings.get("style", "professional")

        slide_data = await self._generate_and_validate_slide(
            db=db,
            tenant_id=tenant_id,
            presentation_id=pres_id,
            outline_item=outline_item,
            slide_index=slide.position,
            total_slides=len(pres.outline),
            prev_layout="",
            rag_context=rag_context,
            language=lang,
            style=style,
        )

        slide.layout_type = slide_data.get("layout_type", "vertical")
        slide.content_json = slide_data.get("content_json", [])
        slide.root_image = slide_data.get("root_image")
        slide.bg_color = slide_data.get("bg_color")

        pres.version = pres.version + 1
        await db.flush()
        await db.refresh(slide)
        return slide

    # ══════════════════════════════════════════════
    #  Export — create export record, actual work done in Arq
    # ══════════════════════════════════════════════

    async def create_export(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        request: ExportRequest,
    ) -> PresentationExport | None:
        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not pres:
            return None

        # Build payload hash for snapshot
        slides_data = []
        for slide in sorted(pres.slides, key=lambda s: s.position):
            slides_data.append({
                "position": slide.position,
                "layout_type": slide.layout_type,
                "content_json": slide.content_json,
                "root_image": slide.root_image,
                "bg_color": slide.bg_color,
            })
        payload_json = json.dumps(slides_data, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

        # Get theme snapshot
        theme_snapshot = None
        if pres.theme_id:
            theme = await db.get(PresentationTheme, pres.theme_id)
            if theme:
                theme_snapshot = theme.theme_data

        export = PresentationExport(
            presentation_id=pres_id,
            tenant_id=tenant_id,
            format=request.format,
            status="pending",
            presentation_version=pres.version,
            payload_hash=payload_hash,
            slide_count=len(pres.slides),
            theme_snapshot=theme_snapshot,
        )
        db.add(export)
        await db.flush()
        await db.refresh(export)
        return export

    async def list_exports(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
    ) -> list[PresentationExport]:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return []
        result = await db.execute(
            select(PresentationExport)
            .where(
                PresentationExport.presentation_id == pres_id,
                PresentationExport.tenant_id == tenant_id,
            )
            .order_by(PresentationExport.created_at.desc())
        )
        return list(result.scalars().all())

    # ══════════════════════════════════════════════
    #  Internal — LLM calls with tracking
    # ══════════════════════════════════════════════

    async def _tracked_llm_call(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        presentation_id: UUID,
        slide_id: UUID | None,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        """Make LLM call and log to generation_runs."""
        run = PresentationGenerationRun(
            tenant_id=tenant_id,
            presentation_id=presentation_id,
            slide_id=slide_id,
            purpose=purpose,
            model=self.model,
            input_hash=hashlib.sha256(
                (system_prompt + user_prompt).encode()
            ).hexdigest(),
            request_payload={
                "system_prompt": system_prompt[:2000],
                "user_prompt": user_prompt[:2000],
            },
            status="running",
        )
        db.add(run)
        await db.flush()

        t0 = time.monotonic()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            run.tokens_in = response.usage.prompt_tokens if response.usage else 0
            run.tokens_out = response.usage.completion_tokens if response.usage else 0
            run.response_excerpt = content[:500]
            run.status = "success"
            run.duration_ms = int((time.monotonic() - t0) * 1000)
            return content
        except Exception as e:
            run.status = "error"
            run.error = str(e)[:2000]
            run.duration_ms = int((time.monotonic() - t0) * 1000)
            raise
        finally:
            await db.flush()

    async def _generate_and_validate_slide(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        presentation_id: UUID,
        outline_item: dict,
        slide_index: int,
        total_slides: int,
        prev_layout: str,
        rag_context: str,
        language: str,
        style: str,
    ) -> dict:
        """Generate a slide with validation → repair → safe fallback."""
        system_prompt = SLIDE_SYSTEM_PROMPT.format(
            language=language,
            style=style,
            rag_context=rag_context,
        )

        user_prompt = (
            f"Slide {slide_index + 1}/{total_slides}.\n"
            f"Sujet : {outline_item.get('title', '')}\n"
            f"Points clés :\n"
            + "\n".join(f"- {b}" for b in outline_item.get("bullets", []))
            + f"\n\nLayout précédent : {prev_layout or 'aucun'} (utilise un layout DIFFÉRENT)."
        )

        # Attempt 1: generate
        raw = await self._tracked_llm_call(
            db=db,
            tenant_id=tenant_id,
            presentation_id=presentation_id,
            slide_id=None,
            purpose=RunPurpose.SLIDE_GEN.value,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        result, errors = self._validate_slide_json(raw)
        if result:
            return result

        # Repair loop
        current_raw = raw
        for attempt in range(MAX_REPAIR_ATTEMPTS):
            logger.warning(
                f"Slide {slide_index} validation failed (attempt {attempt + 1}), "
                f"repairing: {errors[:200]}"
            )

            repair_prompt = REPAIR_USER_TEMPLATE.format(
                raw_json=current_raw[:3000],
                validation_errors=errors,
            )

            repaired = await self._tracked_llm_call(
                db=db,
                tenant_id=tenant_id,
                presentation_id=presentation_id,
                slide_id=None,
                purpose=RunPurpose.REPAIR.value,
                system_prompt=REPAIR_SYSTEM_PROMPT,
                user_prompt=repair_prompt,
            )

            result, errors = self._validate_slide_json(repaired)
            if result:
                return result
            current_raw = repaired

        # Safe template fallback (themed)
        logger.error(
            f"Slide {slide_index} repair failed after {MAX_REPAIR_ATTEMPTS} attempts, "
            f"using safe template"
        )
        return self._safe_slide_template(outline_item, slide_index)

    def _validate_slide_json(self, raw: str) -> tuple[dict | None, str]:
        """Parse and validate slide JSON. Returns (data, errors)."""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            repaired = _repair_truncated_json(raw)
            if repaired:
                parsed = repaired
            else:
                return None, f"JSONDecodeError: invalid JSON"

        try:
            validated = SlideContent.model_validate(parsed)
            return validated.model_dump(), ""
        except ValidationError as e:
            return None, str(e)[:1000]

    @staticmethod
    def _safe_slide_template(outline_item: dict, index: int) -> dict:
        """Themed safe fallback — guaranteed valid."""
        return {
            "layout_type": "vertical",
            "bg_color": None,
            "root_image": None,
            "content_json": [
                {
                    "type": "h2",
                    "children": [
                        {"text": outline_item.get("title", f"Slide {index + 1}")}
                    ],
                },
                {
                    "type": "bullet_group",
                    "children": [
                        {
                            "type": "bullet_item",
                            "children": [
                                {"type": "h3", "children": [{"text": b}]},
                                {"type": "p", "children": [{"text": ""}]},
                            ],
                        }
                        for b in outline_item.get(
                            "bullets", ["Point clé 1", "Point clé 2", "Point clé 3"]
                        )
                    ],
                },
            ],
        }

    def _parse_json(self, raw: str) -> dict | None:
        """Parse JSON with truncation repair."""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return _repair_truncated_json(raw)


# Singleton
presentation_service = PresentationService()
