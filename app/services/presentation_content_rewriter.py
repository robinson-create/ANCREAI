"""Content rewriter — adapts brief content to template slot constraints.

The brief says WHAT to communicate. The rewriter makes it FIT
into the template's exact character limits and structure.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Awaitable

from app.services.presentation_briefs import SlideBrief
from app.services.presentation_prompts import (
    TEMPLATE_REWRITE_PROMPTS,
    TEMPLATE_REWRITE_SYSTEM_PROMPT,
)
from app.services.presentation_template_registry import TemplateDefinition

logger = logging.getLogger(__name__)


async def rewrite_brief_for_template(
    brief: SlideBrief,
    template: TemplateDefinition,
    language: str,
    style: str,
    rag_context: str,
    llm_call: Callable[..., Awaitable[str]],
    original_prompt: str = "",
    detailed_content: str = "",
) -> dict[str, Any]:
    """Rewrite brief content to fit template slot constraints.

    Args:
        brief: The semantic brief with raw content
        template: The selected template with character limits
        language: Output language
        style: Presentation style
        rag_context: RAG context for enrichment
        llm_call: Async function to call the LLM (signature: system_prompt, user_prompt -> str)
        original_prompt: The user's original detailed prompt
        detailed_content: Detailed content extracted from outline for this slide

    Returns:
        Dict with filled slot content, structure depends on template type.
    """
    # Get template-specific rewrite prompt
    rewrite_prompt = TEMPLATE_REWRITE_PROMPTS.get(template.id)
    if not rewrite_prompt:
        logger.warning("No rewrite prompt for template %s, using brief content directly", template.id)
        return _direct_fill_from_brief(brief, template)

    # Format the rewrite prompt with block count if needed
    block_count = max(len(brief.blocks), template.min_blocks)
    block_count = min(block_count, template.max_blocks)
    rewrite_prompt = rewrite_prompt.format(block_count=block_count)

    # Build the brief context for the LLM
    brief_context = _format_brief_for_rewrite(brief)

    # System prompt with constraints
    max_title_words = 5 if template.density == "high" else 6
    system_prompt = TEMPLATE_REWRITE_SYSTEM_PROMPT.format(
        max_title_words=max_title_words,
        language=language,
    )

    # Build source data section from original prompt + detailed_content
    source_data_section = ""
    if detailed_content:
        source_data_section += f"\nDONNÉES SOURCE POUR CE SLIDE (à utiliser en priorité) :\n{detailed_content}\n"
    if original_prompt:
        source_data_section += f"\nPROMPT ORIGINAL DE L'UTILISATEUR (pour contexte et données) :\n{original_prompt}\n"

    # User prompt: brief + source data + rewrite instructions
    user_prompt = f"""\
BRIEF SÉMANTIQUE :
{brief_context}
{source_data_section}
TEMPLATE CIBLE : {template.id} ({template.name})

{rewrite_prompt}

IMPORTANT : Utilise les DONNÉES CONCRÈTES du brief et des sources ci-dessus (chiffres, noms, URLs, exemples). Ne généralise PAS.

Style : {style}. Langue : {language}.
"""

    # Call LLM for rewrite
    raw = await llm_call(system_prompt, user_prompt)

    # Parse response
    filled = _parse_rewrite_response(raw, template)
    if filled:
        # Enforce character limits strictly
        return _enforce_char_limits(filled, template)

    # Fallback: direct fill from brief
    logger.warning("Rewrite parse failed for template %s, using direct fill", template.id)
    return _direct_fill_from_brief(brief, template)


def _format_brief_for_rewrite(brief: SlideBrief) -> str:
    """Format brief as readable context for the LLM."""
    lines = [
        f"Objectif : {brief.slide_goal}",
        f"Rôle narratif : {brief.narrative_role.value}",
        f"Message clé : {brief.key_message}",
        f"Titre : {brief.title}",
    ]
    if brief.subtitle:
        lines.append(f"Sous-titre : {brief.subtitle}")

    if brief.blocks:
        lines.append(f"\nBlocs ({len(brief.blocks)}) :")
        for i, block in enumerate(brief.blocks, 1):
            lines.append(f"  {i}. [{block.kind}] {block.title}")
            if block.body:
                lines.append(f"     {block.body}")
            if block.metrics:
                lines.append(f"     Métriques : {', '.join(block.metrics)}")

    return "\n".join(lines)


def _parse_rewrite_response(raw: str, template: TemplateDefinition) -> dict[str, Any] | None:
    """Parse the LLM's rewrite response as JSON."""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        if "```" in raw:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start:end])
                except json.JSONDecodeError:
                    pass
    return None


def _enforce_char_limits(filled: dict[str, Any], template: TemplateDefinition) -> dict[str, Any]:
    """Strictly enforce character limits on all text fields."""
    slot_limits = {slot.id: slot for slot in template.slots}

    def _truncate(text: str, max_chars: int) -> str:
        if not text or max_chars <= 0:
            return text
        if len(text) <= max_chars:
            return text
        # Truncate at word boundary
        truncated = text[:max_chars]
        last_space = truncated.rfind(" ")
        if last_space > max_chars * 0.6:
            truncated = truncated[:last_space]
        return truncated.rstrip() + "…"

    # Handle different response structures based on template
    if "cards" in filled and isinstance(filled["cards"], list):
        for i, card in enumerate(filled["cards"]):
            slot_id = f"card_{i + 1}"
            slot = slot_limits.get(slot_id)
            if slot and isinstance(card, dict):
                card["title"] = _truncate(card.get("title", ""), slot.max_title_chars)
                card["body"] = _truncate(card.get("body", ""), slot.max_body_chars)

    if "steps" in filled and isinstance(filled["steps"], list):
        for i, step in enumerate(filled["steps"]):
            slot_id = f"step_{i + 1}"
            slot = slot_limits.get(slot_id)
            if slot and isinstance(step, dict):
                step["title"] = _truncate(step.get("title", ""), slot.max_title_chars)
                step["body"] = _truncate(step.get("body", ""), slot.max_body_chars)

    if "kpis" in filled and isinstance(filled["kpis"], list):
        for i, kpi in enumerate(filled["kpis"]):
            slot_id = f"kpi_{i + 1}"
            slot = slot_limits.get(slot_id)
            if slot and isinstance(kpi, dict):
                kpi["label"] = _truncate(kpi.get("label", ""), slot.max_title_chars)
                kpi["context"] = _truncate(kpi.get("context", ""), slot.max_body_chars)

    if "sides" in filled and isinstance(filled["sides"], list):
        for i, side in enumerate(filled["sides"]):
            slot_id = f"side_{i + 1}"
            slot = slot_limits.get(slot_id)
            if slot and isinstance(side, dict):
                side["title"] = _truncate(side.get("title", ""), slot.max_title_chars)
                side["body"] = _truncate(side.get("body", ""), slot.max_body_chars)

    if "points" in filled and isinstance(filled["points"], list):
        for i, point in enumerate(filled["points"]):
            slot_id = f"point_{i + 1}"
            slot = slot_limits.get(slot_id)
            if slot and isinstance(point, dict):
                if "text" in point:
                    point["text"] = _truncate(point.get("text", ""), slot.max_title_chars)
                if "title" in point:
                    point["title"] = _truncate(point.get("title", ""), slot.max_title_chars)
                if "body" in point:
                    point["body"] = _truncate(point.get("body", ""), slot.max_body_chars)

    # Handle header/title
    header_slot = slot_limits.get("header") or slot_limits.get("title") or slot_limits.get("statement")
    if header_slot:
        for key in ("header", "title", "statement"):
            if key in filled and isinstance(filled[key], str):
                filled[key] = _truncate(filled[key], header_slot.max_title_chars)

    # Handle subtitle/context
    subtitle_slot = slot_limits.get("subtitle") or slot_limits.get("context")
    if subtitle_slot:
        for key in ("subtitle", "context"):
            if key in filled and isinstance(filled[key], str):
                filled[key] = _truncate(filled[key], subtitle_slot.max_title_chars)

    # Handle quote
    if "quote_text" in filled:
        quote_slot = slot_limits.get("quote_text")
        if quote_slot:
            filled["quote_text"] = _truncate(filled["quote_text"], quote_slot.max_body_chars)
    if "attribution" in filled:
        attr_slot = slot_limits.get("attribution")
        if attr_slot:
            filled["attribution"] = _truncate(filled["attribution"], attr_slot.max_title_chars)

    return filled


def _direct_fill_from_brief(brief: SlideBrief, template: TemplateDefinition) -> dict[str, Any]:
    """Fallback: fill template slots directly from brief content without LLM rewrite."""
    result: dict[str, Any] = {}

    if template.id == "cover_hero":
        result = {"title": brief.title, "subtitle": brief.subtitle or brief.key_message}

    elif template.id == "big_statement":
        result = {"statement": brief.key_message, "context": brief.subtitle}

    elif template.id in ("cards_3", "cards_4", "cards_6"):
        cards = []
        for block in brief.blocks[:template.max_blocks]:
            card: dict[str, str] = {"title": block.title, "body": block.body}
            if template.id in ("cards_4", "team_grid"):
                card["icon_query"] = block.title.split()[0] if block.title else "star"
            cards.append(card)
        result = {"header": brief.title, "cards": cards}

    elif template.id == "team_grid":
        cards = []
        for block in brief.blocks[:template.max_blocks]:
            cards.append({
                "icon_query": "user",
                "title": block.title,
                "body": block.body,
            })
        result = {"header": brief.title, "cards": cards}

    elif template.id == "bullet_dense":
        points = [{"title": b.title, "body": b.body} for b in brief.blocks[:template.max_blocks]]
        result = {"header": brief.title, "points": points}

    elif template.id in ("timeline_4", "process_grid"):
        steps = [{"title": b.title, "body": b.body} for b in brief.blocks[:template.max_blocks]]
        result = {"header": brief.title, "steps": steps}

    elif template.id == "comparison_2col":
        sides = [{"title": b.title, "body": b.body} for b in brief.blocks[:2]]
        result = {"header": brief.title, "sides": sides}

    elif template.id == "kpi_row":
        kpis = []
        for block in brief.blocks[:template.max_blocks]:
            value = block.metrics[0] if block.metrics else "—"
            kpis.append({"value": value, "label": block.title, "context": block.body})
        result = {"header": brief.title, "kpis": kpis}

    elif template.id == "quote_proof":
        if brief.blocks:
            result = {"quote_text": brief.blocks[0].body or brief.key_message, "attribution": brief.blocks[0].title}
        else:
            result = {"quote_text": brief.key_message, "attribution": None}

    elif template.id == "closing_takeaway":
        points = [{"text": b.title} for b in brief.blocks[:template.max_blocks]]
        result = {"header": "À retenir", "points": points}

    else:
        # Generic fallback
        result = {"header": brief.title, "cards": [{"title": b.title, "body": b.body} for b in brief.blocks[:3]]}

    return _enforce_char_limits(result, template)
