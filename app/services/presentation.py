"""Presentation service — CRUD, AI generation (JSON template pipeline), export orchestration."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.presentation import (
    AssetKind,
    AssetStatus,
    Presentation,
    PresentationAsset,
    PresentationExport,
    PresentationGenerationRun,
    PresentationSlide,
    PresentationStatus,
    PresentationTheme,
    RunPurpose,
)
from app.schemas.presentation import (
    ExportRequest,
    GenerateSlidesRequest,
    OutlineItem,
    PresentationCreate,
    PresentationUpdate,
    RegenerateSlideRequest,
    SlideUpdate,
    ThemeCreate,
    ThemeData,
)
from app.services.presentation_icons import suggest_icons_for_content
from app.services.presentation_slide_generator import (
    edit_slide_content,
    generate_full_deck,
)
from app.services.retrieval import RetrievalService

settings = get_settings()
logger = logging.getLogger(__name__)


class PresentationService:
    """Service for presentation CRUD and AI-assisted slide generation."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.mistral_api_key,
            base_url="https://api.mistral.ai/v1",
        )
        self.retrieval = RetrievalService()
        self.model = settings.llm_model
        self.slide_model = settings.llm_slide_model
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
            layout_type="basic-info-slide",
            content_json={
                "title": "New Slide",
                "description": "Add content here.",
                "image": {"__image_prompt__": "abstract professional background"},
            },
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
    #  AI Generation — JSON template pipeline
    # ══════════════════════════════════════════════

    async def generate_slides(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        request: GenerateSlidesRequest,
        on_slide_progress: Any | None = None,
    ) -> list[PresentationSlide]:
        """Generate slides using 3-step JSON template pipeline.

        Pipeline:
        1. LLM outline generation → N markdown outlines
        2. LLM layout selection → layout_id per slide
        3. Per-slide JSON content generation (parallel batches)
        4. Icon resolution + image prompt extraction
        5. Persist each slide to DB + SSE event
        """
        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not pres:
            raise ValueError(f"Presentation {pres_id} not found")
        if not pres.prompt:
            raise ValueError("No prompt — set prompt first")

        pres.status = PresentationStatus.GENERATING_SLIDES.value
        await db.flush()

        lang = pres.settings.get("language", "fr-FR")
        style = pres.settings.get("style", "professional")
        slide_count = pres.settings.get("slide_count", 8)

        logger.info(
            "generate_slides: pres=%s, prompt=%.80s..., slide_count=%d, lang=%s",
            pres_id, pres.prompt or "", slide_count, lang,
        )

        # Optional RAG context
        rag_context = ""
        if request.collection_ids:
            chunks = await self.retrieval.retrieve(
                query=pres.prompt or pres.title,
                tenant_id=tenant_id,
                collection_ids=request.collection_ids,
                db=db,
            )
            rag_context = self.retrieval.build_context(chunks)
            logger.info(
                "generate_slides: RAG context=%d chars from %d collections",
                len(rag_context), len(request.collection_ids),
            )

        # Resolve theme
        theme_data = None
        if pres.theme_id:
            theme = await db.get(PresentationTheme, pres.theme_id)
            if theme:
                theme_data = theme.theme_data

        logger.info(
            "generate_slides: theme=%s",
            "auto-creating" if not theme_data else str(pres.theme_id),
        )

        try:
            # Auto-create theme if none selected
            if not theme_data:
                theme_data = await self._auto_create_theme(db, tenant_id, pres)

            # Delete existing slides
            for existing in pres.slides:
                await db.delete(existing)
            await db.flush()

            # Build LLM call wrapper — no DB tracking to be safe for parallel use.
            # _tracked_llm_call shares the same AsyncSession which is NOT safe
            # under asyncio.gather (concurrent flush). Instead, call the API
            # directly and log to stdout.
            async def llm_call(sys_prompt: str, usr_prompt: str) -> str:
                t0 = time.monotonic()
                logger.info(
                    "LLM call: model=%s, prompt_len=%d+%d",
                    self.slide_model, len(sys_prompt), len(usr_prompt),
                )
                response = await self.client.chat.completions.create(
                    model=self.slide_model,
                    max_tokens=4096,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": usr_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or ""
                duration_ms = int((time.monotonic() - t0) * 1000)
                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0
                logger.info(
                    "LLM call: success, tokens=%d→%d, %dms",
                    tokens_in, tokens_out, duration_ms,
                )
                logger.debug("LLM call: response first 300 chars: %s", content[:300])
                return content

            logger.info("generate_slides: launching 3-step pipeline")
            # Run the 3-step pipeline
            deck = await generate_full_deck(
                content=pres.prompt,
                n_slides=slide_count,
                language=lang,
                additional_context=rag_context,
                instructions=pres.settings.get("instructions"),
                tone=style,
                verbosity=pres.settings.get("verbosity"),
                llm_call=llm_call,
            )

            logger.info("generate_slides: deck returned %d slides", len(deck))

            # Persist slides
            slides: list[PresentationSlide] = []
            slide_ids: list[str] = []
            outline_items: list[dict] = []

            for i, slide_data in enumerate(deck):
                layout_id = slide_data["layout_id"]
                content_json = slide_data["content_json"]
                speaker_notes = slide_data.get("speaker_notes", "")
                logger.debug(
                    "generate_slides: slide %d content_json keys=%s, layout=%s",
                    i, list(content_json.keys()), layout_id,
                )

                # Post-process: resolve icons + capitalize titles
                content_json = self._resolve_icons(content_json)
                content_json = self._post_process_content(content_json)

                # Clean image placeholders (images are uploaded manually)
                content_json = self._clean_image_placeholders(content_json)

                slide = PresentationSlide(
                    presentation_id=pres_id,
                    position=i,
                    layout_type=layout_id,
                    content_json=content_json,
                    speaker_notes=speaker_notes,
                )
                db.add(slide)
                await db.flush()
                await db.refresh(slide)

                slides.append(slide)
                slide_ids.append(str(slide.id))

                # Build outline item for storage
                outline_items.append({
                    "title": content_json.get("title", content_json.get("heading", f"Slide {i + 1}")),
                    "bullets": [],
                    "detailed_content": "",
                    "source_mode": "json_template",
                })

                logger.info(
                    "Saved slide %d/%d (layout=%s) for %s",
                    i + 1, len(deck), layout_id, pres_id,
                )

                if on_slide_progress:
                    try:
                        await on_slide_progress(slide, i, len(deck))
                    except Exception as cb_err:
                        logger.warning("Progress callback failed: %s", cb_err)

            pres.outline = outline_items
            pres.slide_order = slide_ids
            pres.status = PresentationStatus.READY.value
            pres.version = pres.version + 1
            await db.flush()

            return slides

        except Exception as fatal:
            logger.exception("Fatal error in slide generation for %s: %s", pres_id, fatal)
            pres.status = PresentationStatus.ERROR.value
            await db.flush()
            raise

    async def regenerate_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
        request: RegenerateSlideRequest,
    ) -> PresentationSlide | None:
        """Regenerate a single slide with user instruction.

        Uses instruction-based editing: sends current content + instruction to LLM,
        which returns updated JSON matching the same template schema.
        """
        slide = await self.get_slide(db, tenant_id, pres_id, slide_id)
        if not slide:
            return None

        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not pres:
            return None

        lang = pres.settings.get("language", "fr-FR")

        async def llm_call(sys_prompt: str, usr_prompt: str) -> str:
            return await self._tracked_llm_call(
                db=db,
                tenant_id=tenant_id,
                presentation_id=pres_id,
                slide_id=slide_id,
                purpose="REGENERATE",
                system_prompt=sys_prompt,
                user_prompt=usr_prompt,
                max_tokens=4096,
                model=self.slide_model,
            )

        try:
            new_content = await edit_slide_content(
                current_content=slide.content_json if isinstance(slide.content_json, dict) else {},
                instruction=request.instruction or "Improve this slide",
                layout_id=slide.layout_type,
                language=lang,
                llm_call=llm_call,
            )

            # Post-process: resolve icons + capitalize titles + images
            new_content = self._resolve_icons(new_content)
            new_content = self._post_process_content(new_content)
            new_content = self._clean_image_placeholders(new_content)

            # Extract speaker note
            speaker_notes = new_content.pop("__speaker_note__", slide.speaker_notes or "")

            slide.content_json = new_content
            slide.speaker_notes = speaker_notes

            pres.version = pres.version + 1
            await db.flush()
            await db.refresh(slide)
            return slide

        except Exception as e:
            logger.error("Slide regeneration failed for %s: %s", slide_id, e)
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
        """Make LLM call with JSON response format and log to generation_runs."""
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

        logger.info(
            "LLM call: model=%s, purpose=%s, prompt_len=%d+%d",
            effective_model, purpose, len(system_prompt), len(user_prompt),
        )

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
            logger.info(
                "LLM call: success, tokens=%d→%d, %dms",
                run.tokens_in, run.tokens_out, run.duration_ms,
            )
            logger.debug("LLM call: response first 300 chars: %s", content[:300])
            return content
        except Exception as e:
            run.status = "error"
            run.error = str(e)[:2000]
            run.duration_ms = int((time.monotonic() - t0) * 1000)
            raise
        finally:
            await db.flush()

    # ══════════════════════════════════════════════
    #  Internal — helpers
    # ══════════════════════════════════════════════

    async def _auto_create_theme(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres: Presentation,
    ) -> dict:
        """Auto-create a default Minim theme if none is selected."""
        try:
            from app.schemas.presentation import ThemeColors, ThemeData, ThemeFonts
            auto_theme_data = ThemeData(
                colors=ThemeColors(
                    primary="#323F50",
                    secondary="#313F4F",
                    accent="#EFEBEA",
                    background="#FFFFFF",
                    text="#323F50",
                    heading="#323F50",
                    muted="#8896A6",
                ),
                fonts=ThemeFonts(
                    heading="Plus Jakarta Sans",
                    body="DM Sans",
                ),
            )
            auto_theme = PresentationTheme(
                tenant_id=tenant_id,
                name="Auto — Minim",
                is_builtin=False,
                theme_data=auto_theme_data.model_dump(),
            )
            db.add(auto_theme)
            await db.flush()
            await db.refresh(auto_theme)

            pres.theme_id = auto_theme.id
            await db.flush()

            logger.info("Auto-created theme '%s' for %s", auto_theme.name, pres.id)
            return auto_theme.theme_data
        except Exception as theme_err:
            logger.warning("Failed to auto-create theme: %s", theme_err)
            return {}

    @staticmethod
    def _clean_image_placeholders(content: dict[str, Any]) -> dict[str, Any]:
        """Strip __image_prompt__ objects, keep empty image slots for manual upload.

        LLM generates {"__image_prompt__": "..."} but images are uploaded manually.
        Replace with empty object {} so templates show the upload placeholder.
        """
        import copy
        result = copy.deepcopy(content)

        for key, value in list(result.items()):
            if isinstance(value, dict) and "__image_prompt__" in value:
                # Keep as empty image slot (no __image_url__ → template shows placeholder)
                result[key] = {}
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        for sub_key, sub_value in list(item.items()):
                            if isinstance(sub_value, dict) and "__image_prompt__" in sub_value:
                                item[sub_key] = {}

        return result

    @staticmethod
    def _post_process_content(content: dict[str, Any]) -> dict[str, Any]:
        """Post-process content_json: capitalize titles, strip markdown, clean up text."""
        import re

        def _capitalize(text: str) -> str:
            """Capitalize first letter of a string, preserving the rest."""
            if not text:
                return text
            return text[0].upper() + text[1:]

        def _strip_markdown(text: str) -> str:
            """Remove markdown formatting from text (bold, italic, links, headers)."""
            if not text:
                return text
            # Bold: **text** or __text__
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'__(.+?)__', r'\1', text)
            # Italic: *text* or _text_
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
            # Inline code: `text`
            text = re.sub(r'`(.+?)`', r'\1', text)
            # Links: [text](url)
            text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
            # Headers: # text
            text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
            return text

        def _clean_str(text: str) -> str:
            return _strip_markdown(text)

        # Clean all top-level string fields
        for key, value in content.items():
            if isinstance(value, str):
                content[key] = _clean_str(value)

        # Clean strings inside arrays of dicts
        for key, value in content.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            if isinstance(sub_value, str):
                                item[sub_key] = _clean_str(sub_value)

        # Capitalize top-level title/heading fields
        for key in ("title", "heading"):
            if key in content and isinstance(content[key], str):
                content[key] = _capitalize(content[key])

        # Capitalize bullet titles and section titles in arrays
        for key, value in content.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        for sub_key in ("title", "heading", "name", "label"):
                            if sub_key in item and isinstance(item[sub_key], str):
                                item[sub_key] = _capitalize(item[sub_key])

        return content

    def _resolve_icons(self, content: dict[str, Any]) -> dict[str, Any]:
        """Walk content_json and resolve __icon_query__ objects to icon name strings.

        Replaces {"__icon_query__": "rocket"} with the resolved Lucide icon name "Rocket".
        Templates expect icon fields to be plain strings, not objects.
        """
        import copy
        result = copy.deepcopy(content)

        def _resolve_one(query: str) -> str:
            try:
                from app.services.presentation_icons import resolve_icon, VALID_ICON_NAMES
                # If the LLM already gave us an exact Lucide name, use it directly
                if query in VALID_ICON_NAMES:
                    return query
                # Try semantic resolution
                resolved = resolve_icon(query)
                if resolved:
                    return resolved
                # Fallback to content-based suggestion
                icons = suggest_icons_for_content(query, max_results=1)
                return icons[0] if icons else "Lightbulb"
            except Exception:
                return "Lightbulb"

        # Top-level fields: e.g. content_json.icon = {"__icon_query__": "..."}
        for key, value in list(result.items()):
            if isinstance(value, dict) and "__icon_query__" in value:
                result[key] = _resolve_one(value["__icon_query__"])
            elif isinstance(value, list):
                # Array items: e.g. bulletPoints[].icon = {"__icon_query__": "..."}
                for item in value:
                    if isinstance(item, dict):
                        for sub_key, sub_value in list(item.items()):
                            if isinstance(sub_value, dict) and "__icon_query__" in sub_value:
                                item[sub_key] = _resolve_one(sub_value["__icon_query__"])

        return result


# Singleton
presentation_service = PresentationService()
