"""Per-slide XML generator — Step 3 of the V2 pipeline.

Generates one slide at a time with constrained prompts, validates,
repairs if needed, and falls back to deterministic templates.

This function NEVER raises — it always returns a valid slide_data dict.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from app.services.presentation_design_normalizer import normalize_slide
from app.services.presentation_fit_evaluator import adjust_sizing_for_fit
from app.services.presentation_slide_planner import SlidePlan, DeckPlan
from app.services.presentation_slide_validator import validate_slide
from app.services.presentation_xml_parser import XMLSlideParser

logger = logging.getLogger(__name__)

# Type aliases
LLMCallXmlFn = Callable[[str, str], Awaitable[str]]


# ══════════════════════════════════════════════
#  Fallback slide builder (deterministic, no LLM)
# ══════════════════════════════════════════════


def _build_fallback_slide(plan: SlidePlan) -> dict[str, Any]:
    """Build a deterministic fallback slide from the plan.

    Used when LLM generation + repair both fail.
    Produces a safe accent-top + H2 + BULLETS layout.
    """
    content_json: list[dict[str, Any]] = [
        {
            "type": "h2",
            "children": [{"text": plan.title}],
        },
    ]

    # Build bullet items from key_points
    items: list[dict[str, Any]] = []
    points = plan.key_points[:5] if plan.key_points else [plan.goal or plan.title]
    for kp in points:
        if not kp or not kp.strip():
            continue
        items.append({
            "type": "bullet_item",
            "children": [
                {"type": "h3", "children": [{"text": kp[:80]}]},
            ],
        })

    if items:
        content_json.append({
            "type": "bullet_group",
            "variant": "arrow",
            "children": items,
        })

    # Build root_image if plan requires it
    root_image = None
    if plan.needs_image:
        root_image = {
            "query": f"{plan.title} professional business context high quality photo",
        }

    layout = plan.layout if plan.layout != "background" else "accent-top"

    return {
        "layout_type": layout,
        "content_json": content_json,
        "root_image": root_image,
        "bg_color": None,
        "sizing": {
            "font_scale": plan.font_scale,
            "block_spacing": "normal",
            "card_width": "M",
        },
    }


# ══════════════════════════════════════════════
#  Template resolution for fit evaluation
# ══════════════════════════════════════════════


def _resolve_template_for_plan(plan: SlidePlan):
    """Resolve a TemplateDefinition for a SlidePlan (best-effort).

    Returns TemplateDefinition or None. Used by adjust_sizing_for_fit().
    """
    try:
        from app.services.presentation_briefs import NarrativeRole
        from app.services.presentation_template_registry import TEMPLATE_REGISTRY

        role = NarrativeRole(plan.role)
    except (ValueError, ImportError):
        return None

    candidates = [
        t for t in TEMPLATE_REGISTRY.values()
        if role in t.allowed_roles
    ]
    if not candidates:
        return None

    # Match preferred component to template node_structure
    _COMP_TO_STRUCTURE: dict[str, str] = {
        "BOXES": "box_group",
        "STATS": "stats_group",
        "TIMELINE": "timeline_group",
        "BULLETS": "bullet_group",
        "COMPARE": "compare_group",
        "STAIRCASE": "staircase_group",
        "QUOTE": "quote",
    }
    if plan.preferred_component:
        target = _COMP_TO_STRUCTURE.get(plan.preferred_component)
        if target:
            for t in candidates:
                if t.node_structure == target:
                    return t

    return candidates[0]


# ══════════════════════════════════════════════
#  Prompt builders
# ══════════════════════════════════════════════


def _build_previous_slides_summary(previously_generated: list[dict]) -> str:
    """Build a compact one-line-per-slide summary for context."""
    if not previously_generated:
        return "Aucun slide précédent."

    lines: list[str] = []
    for i, slide in enumerate(previously_generated):
        layout = slide.get("layout_type", "?")
        content = slide.get("content_json", [])
        # Find the main component
        component = "?"
        variant = ""
        for node in content:
            node_type = node.get("type", "")
            if node_type.endswith("_group") or node_type in ("quote", "chart", "table"):
                from app.services.presentation_slide_validator import GROUP_TYPE_TO_COMPONENT
                component = GROUP_TYPE_TO_COMPONENT.get(node_type, node_type)
                if node.get("variant"):
                    variant = f" {node['variant']}"
                break
        # Find the title
        title = ""
        for node in content:
            if node.get("type") in ("h1", "h2"):
                children = node.get("children", [])
                for child in children:
                    if isinstance(child, dict) and child.get("text"):
                        title = child["text"][:50]
                        break
                if title:
                    break
        lines.append(f'{i + 1}. "{title}" — layout: {layout}, composant: {component}{variant}')

    return "\n".join(lines)


def _build_slide_constraints(plan: SlidePlan) -> str:
    """Build the constraints block for the slide prompt."""
    parts: list[str] = [
        f"- Le layout DOIT être \"{plan.layout}\"",
    ]

    if plan.allowed_components:
        parts.append(f"- Composant principal PARMI : {', '.join(plan.allowed_components)}")
        if plan.preferred_component:
            parts.append(f"- Composant PRÉFÉRÉ (utiliser en priorité) : {plan.preferred_component}")
            _COMP_HINTS: dict[str, str] = {
                "STATS": "Valeurs percutantes (+XX%, XM€, xN). Chaque item : valeur + légende courte (10 mots max). Variant 'bar' ou 'circle'.",
                "BOXES": "CHAQUE item DOIT avoir un <ICON query=\"...\">. Descriptions courtes (2 phrases max, ~25 mots). Variant 'sideline' ou 'icons'.",
                "TIMELINE": "Variant 'pills'. Chaque étape : H3 daté/numéroté + P de 1-2 phrases (~20 mots). MAX 4 étapes.",
                "COMPARE": "Exactement 2 DIV. Chaque côté avec titre + 3-4 arguments chiffrés.",
                "BULLETS": "Variant 'numbered' ou 'arrow'. Points de synthèse percutants (~20 mots chacun).",
                "QUOTE": "Variant 'large'. Citation impactante avec attribution.",
                "CHART": "4-6 data points réalistes. Pas d'étiquettes abstraites.",
                "ICONS": "CHAQUE item DOIT avoir <ICON query=\"...\"> + H3 court (5 mots max) + P concis (~20 mots).",
                "STAIRCASE": "Progression claire par paliers numérotés. MAX 4 paliers, ~20 mots par description.",
            }
            hint = _COMP_HINTS.get(plan.preferred_component)
            if hint:
                parts.append(f"  GUIDE : {hint}")

    if plan.allowed_variants:
        for comp, variants in plan.allowed_variants.items():
            parts.append(f"- Variants autorisés pour {comp} : {', '.join(variants)}")

    if plan.min_items > 0 or plan.max_items > 0:
        parts.append(f"- Nombre d'items : entre {plan.min_items} et {plan.max_items}")

    if plan.needs_image:
        parts.append("- Image OBLIGATOIRE : inclure un tag <IMG query=\"description 10+ mots\" />")
    else:
        parts.append("- Image optionnelle")

    parts.append(f"- Densité : {plan.density} (font_scale: {plan.font_scale})")

    return "\n".join(parts)


def _build_system_prompt(
    plan: SlidePlan,
    deck_plan: DeckPlan,
    previously_generated: list[dict],
    original_prompt: str,
    rag_context: str,
    language: str,
    style: str,
    theme_extra_sections: str,
) -> str:
    """Build the constrained system prompt for single-slide generation."""
    from app.services.presentation_prompts import CONSTRAINED_SLIDE_SYSTEM_PROMPT

    constraints = _build_slide_constraints(plan)
    prev_summary = _build_previous_slides_summary(previously_generated)
    deck_context = (
        f"Titre : {deck_plan.presentation_title}\n"
        f"Audience : {deck_plan.audience}\n"
        f"Style : {deck_plan.tone}\n"
        f"Sujet : {original_prompt[:8000]}"
    )

    image_rule = (
        "IMG OBLIGATOIRE avec query de 10+ mots"
        if plan.needs_image
        else "IMG optionnelle"
    )

    prompt = CONSTRAINED_SLIDE_SYSTEM_PROMPT.replace(
        "{{LANGUAGE}}", language,
    ).replace(
        "{{TONE}}", style,
    ).replace(
        "{{REQUIRED_LAYOUT}}", plan.layout,
    ).replace(
        "{{ALLOWED_COMPONENTS}}", ", ".join(plan.allowed_components) if plan.allowed_components else "(cover: H1 + P + IMG)",
    ).replace(
        "{{MIN_ITEMS}}", str(plan.min_items),
    ).replace(
        "{{MAX_ITEMS}}", str(plan.max_items),
    ).replace(
        "{{IMAGE_RULE}}", image_rule,
    ).replace(
        "{{SLIDE_CONSTRAINTS}}", constraints,
    ).replace(
        "{{DECK_CONTEXT}}", deck_context,
    ).replace(
        "{{PREVIOUS_SLIDES_SUMMARY}}", prev_summary,
    ).replace(
        "{{EXTRA_SECTIONS}}", theme_extra_sections,
    )

    return prompt


def _build_user_prompt(
    plan: SlidePlan,
    deck_plan: DeckPlan,
    rag_context: str,
    instruction: str | None = None,
) -> str:
    """Build the user prompt for single-slide generation."""
    total = len(deck_plan.slides)
    parts: list[str] = [
        f"Slide {plan.slide_number}/{total} — Rôle : {plan.role}",
        f"Titre : {plan.title}",
    ]

    if plan.goal:
        parts.append(f"Objectif : {plan.goal}")

    if plan.key_points:
        kps = "\n".join(f"  - {kp}" for kp in plan.key_points)
        parts.append(f"Points clés :\n{kps}")

    if rag_context and rag_context != "Aucun contexte additionnel.":
        parts.append(f"\nContexte RAG :\n{rag_context[:4000]}")

    if instruction:
        parts.append(f"\nINSTRUCTION UTILISATEUR : {instruction.strip()}")

    parts.append(f"\nGénère UN SEUL tag <SECTION layout=\"{plan.layout}\">...</SECTION>")

    return "\n".join(parts)


def _build_repair_prompt(
    xml_content: str,
    errors: list[str],
    plan: SlidePlan,
) -> str:
    """Build a repair prompt for a failed slide."""
    from app.services.presentation_prompts import SLIDE_REPAIR_XML_PROMPT

    return SLIDE_REPAIR_XML_PROMPT.format(
        xml_content=xml_content[:2000],
        errors="\n".join(f"- {e}" for e in errors),
        required_layout=plan.layout,
        allowed_components=", ".join(plan.allowed_components) if plan.allowed_components else "H1, P, IMG",
        min_items=plan.min_items,
        max_items=plan.max_items,
    )


# ══════════════════════════════════════════════
#  Main generation function
# ══════════════════════════════════════════════


async def generate_slide_xml(
    *,
    slide_plan: SlidePlan,
    deck_plan: DeckPlan,
    previously_generated: list[dict],
    original_prompt: str,
    rag_context: str,
    language: str,
    style: str,
    theme_extra_sections: str,
    llm_call_xml: LLMCallXmlFn,
    llm_call_json: LLMCallXmlFn | None = None,
    instruction: str | None = None,
) -> dict[str, Any]:
    """Generate a single slide XML, validate, repair, or fallback.

    This function NEVER raises. It always returns a valid slide_data dict.
    """
    parser = XMLSlideParser()

    # ── Step 1: Build prompts ──
    system_prompt = _build_system_prompt(
        plan=slide_plan,
        deck_plan=deck_plan,
        previously_generated=previously_generated,
        original_prompt=original_prompt,
        rag_context=rag_context,
        language=language,
        style=style,
        theme_extra_sections=theme_extra_sections,
    )
    user_prompt = _build_user_prompt(
        plan=slide_plan,
        deck_plan=deck_plan,
        rag_context=rag_context,
        instruction=instruction,
    )

    xml_response = ""
    try:
        # ── Step 2: LLM call ──
        xml_response = await llm_call_xml(system_prompt, user_prompt)

        # ── Step 3: Parse XML ──
        slide_data = parser.parse_single_section(xml_response)

        # ── Step 4: Validate ──
        result = validate_slide(slide_data, slide_plan)
        slide_data = result.slide_data

        if result.valid:
            # ── Step 5: Normalize + fit check and return ──
            slide_data = normalize_slide(slide_data)
            template_def = _resolve_template_for_plan(slide_plan)
            slide_data = adjust_sizing_for_fit(slide_data, template_def)
            logger.info(
                "Slide %d generated OK (auto_fixes=%d, warnings=%d)",
                slide_plan.slide_number, len(result.auto_fixed), len(result.warnings),
            )
            return slide_data

        # ── Step 6: Repair ──
        logger.warning(
            "Slide %d validation failed (%d errors), attempting repair",
            slide_plan.slide_number, len(result.errors),
        )

        repair_fn = llm_call_json or llm_call_xml
        repair_system = "Tu corriges du XML de slide de présentation. Renvoie UNIQUEMENT le tag <SECTION> corrigé."
        repair_user = _build_repair_prompt(xml_response, result.errors, slide_plan)

        repaired_xml = await repair_fn(repair_system, repair_user)
        repaired_data = parser.parse_single_section(repaired_xml)
        repaired_result = validate_slide(repaired_data, slide_plan)
        repaired_data = repaired_result.slide_data

        if repaired_result.valid:
            repaired_data = normalize_slide(repaired_data)
            template_def = _resolve_template_for_plan(slide_plan)
            repaired_data = adjust_sizing_for_fit(repaired_data, template_def)
            logger.info(
                "Slide %d repaired OK (auto_fixes=%d)",
                slide_plan.slide_number, len(repaired_result.auto_fixed),
            )
            return repaired_data

        logger.warning(
            "Slide %d repair also failed (%d errors), using fallback",
            slide_plan.slide_number, len(repaired_result.errors),
        )

    except Exception as e:
        logger.error(
            "Slide %d generation exception: %s, using fallback",
            slide_plan.slide_number, e,
        )

    # ── Step 7: Deterministic fallback ──
    fallback = _build_fallback_slide(slide_plan)
    fallback = normalize_slide(fallback)
    fallback = adjust_sizing_for_fit(fallback, None)
    logger.info("Slide %d using deterministic fallback", slide_plan.slide_number)
    return fallback
