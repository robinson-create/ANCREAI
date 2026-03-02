"""JSON template slide generator — 3-step pipeline.

Step 1: generate_outline()  — LLM produces N markdown outlines
Step 2: select_layouts()    — LLM picks a layout index per slide
Step 3: generate_slide_content() — LLM fills JSON per template schema (parallelisable)

Also: edit_slide_content() for instruction-based regeneration.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from typing import Any, Callable, Awaitable

from pydantic import BaseModel, Field

from app.services.presentation_layout_registry import (
    LAYOUT_REGISTRY,
    build_layout_description_for_llm,
    get_layout_by_index,
    get_schema_for_llm,
)
from app.services.presentation_prompts import (
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_USER_PROMPT,
    STRUCTURE_SYSTEM_PROMPT,
    STRUCTURE_USER_PROMPT,
    SLIDE_CONTENT_SYSTEM_PROMPT,
    SLIDE_CONTENT_USER_PROMPT,
    SLIDE_EDIT_SYSTEM_PROMPT,
    SLIDE_EDIT_USER_PROMPT,
    build_outline_system_prompt,
    build_structure_system_prompt,
    build_slide_content_system_prompt,
)

logger = logging.getLogger(__name__)

# Type alias: async (system_prompt, user_prompt) -> raw string
LLMCallFn = Callable[[str, str], Awaitable[str]]

# Batch size for parallel slide content generation
_BATCH_SIZE = 5


# ══════════════════════════════════════════════
#  Data models
# ══════════════════════════════════════════════


class SlideOutline(BaseModel):
    """One slide in the generated outline."""
    slide_number: int
    content: str  # markdown description of what the slide should contain


class PresentationOutline(BaseModel):
    """Full outline: a list of slide outlines."""
    slides: list[SlideOutline] = Field(default_factory=list)


class LayoutSelection(BaseModel):
    """Layout selection result: one index per slide."""
    slides: list[int] = Field(default_factory=list)


# ══════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════


def _ensure_dict(raw: str) -> dict[str, Any]:
    """Parse a raw LLM response into a dict, stripping markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


def _ensure_list(raw: str) -> list[Any]:
    """Parse a raw LLM response into a list, stripping markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    data = json.loads(cleaned)
    if isinstance(data, dict):
        # Try common keys
        for key in ("slides", "layout_indices", "indices", "selections"):
            if key in data and isinstance(data[key], list):
                return data[key]
        # If dict has numeric keys or a single list value
        for v in data.values():
            if isinstance(v, list):
                return v
    if isinstance(data, list):
        return data
    raise ValueError(f"Expected list, got {type(data)}")


# ══════════════════════════════════════════════
#  Step 1: Outline generation
# ══════════════════════════════════════════════


async def generate_outline(
    *,
    content: str,
    n_slides: int,
    language: str,
    additional_context: str = "",
    instructions: str | None = None,
    tone: str | None = None,
    verbosity: str | None = None,
    llm_call: LLMCallFn,
) -> PresentationOutline:
    """Generate N slide outlines via LLM.

    Returns PresentationOutline with exactly n_slides entries.
    """
    from datetime import datetime

    system_prompt = build_outline_system_prompt(
        instructions=instructions,
        tone=tone,
        verbosity=verbosity,
    )
    user_prompt = OUTLINE_USER_PROMPT.format(
        content=content,
        language=language,
        n_slides=n_slides,
        current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M"),
        additional_context=additional_context or "None",
    )

    logger.info("Outline: calling LLM with n_slides=%d, lang=%s", n_slides, language)

    try:
        raw = await llm_call(system_prompt, user_prompt)
        logger.debug("Outline: raw LLM response (first 1000 chars): %s", raw[:1000])
        data = _ensure_dict(raw)

        slides_data = data.get("slides", [])
        if not isinstance(slides_data, list):
            logger.warning("Outline: 'slides' key missing or not a list, got keys=%s", list(data.keys()))
            slides_data = []

        slides: list[SlideOutline] = []
        for i, item in enumerate(slides_data):
            if isinstance(item, dict):
                slides.append(SlideOutline(
                    slide_number=item.get("slide_number", i + 1),
                    content=item.get("content", item.get("title", f"Slide {i + 1}")),
                ))
            elif isinstance(item, str):
                slides.append(SlideOutline(slide_number=i + 1, content=item))

        logger.info("Outline: parsed %d slides from LLM (requested %d)", len(slides), n_slides)
        outline = PresentationOutline(slides=slides)

    except Exception as e:
        logger.error("Outline generation failed: %s", e, exc_info=True)
        outline = PresentationOutline(slides=[])

    # Pad or trim to match n_slides
    if len(outline.slides) < n_slides:
        logger.warning("Outline: padding %d → %d slides", len(outline.slides), n_slides)
    while len(outline.slides) < n_slides:
        n = len(outline.slides) + 1
        outline.slides.append(SlideOutline(
            slide_number=n,
            content=f"Additional point {n}",
        ))
    if len(outline.slides) > n_slides:
        outline.slides = outline.slides[:n_slides]

    # Re-number
    for i, s in enumerate(outline.slides):
        s.slide_number = i + 1

    logger.info("Outline generated: %d slides", len(outline.slides))
    return outline


# ══════════════════════════════════════════════
#  Step 2: Layout selection
# ══════════════════════════════════════════════


async def select_layouts(
    *,
    outline: PresentationOutline,
    n_slides: int,
    instructions: str | None = None,
    llm_call: LLMCallFn,
) -> list[int]:
    """Ask LLM to select a layout index for each slide.

    Returns a list of layout indices (0-based into LAYOUT_REGISTRY).
    """
    layout_descriptions = build_layout_description_for_llm()

    # Build outline text for the LLM
    outline_lines: list[str] = []
    for s in outline.slides:
        outline_lines.append(f"Slide {s.slide_number}: {s.content}")
    outline_text = "\n".join(outline_lines)

    system_prompt = build_structure_system_prompt(
        layout_descriptions=layout_descriptions,
        n_slides=n_slides,
        instructions=instructions,
    )
    user_prompt = STRUCTURE_USER_PROMPT.format(outline_text=outline_text)

    max_index = len(LAYOUT_REGISTRY) - 1
    logger.info("Layouts: calling LLM for %d slides (max_index=%d)", n_slides, max_index)

    try:
        raw = await llm_call(system_prompt, user_prompt)
        logger.debug("Layouts: raw LLM response: %s", raw[:500])
        indices = _ensure_list(raw)
        logger.info("Layouts: LLM returned %d indices: %s", len(indices), indices)

        # Validate and clamp indices
        result: list[int] = []
        for idx in indices:
            if isinstance(idx, dict):
                idx = idx.get("layout_index", idx.get("index", 0))
            original = int(idx)
            clamped = max(0, min(original, max_index))
            if clamped != original:
                logger.warning("Layouts: clamped index %d → %d", original, clamped)
            result.append(clamped)

    except Exception as e:
        logger.error("Layout selection failed: %s", e, exc_info=True)
        result = []

    # Pad or trim
    if len(result) < n_slides:
        logger.warning("Layouts: padding %d → %d indices (default=1)", len(result), n_slides)
    while len(result) < n_slides:
        result.append(1)  # default to "Basic Info"
    if len(result) > n_slides:
        result = result[:n_slides]

    # Force first slide to intro (index 0) if not already
    if result and result[0] != 0:
        result[0] = 0

    logger.info("Layouts selected: %s", result)
    return result


# ══════════════════════════════════════════════
#  Step 3: Slide content generation
# ══════════════════════════════════════════════


async def generate_slide_content(
    *,
    outline_content: str,
    layout_id: str,
    language: str,
    instructions: str | None = None,
    tone: str | None = None,
    verbosity: str | None = None,
    llm_call: LLMCallFn,
) -> dict[str, Any]:
    """Generate JSON content for a single slide based on its template schema.

    Returns a dict matching the template's JSON schema.
    """
    from datetime import datetime

    logger.info("Slide content: generating for layout=%s", layout_id)

    schema = get_schema_for_llm(layout_id)
    if not schema:
        logger.error("No schema found for layout_id=%s", layout_id)
        return {"title": "Error", "__speaker_note__": "Schema not found"}

    logger.debug("Slide content: schema keys=%s", list(schema.get("properties", {}).keys()))

    system_prompt = build_slide_content_system_prompt(
        instructions=instructions,
        tone=tone,
        verbosity=verbosity,
    )

    # Inject schema into user prompt
    schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
    user_prompt = SLIDE_CONTENT_USER_PROMPT.format(
        current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M"),
        language=language,
        outline_content=outline_content,
    )
    # Append schema to user prompt
    user_prompt += f"\n\n## Slide JSON Schema (follow strictly)\n```json\n{schema_str}\n```"

    try:
        raw = await llm_call(system_prompt, user_prompt)
        logger.debug("Slide content: raw LLM response (first 500 chars): %s", raw[:500])
        content = _ensure_dict(raw)

        # Extract speaker note from content
        if "__speaker_note__" not in content:
            content["__speaker_note__"] = ""

        logger.info("Slide content: generated keys=%s for layout=%s", list(content.keys()), layout_id)
        return content

    except Exception as e:
        logger.error("Slide content: FALLBACK for layout=%s, error=%s", layout_id, e, exc_info=True)
        # Build minimal fallback from schema required fields
        fallback: dict[str, Any] = {}
        props = schema.get("properties", {})
        for key, prop in props.items():
            if prop.get("type") == "string":
                fallback[key] = key.replace("_", " ").title()
            elif prop.get("type") == "array":
                fallback[key] = []
            elif prop.get("type") == "object":
                fallback[key] = {}
        fallback["__speaker_note__"] = ""
        logger.warning("Slide content: fallback keys=%s", list(fallback.keys()))
        return fallback


# ══════════════════════════════════════════════
#  Step 3b: Slide editing (instruction-based)
# ══════════════════════════════════════════════


async def edit_slide_content(
    *,
    current_content: dict[str, Any],
    instruction: str,
    layout_id: str,
    language: str,
    llm_call: LLMCallFn,
) -> dict[str, Any]:
    """Edit a slide's content based on user instruction.

    Returns updated dict matching the template's JSON schema.
    """
    schema = get_schema_for_llm(layout_id)
    schema_str = json.dumps(schema, indent=2, ensure_ascii=False) if schema else "{}"

    system_prompt = SLIDE_EDIT_SYSTEM_PROMPT
    user_prompt = SLIDE_EDIT_USER_PROMPT.format(
        current_content=json.dumps(current_content, indent=2, ensure_ascii=False),
        instruction=instruction,
        language=language,
    )
    user_prompt += f"\n\n## Slide JSON Schema (follow strictly)\n```json\n{schema_str}\n```"

    try:
        raw = await llm_call(system_prompt, user_prompt)
        content = _ensure_dict(raw)
        if "__speaker_note__" not in content:
            content["__speaker_note__"] = current_content.get("__speaker_note__", "")
        return content

    except Exception as e:
        logger.error("Slide edit failed for %s: %s", layout_id, e)
        return current_content


# ══════════════════════════════════════════════
#  Orchestrator: full deck generation
# ══════════════════════════════════════════════


async def generate_full_deck(
    *,
    content: str,
    n_slides: int,
    language: str,
    additional_context: str = "",
    instructions: str | None = None,
    tone: str | None = None,
    verbosity: str | None = None,
    llm_call: LLMCallFn,
    on_slide_ready: Callable[[int, str, dict[str, Any]], Awaitable[None]] | None = None,
) -> list[dict[str, Any]]:
    """Generate a full presentation deck using the 3-step pipeline.

    Args:
        content: User's presentation prompt/content
        n_slides: Number of slides to generate
        language: Output language
        additional_context: RAG-retrieved context
        instructions: User instructions
        tone: Presentation tone
        verbosity: Content verbosity level
        llm_call: Async LLM call function
        on_slide_ready: Optional callback(slide_index, layout_id, slide_content)
            Called as each slide is generated (for SSE streaming).

    Returns:
        List of dicts, each with:
        - "layout_id": str
        - "content_json": dict (template-specific JSON)
        - "speaker_notes": str
    """
    logger.info("Full deck: starting pipeline for %d slides, lang=%s", n_slides, language)

    # Step 1: Generate outline
    outline = await generate_outline(
        content=content,
        n_slides=n_slides,
        language=language,
        additional_context=additional_context,
        instructions=instructions,
        tone=tone,
        verbosity=verbosity,
        llm_call=llm_call,
    )

    # Step 2: Select layouts
    layout_indices = await select_layouts(
        outline=outline,
        n_slides=n_slides,
        instructions=instructions,
        llm_call=llm_call,
    )

    # Step 3: Generate content per slide (in batches for parallelism)
    slides: list[dict[str, Any]] = [{}] * n_slides

    async def _generate_one(index: int) -> None:
        layout_index = layout_indices[index]
        layout = get_layout_by_index(layout_index)
        layout_id = layout["id"] if layout else "basic-info-slide"

        slide_content = await generate_slide_content(
            outline_content=outline.slides[index].content,
            layout_id=layout_id,
            language=language,
            instructions=instructions,
            tone=tone,
            verbosity=verbosity,
            llm_call=llm_call,
        )

        # Extract speaker note
        speaker_notes = slide_content.pop("__speaker_note__", "")

        result = {
            "layout_id": layout_id,
            "content_json": slide_content,
            "speaker_notes": speaker_notes,
        }
        slides[index] = result

        if on_slide_ready:
            await on_slide_ready(index, layout_id, slide_content)

    # Process in batches
    for batch_start in range(0, n_slides, _BATCH_SIZE):
        batch_end = min(batch_start + _BATCH_SIZE, n_slides)
        logger.info("Full deck: generating batch slides %d-%d of %d", batch_start + 1, batch_end, n_slides)
        tasks = [_generate_one(i) for i in range(batch_start, batch_end)]
        await asyncio.gather(*tasks)

    layout_ids = [s.get("layout_id", "?") for s in slides]
    logger.info("Full deck: complete, %d slides, layouts=%s", len(slides), layout_ids)
    return slides
