"""Presentation service — CRUD, AI generation (outline + slides), export orchestration."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any
from uuid import UUID

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
from app.services.presentation_design_normalizer import normalize_slide
from app.services.presentation_icons import (
    get_icon_names_for_prompt,
    get_icon_policy_for_prompt,
    suggest_icons_for_content,
)
from app.services.presentation_prompts import (
    CURRENT_CONTENT_SECTION,
    DESIGN_CONSTRAINTS_SECTION,
    ICON_POLICY_SECTION,
    OUTLINE_CONTEXT_SECTION,
    OUTLINE_SYSTEM_PROMPT,
    REPAIR_SYSTEM_PROMPT,
    REPAIR_USER_TEMPLATE,
    SLIDE_SYSTEM_PROMPT,
    SLIDES_BATCH_SYSTEM_PROMPT,
    TEMPLATE_HINT_SECTION,
    THEME_CONTEXT_SECTION,
    USER_INSTRUCTION_SECTION,
)
from app.services.presentation_templates import (
    SlideIntent,
    TemplateSuggestion,
    get_template,
    get_template_hint_for_prompt,
    get_safe_fallback,
    suggest_template,
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
        self.slide_model = settings.llm_slide_model  # Mistral Large for slide generation
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
        """Generate slides one-by-one with per-slide progress.

        Each slide gets:
        - Full original prompt for substance
        - Full outline for context (what comes before/after)
        - Forced template with JSON skeleton
        - Diversity tracking (no two consecutive identical templates)
        """
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
        slide_count = len(pres.outline)

        # Resolve theme data
        theme_data = None
        if pres.theme_id:
            theme = await db.get(PresentationTheme, pres.theme_id)
            if theme:
                theme_data = theme.theme_data

        # Pre-assign templates with diversity tracking
        used_templates: list[str] = []
        template_plan: list[TemplateSuggestion] = []
        for i, item in enumerate(pres.outline):
            suggestion = suggest_template(item, i, slide_count)
            # Avoid consecutive duplicate templates (except cover/takeaway)
            if (
                used_templates
                and suggestion.template_id == used_templates[-1]
                and suggestion.template_id not in ("cover", "takeaway")
            ):
                # Pick an alternative template
                alt = self._pick_alternative_template(
                    suggestion.template_id, used_templates, item, i, slide_count
                )
                if alt:
                    suggestion = alt
            template_plan.append(suggestion)
            used_templates.append(suggestion.template_id)

        # Build outline context string (shared across all slides)
        outline_context = f"Titre : {pres.title}\nSujet : {pres.prompt or pres.title}\n\nPLAN COMPLET :\n"
        for i, item in enumerate(pres.outline):
            t = item.get("title", f"Section {i + 1}")
            bullets = item.get("bullets", [])
            outline_context += f"  {i + 1}. {t}\n"
            for b in bullets:
                outline_context += f"     - {b}\n"

        # Delete existing slides
        for existing in pres.slides:
            await db.delete(existing)
        await db.flush()

        # Generate each slide individually with full context
        slides: list[PresentationSlide] = []
        slide_ids: list[str] = []
        prev_layout = ""

        for i, item in enumerate(pres.outline):
            suggestion = template_plan[i]
            template_obj = get_template(suggestion.template_id)

            slide_data = await self._generate_and_validate_slide(
                db=db,
                tenant_id=tenant_id,
                presentation_id=pres_id,
                outline_item=item,
                slide_index=i,
                total_slides=slide_count,
                prev_layout=prev_layout,
                rag_context=rag_context,
                language=lang,
                style=style,
                theme_data=theme_data,
                # Enriched context for this slide
                full_outline_context=outline_context,
                forced_template=suggestion,
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

            logger.info(f"Generated slide {i + 1}/{slide_count} ({suggestion.template_id}) for {pres_id}")

            if on_slide_progress:
                await on_slide_progress(slide, i, slide_count)

        pres.slide_order = slide_ids
        pres.status = PresentationStatus.READY.value
        pres.version = pres.version + 1
        await db.flush()

        return slides

    @staticmethod
    def _pick_alternative_template(
        current_id: str,
        used: list[str],
        outline_item: dict,
        slide_index: int,
        total_slides: int,
    ) -> TemplateSuggestion | None:
        """Pick a different template to avoid consecutive duplicates."""
        # Alternatives by category
        _ALTERNATIVES = {
            "cards_3": ["features_icons", "kpi_3", "timeline"],
            "cards_4": ["cards_3", "features_icons", "kpi_3"],
            "features_icons": ["cards_3", "cards_4", "timeline"],
            "kpi_3": ["chart", "big_number", "cards_3"],
            "big_number": ["kpi_3", "chart", "cards_3"],
            "timeline": ["process_steps", "roadmap", "cards_3"],
            "process_steps": ["timeline", "roadmap", "features_icons"],
            "roadmap": ["timeline", "process_steps", "cards_3"],
            "comparison_2col": ["pros_cons", "before_after", "cards_3"],
            "pros_cons": ["comparison_2col", "before_after", "kpi_3"],
            "before_after": ["comparison_2col", "pros_cons", "cards_3"],
            "chart": ["kpi_3", "big_number", "cards_3"],
            "quote": ["big_number", "cards_3", "features_icons"],
        }
        alts = _ALTERNATIVES.get(current_id, ["cards_3", "features_icons", "timeline"])
        recent = set(used[-2:]) if len(used) >= 2 else set(used)
        for alt_id in alts:
            if alt_id not in recent:
                template = get_template(alt_id)
                if template:
                    return TemplateSuggestion(
                        template_id=alt_id,
                        confidence=0.65,
                        reason=f"diversity: replaced consecutive {current_id}",
                        intent=template.intent,
                    )
        return None

    @staticmethod
    def _detect_template_from_instruction(instruction: str) -> TemplateSuggestion | None:
        """Detect visual type from user instruction and return matching template."""
        lower = instruction.lower()
        _INSTRUCTION_KEYWORDS = [
            (["graphique", "chart", "courbe", "diagramme", "camembert", "barres", "pie", "donut"], "chart"),
            (["timeline", "chronologie", "frise", "étapes", "processus"], "timeline"),
            (["stats", "chiffres", "kpi", "métriques", "statistiques", "chiffre clé", "nombre"], "kpi_3"),
            (["comparaison", "comparer", "versus", " vs ", "côte à côte"], "comparison_2col"),
            (["pour contre", "pros cons", "avantages", "inconvénients"], "pros_cons"),
            (["avant après", "before after", "transformation"], "before_after"),
            (["cartes", "cards", "box", "grille"], "cards_3"),
            (["icônes", "icons", "features", "fonctionnalités"], "features_icons"),
            (["citation", "quote", "témoignage"], "quote"),
            (["pyramide", "funnel", "entonnoir"], "pyramid_group"),
            (["escalier", "staircase", "progression"], "process_steps"),
            (["équipe", "team", "profils"], "team"),
        ]
        for keywords, template_id in _INSTRUCTION_KEYWORDS:
            if any(kw in lower for kw in keywords):
                template = get_template(template_id)
                if template:
                    return TemplateSuggestion(
                        template_id=template_id,
                        confidence=1.0,
                        reason=f"instruction-detected: {template_id}",
                        intent=template.intent,
                    )
        return None

    def _parse_batch_slides(
        self,
        raw: str,
        outline: list[dict],
        expected_count: int,
    ) -> list[dict]:
        """Parse the batch LLM response into individual slide dicts.

        Handles: valid JSON array, truncated JSON, and fallback to safe templates.
        """
        parsed = self._parse_json(raw)
        if not parsed:
            logger.error("Batch slide generation: failed to parse JSON, using fallbacks")
            return [
                get_safe_fallback(
                    outline[i] if i < len(outline) else {"title": f"Slide {i+1}", "bullets": []},
                    i,
                    expected_count,
                )
                for i in range(expected_count)
            ]

        # Extract slides array
        raw_slides = parsed.get("slides", [])
        if not isinstance(raw_slides, list):
            raw_slides = [parsed] if "content_json" in parsed else []

        # Validate each slide, fallback for invalid ones
        result: list[dict] = []
        for i in range(expected_count):
            if i < len(raw_slides):
                slide_data = raw_slides[i]
                try:
                    validated = SlideContent.model_validate(slide_data)
                    result.append(validated.model_dump())
                    continue
                except (ValidationError, Exception) as e:
                    logger.warning(f"Slide {i} validation failed: {e}")

            # Fallback for missing/invalid slides
            outline_item = outline[i] if i < len(outline) else {"title": f"Slide {i+1}", "bullets": []}
            result.append(get_safe_fallback(outline_item, i, expected_count))

        return result

    async def regenerate_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
        request: RegenerateSlideRequest,
    ) -> PresentationSlide | None:
        """Regenerate a single slide with optional user instruction."""
        slide = await self.get_slide(db, tenant_id, pres_id, slide_id)
        if not slide:
            return None

        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
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

        # Resolve theme data for prompt enrichment
        theme_data = None
        if pres.theme_id:
            theme = await db.get(PresentationTheme, pres.theme_id)
            if theme:
                theme_data = theme.theme_data

        # Current content for "modify, don't recreate" approach
        current_content = slide.content_json if isinstance(slide.content_json, list) else None

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
            user_instruction=request.instruction.strip() if request.instruction else "",
            target_template=request.target_template,
            current_content=current_content,
            theme_data=theme_data,
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
        model: str | None = None,
    ) -> str:
        """Make LLM call and log to generation_runs."""
        effective_model = model or self.model
        run = PresentationGenerationRun(
            tenant_id=tenant_id,
            presentation_id=presentation_id,
            slide_id=slide_id,
            purpose=purpose,
            model=effective_model,
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
                model=effective_model,
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
        user_instruction: str = "",
        target_template: str | None = None,
        current_content: list[dict] | None = None,
        theme_data: dict | None = None,
        full_outline_context: str = "",
        forced_template: TemplateSuggestion | None = None,
    ) -> dict:
        """Generate a slide with enriched prompt → validation → normalization → repair → fallback.

        Pipeline: generation → schema validation → design normalization → repair → result
        """
        # 1. Determine template: instruction keywords > forced > target > auto-suggest
        instruction_template = self._detect_template_from_instruction(user_instruction) if user_instruction else None
        if instruction_template:
            suggestion = instruction_template
        elif forced_template:
            suggestion = forced_template
        elif target_template:
            template_obj = get_template(target_template)
            suggestion = TemplateSuggestion(
                template_id=target_template,
                confidence=1.0,
                reason=f"user-requested: {target_template}",
                intent=template_obj.intent if template_obj else SlideIntent.INFORM,
            )
        else:
            suggestion = suggest_template(outline_item, slide_index, total_slides)

        template_obj = get_template(suggestion.template_id)

        # 2. Suggest icons based on content
        combined_text = f"{outline_item.get('title', '')} {' '.join(outline_item.get('bullets', []))}"
        suggested_icons = suggest_icons_for_content(combined_text, max_results=5)

        # 3. Build enriched system prompt
        system_prompt = SLIDE_SYSTEM_PROMPT.format(
            language=language,
            style=style,
            rag_context=rag_context,
        )

        # Inject icon policy (compact: only names list)
        system_prompt += ICON_POLICY_SECTION.format(
            icon_names=get_icon_names_for_prompt(max_icons=40),
        )

        # Inject design constraints
        system_prompt += DESIGN_CONSTRAINTS_SECTION

        # Inject theme context if available
        if theme_data:
            colors = theme_data.get("colors", {})
            fonts = theme_data.get("fonts", {})
            system_prompt += THEME_CONTEXT_SECTION.format(
                primary=colors.get("primary", ""),
                secondary=colors.get("secondary", ""),
                accent=colors.get("accent", ""),
                heading_font=fonts.get("heading", "Inter"),
                body_font=fonts.get("body", "Inter"),
                border_radius=theme_data.get("border_radius", "12px"),
            )

        # 4. Build enriched user prompt — frame as visual topics, not text bullets
        topics = outline_item.get("bullets", [])
        user_prompt = (
            f"Slide {slide_index + 1}/{total_slides}.\n"
            f"Sujet : {outline_item.get('title', '')}\n"
            f"Thèmes à illustrer VISUELLEMENT (ne PAS copier en texte brut) :\n"
            + "\n".join(f"- {b}" for b in topics)
            + f"\n\nLayout précédent : {prev_layout or 'aucun'} (utilise un layout DIFFÉRENT)."
            + f"\n\nRAPPEL : suis le TEMPLATE OBLIGATOIRE ci-dessous. Ne génère PAS de bullet_group ni de texte seul."
        )

        # Inject full outline context (so each slide knows the full presentation plan)
        if full_outline_context:
            user_prompt += "\n" + OUTLINE_CONTEXT_SECTION.format(
                outline_context=full_outline_context,
                slide_number=slide_index + 1,
                total_slides=total_slides,
            )

        # Inject template hint
        user_prompt += "\n" + get_template_hint_for_prompt(suggestion)

        # Inject suggested icons
        if suggested_icons:
            user_prompt += f"\nIcônes recommandées : {', '.join(suggested_icons)}"

        # Inject user instruction (highest priority)
        if user_instruction:
            user_prompt += "\n" + USER_INSTRUCTION_SECTION.format(
                instruction=user_instruction,
            )

        # Inject current content for regeneration
        if current_content:
            truncated = json.dumps(current_content, ensure_ascii=False)[:1500]
            user_prompt += "\n" + CURRENT_CONTENT_SECTION.format(
                current_content=truncated,
            )

        # 5. Generate (using Mistral Large for quality)
        raw = await self._tracked_llm_call(
            db=db,
            tenant_id=tenant_id,
            presentation_id=presentation_id,
            slide_id=None,
            purpose=RunPurpose.SLIDE_GEN.value if not user_instruction else RunPurpose.REGENERATE.value,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=6144,  # Increased for complex slides
            model=self.slide_model,
        )

        # 6. Validate schema
        result, errors = self._validate_slide_json(raw)
        if result:
            # 7. Design normalization (LLM proposes, engine civilizes)
            result = normalize_slide(result, template=template_obj, theme=theme_data)
            return result

        # 8. Repair loop
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
                result = normalize_slide(result, template=template_obj, theme=theme_data)
                return result
            current_raw = repaired

        # 9. Premium safe fallback (never a bare bullet_group)
        logger.error(
            f"Slide {slide_index} repair failed after {MAX_REPAIR_ATTEMPTS} attempts, "
            f"using safe template '{suggestion.template_id}'"
        )
        fallback = get_safe_fallback(outline_item, slide_index, total_slides)
        return normalize_slide(fallback, template=template_obj, theme=theme_data)

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

    def _parse_json(self, raw: str) -> dict | None:
        """Parse JSON with truncation repair."""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return _repair_truncated_json(raw)


# Singleton
presentation_service = PresentationService()
