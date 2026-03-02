"""Deterministic template selection based on brief scoring.

The LLM generates a SlideBrief, this module picks the best template
using rules and scoring — no LLM involved.
"""

from __future__ import annotations

import logging

from app.services.presentation_briefs import DeckContext, NarrativeRole, SlideBrief
from app.services.presentation_template_registry import (
    TEMPLATE_REGISTRY,
    TemplateDefinition,
    get_templates_for_role,
)

logger = logging.getLogger(__name__)

# Template Fit Failure threshold — template must hold ≥35% of content
_MIN_CAPACITY_RATIO = 0.35


def select_template(
    brief: SlideBrief,
    deck_context: DeckContext,
) -> TemplateDefinition:
    """Select the best template for a brief using deterministic scoring.

    Scoring dimensions (total 110):
    - Role match: 30 pts
    - Block count fit: 20 pts
    - Density match: 15 pts
    - Diversity (no consecutive duplicates): 20 pts
    - Asset/visual match: 15 pts
    - Content capacity: 10 pts
    """
    block_count = len(brief.blocks)

    # Get candidates matching the narrative role
    candidates = get_templates_for_role(brief.narrative_role)

    if not candidates:
        # Fallback: try broader roles
        candidates = _fallback_candidates(brief)

    if not candidates:
        # Ultimate fallback: cards_3
        logger.warning("No template candidates for role=%s, falling back to cards_3", brief.narrative_role)
        return TEMPLATE_REGISTRY["cards_3"]

    # Filter by block count compatibility
    compatible = [
        t for t in candidates
        if t.min_blocks <= block_count <= t.max_blocks
    ]

    # If no exact match, keep all candidates (scoring will penalize mismatch)
    if not compatible:
        compatible = candidates

    # Score each candidate
    scored: list[tuple[TemplateDefinition, float]] = []
    for template in compatible:
        score = 0.0
        score += _role_match_score(brief, template)
        score += _block_count_score(brief, template)
        score += _density_match_score(brief, template)
        score += _diversity_score(template, deck_context)
        score += _asset_match_score(brief, template)
        score += _content_capacity_score(brief, template)
        scored.append((template, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    best = scored[0][0]
    logger.info(
        "Template selected: %s (score=%.1f) for role=%s blocks=%d",
        best.id, scored[0][1], brief.narrative_role.value, block_count,
    )

    # Template Fit Failure check — ensure chosen template can hold enough content
    total_content = sum(len(b.body) for b in brief.blocks)
    if total_content > 0:
        body_slots = [s for s in best.slots if s.max_body_chars > 0]
        total_capacity = sum(s.max_body_chars for s in body_slots[:len(brief.blocks)])
        ratio = total_capacity / total_content if total_content else 1.0

        if ratio < _MIN_CAPACITY_RATIO:
            logger.warning(
                "Template fit failure: %s capacity=%d / content=%d = %.0f%% < %d%%. "
                "Searching for higher-capacity alternative.",
                best.id, total_capacity, total_content,
                ratio * 100, int(_MIN_CAPACITY_RATIO * 100),
            )
            for tmpl, _sc in scored[1:]:
                alt_slots = [s for s in tmpl.slots if s.max_body_chars > 0]
                alt_capacity = sum(s.max_body_chars for s in alt_slots[:len(brief.blocks)])
                alt_ratio = alt_capacity / total_content
                if alt_ratio >= _MIN_CAPACITY_RATIO:
                    logger.info(
                        "Fit failure override: %s → %s (ratio %.0f%%)",
                        best.id, tmpl.id, alt_ratio * 100,
                    )
                    best = tmpl
                    break

    return best


def _role_match_score(brief: SlideBrief, template: TemplateDefinition) -> float:
    """Score based on how well the template matches the narrative role. Max 30."""
    if brief.narrative_role in template.allowed_roles:
        # Bonus if it's the first allowed role (primary match)
        if template.allowed_roles[0] == brief.narrative_role:
            return 30.0
        return 25.0
    return 0.0


def _block_count_score(brief: SlideBrief, template: TemplateDefinition) -> float:
    """Score based on how well block count fits template slots. Max 20."""
    block_count = len(brief.blocks)

    if template.min_blocks <= block_count <= template.max_blocks:
        # Perfect fit
        return 20.0
    elif block_count < template.min_blocks:
        # Too few blocks — mild penalty
        gap = template.min_blocks - block_count
        return max(0.0, 15.0 - gap * 5.0)
    else:
        # Too many blocks — stronger penalty
        gap = block_count - template.max_blocks
        return max(0.0, 10.0 - gap * 5.0)


def _density_match_score(brief: SlideBrief, template: TemplateDefinition) -> float:
    """Score based on density alignment. Max 15."""
    if brief.density_target == template.density:
        return 15.0

    # Adjacent density levels
    _DENSITY_ORDER = {"low": 0, "medium": 1, "high": 2}
    brief_level = _DENSITY_ORDER.get(brief.density_target, 1)
    template_level = _DENSITY_ORDER.get(template.density, 1)

    distance = abs(brief_level - template_level)
    if distance == 1:
        return 8.0
    return 0.0


def _diversity_score(template: TemplateDefinition, deck_context: DeckContext) -> float:
    """Score based on template diversity in the deck. Max 20."""
    used = deck_context.used_templates

    if not used:
        return 20.0

    # Penalize consecutive duplicate
    if used[-1] == template.id:
        return 0.0

    # Penalize recent use (last 3 slides)
    recent = used[-3:]
    if template.id in recent:
        return 5.0

    # Penalize same layout as previous
    if deck_context.used_layouts and deck_context.used_layouts[-1] == template.layout_type:
        return 12.0

    return 20.0


def _asset_match_score(brief: SlideBrief, template: TemplateDefinition) -> float:
    """Score based on asset/visual alignment. Max 15."""
    score = 0.0

    # Visual preference match
    _VISUAL_TO_STRUCTURE = {
        "timeline": "timeline_group",
        "cards": "box_group",
        "stats": "stats_group",
        "comparison": "compare_group",
        "quote": "quote",
    }

    if brief.preferred_visual:
        expected_structure = _VISUAL_TO_STRUCTURE.get(brief.preferred_visual, "")
        if template.node_structure == expected_structure:
            score += 10.0
        elif expected_structure and template.node_structure:
            score += 3.0  # At least there's a structure

    # Asset need match
    if brief.asset_need == "photo" and template.needs_root_image:
        score += 5.0
    elif brief.asset_need == "none" and not template.needs_root_image:
        score += 5.0
    elif brief.asset_need in ("icon", "chart"):
        score += 3.0  # Most templates can handle these

    return min(score, 15.0)


def _content_capacity_score(brief: SlideBrief, template: TemplateDefinition) -> float:
    """Bonus for templates that can hold the content volume. Max 10."""
    if not brief.blocks:
        return 0.0
    avg_body = sum(len(b.body) for b in brief.blocks) / len(brief.blocks)
    if avg_body < 150:
        return 0.0  # Content is not dense — no need to favor capacity

    body_slots = [s for s in template.slots if s.max_body_chars > 0]
    if not body_slots:
        return 0.0
    avg_capacity = sum(s.max_body_chars for s in body_slots) / len(body_slots)

    if avg_capacity >= 250:
        return 10.0
    elif avg_capacity >= 180:
        return 5.0
    return 0.0


def _fallback_candidates(brief: SlideBrief) -> list[TemplateDefinition]:
    """Get fallback candidates when no templates match the exact role."""
    # Map to broader categories
    _ROLE_FALLBACKS: dict[NarrativeRole, list[str]] = {
        NarrativeRole.HOOK: ["big_statement", "kpi_row"],
        NarrativeRole.CONTEXT: ["cards_3", "cards_4", "cards_6", "bullet_dense"],
        NarrativeRole.PROBLEM: ["cards_3", "comparison_2col", "bullet_dense"],
        NarrativeRole.INSIGHT: ["cards_3", "kpi_row", "cards_6"],
        NarrativeRole.PROOF: ["kpi_row", "quote_proof", "cards_6"],
        NarrativeRole.PROCESS: ["timeline_4", "process_grid", "cards_6"],
        NarrativeRole.PLAN: ["timeline_4", "cards_4", "cards_6"],
        NarrativeRole.COMPARISON: ["comparison_2col"],
        NarrativeRole.TEAM: ["team_grid", "cards_4", "cards_6"],
        NarrativeRole.TAKEAWAY: ["closing_takeaway"],
        NarrativeRole.CLOSING: ["closing_takeaway", "big_statement"],
        NarrativeRole.COVER: ["cover_hero"],
    }
    fallback_ids = _ROLE_FALLBACKS.get(brief.narrative_role, ["cards_3"])
    return [TEMPLATE_REGISTRY[tid] for tid in fallback_ids if tid in TEMPLATE_REGISTRY]
