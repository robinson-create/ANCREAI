"""Visual quality scoring — heuristic evaluation of composed slides.

Checks surface occupation, text density, balance, and hierarchy.
No LLM involved — pure algorithmic evaluation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.services.presentation_template_registry import TemplateDefinition

logger = logging.getLogger(__name__)

# Approximate char-to-surface ratios (based on 960x540 slide)
_AVG_CHAR_WIDTH_PX = 8  # ~14px font, Inter (default for "M")
_AVG_LINE_HEIGHT_PX = 22
_SLIDE_CONTENT_AREA = 880 * 480  # Usable area (with margins)

# Font-scale-aware surface factors
_FONT_SCALE_FACTORS: dict[str, dict[str, float]] = {
    "S": {"char_width": 6.5, "line_height": 18},   # Compact fonts for dense slides
    "M": {"char_width": 8.0, "line_height": 22},    # Standard (current default)
    "L": {"char_width": 10.0, "line_height": 28},   # Airy / hero slides
}


@dataclass
class FitReport:
    """Quality report for a composed slide."""

    surface_ratio: float  # 0.0-1.0 estimated content occupation
    text_density_ok: bool
    overflow_detected: bool
    underfill_detected: bool
    balance_score: float  # 0.0-1.0 how balanced the blocks are
    hierarchy_score: float  # 0.0-1.0 clear title → content hierarchy
    score: int  # 0-100 overall quality
    recommendation: str  # "ok" | "rewrite" | "alternate_template" | "split"


def evaluate_fit(
    composed_slide: dict[str, Any],
    template: TemplateDefinition,
) -> FitReport:
    """Evaluate the visual quality of a composed slide.

    Scoring (total 100):
    - Surface occupation within template target: 30
    - Text within character limits: 25
    - Block balance (similar sizes): 20
    - Clear hierarchy (title + content): 15
    - Layout/role coherence: 10
    """
    content_json = composed_slide.get("content_json", [])
    sizing = composed_slide.get("sizing")

    # Calculate metrics (use sizing-aware surface estimation)
    surface_ratio = _estimate_surface_ratio(content_json, sizing=sizing)
    text_ok, overflow, underfill = _check_text_density(content_json, template)
    balance = _compute_balance(content_json)
    hierarchy = _compute_hierarchy(content_json)

    # Score
    score = 0

    # Surface occupation (30 pts)
    min_target, max_target = template.surface_target
    if min_target <= surface_ratio <= max_target:
        score += 30
    elif surface_ratio < min_target:
        # Proportional penalty for underfill
        ratio = surface_ratio / min_target if min_target > 0 else 0
        score += int(30 * ratio)
    else:
        # Over-target is less bad than under-target
        score += 20

    # Text density (25 pts)
    if text_ok:
        score += 25
    elif overflow:
        score += 10  # Overflow is worse
    else:
        score += 15  # Underfill is moderate

    # Balance (20 pts)
    score += int(20 * balance)

    # Hierarchy (15 pts)
    score += int(15 * hierarchy)

    # Layout coherence (10 pts)
    if composed_slide.get("layout_type") == template.layout_type:
        score += 10

    # Determine recommendation
    if score >= 75:
        recommendation = "ok"
    elif score >= 60:
        recommendation = "rewrite"
    elif overflow:
        recommendation = "split"
    else:
        recommendation = "alternate_template"

    report = FitReport(
        surface_ratio=surface_ratio,
        text_density_ok=text_ok,
        overflow_detected=overflow,
        underfill_detected=underfill,
        balance_score=balance,
        hierarchy_score=hierarchy,
        score=score,
        recommendation=recommendation,
    )

    logger.debug(
        "Fit evaluation: score=%d surface=%.2f balance=%.2f hierarchy=%.2f rec=%s",
        score, surface_ratio, balance, hierarchy, recommendation,
    )

    return report


def _estimate_surface_ratio(content_json: list[dict], sizing: dict | None = None) -> float:
    """Estimate what fraction of the slide area the content occupies."""
    total_chars = _count_chars_recursive(content_json)
    total_blocks = _count_blocks(content_json)

    # Use font_scale from sizing to adjust surface calculation
    font_scale = sizing.get("font_scale", "M") if sizing else "M"
    factors = _FONT_SCALE_FACTORS.get(font_scale, _FONT_SCALE_FACTORS["M"])
    char_width = factors["char_width"]
    line_height = factors["line_height"]

    # Rough estimation: each char takes char_width px, wraps at ~600px
    # Each block has ~24px padding + margins
    chars_area = total_chars * char_width * line_height
    block_overhead = total_blocks * 200 * 50  # Approximate box size

    estimated_area = chars_area + block_overhead

    # Title area (typically ~100px height)
    has_title = any(n.get("type") in ("h1", "h2") for n in content_json)
    if has_title:
        estimated_area += 1100 * 80  # Title bar

    ratio = estimated_area / _SLIDE_CONTENT_AREA
    return min(ratio, 1.5)  # Can exceed 1.0 for overflow detection


def _check_text_density(
    content_json: list[dict],
    template: TemplateDefinition,
) -> tuple[bool, bool, bool]:
    """Check if text fits the template constraints.

    Returns: (text_ok, overflow_detected, underfill_detected)
    """
    total_chars = _count_chars_recursive(content_json)
    block_count = _count_blocks(content_json)

    # Define density thresholds based on template
    max_chars = sum(s.max_title_chars + s.max_body_chars for s in template.slots)
    min_chars = max_chars * 0.25  # At least 25% filled

    overflow = total_chars > max_chars * 1.2
    underfill = total_chars < min_chars

    return (not overflow and not underfill, overflow, underfill)


def _compute_balance(content_json: list[dict]) -> float:
    """Compute how balanced the content blocks are (0.0-1.0).

    1.0 = all blocks have similar length, 0.0 = very uneven.
    """
    block_sizes: list[int] = []

    for node in content_json:
        ntype = node.get("type", "")
        # Look for group children
        if ntype.endswith("_group") or ntype == "quote":
            children = node.get("children", [])
            for child in children:
                size = _count_chars_recursive([child])
                if size > 0:
                    block_sizes.append(size)

    if len(block_sizes) <= 1:
        return 1.0  # Single block or no blocks = balanced by default

    avg = sum(block_sizes) / len(block_sizes)
    if avg == 0:
        return 1.0

    # Coefficient of variation (lower = more balanced)
    variance = sum((s - avg) ** 2 for s in block_sizes) / len(block_sizes)
    cv = (variance ** 0.5) / avg

    # Map CV to 0-1 score (CV of 0 = perfect, CV > 1 = terrible)
    return max(0.0, 1.0 - cv)


def _compute_hierarchy(content_json: list[dict]) -> float:
    """Compute hierarchy clarity (0.0-1.0).

    Good hierarchy: 1 title (h1/h2) + content blocks, no competing titles.
    """
    title_count = 0
    has_content_group = False

    for node in content_json:
        ntype = node.get("type", "")
        if ntype in ("h1", "h2"):
            title_count += 1
        if ntype.endswith("_group") or ntype == "quote" or ntype.startswith("chart-"):
            has_content_group = True

    # Perfect: 1 title + content
    if title_count == 1 and has_content_group:
        return 1.0
    # OK: 1 title only (cover, big statement)
    if title_count == 1:
        return 0.85
    # Weak: no title
    if title_count == 0:
        return 0.4
    # Bad: multiple titles
    return max(0.0, 0.7 - (title_count - 1) * 0.2)


def _count_chars_recursive(nodes: list[dict]) -> int:
    """Count total text characters in a node tree."""
    total = 0
    for node in nodes:
        if "text" in node and "type" not in node:
            total += len(node.get("text", ""))
        children = node.get("children", [])
        if isinstance(children, list):
            total += _count_chars_recursive(children)
    return total


def _count_blocks(content_json: list[dict]) -> int:
    """Count the number of content blocks (items in groups)."""
    count = 0
    for node in content_json:
        ntype = node.get("type", "")
        if ntype.endswith("_group") or ntype == "quote":
            children = node.get("children", [])
            count += len(children)
    return count


# ══════════════════════════════════════════════
#  Auto-sizing adjustment
# ══════════════════════════════════════════════

_FONT_DOWN: dict[str, str] = {"L": "M", "M": "S", "S": "S"}
_FONT_UP: dict[str, str] = {"S": "M", "M": "L", "L": "L"}
_SPACING_TIGHTER: dict[str, str] = {"loose": "normal", "normal": "tight", "tight": "tight"}
_SPACING_LOOSER: dict[str, str] = {"tight": "normal", "normal": "loose", "loose": "loose"}


def adjust_sizing_for_fit(
    slide_data: dict[str, Any],
    template: TemplateDefinition | None = None,
) -> dict[str, Any]:
    """Evaluate fit and adjust sizing if overflow or underfill.

    Strategy:
    - If overflow_detected → reduce font_scale (M→S, L→M), tighten block_spacing
    - If underfill_detected → increase font_scale (S→M, M→L), loosen block_spacing
    - If already at extremes, leave as-is

    This function is safe to call on any slide_data dict. Never raises.
    """
    try:
        if template is None:
            return _adjust_by_surface_heuristic(slide_data)

        report = evaluate_fit(slide_data, template)

        if report.recommendation == "ok":
            return slide_data

        sizing = dict(slide_data.get("sizing") or {})
        current_font = sizing.get("font_scale", "M")
        current_spacing = sizing.get("block_spacing", "normal")

        if report.overflow_detected:
            new_font = _FONT_DOWN.get(current_font, "S")
            new_spacing = _SPACING_TIGHTER.get(current_spacing, "tight")
            sizing["font_scale"] = new_font
            sizing["block_spacing"] = new_spacing
            logger.info(
                "Fit adjustment: overflow → font %s→%s, spacing %s→%s (surface=%.2f)",
                current_font, new_font, current_spacing, new_spacing, report.surface_ratio,
            )
        elif report.underfill_detected:
            new_font = _FONT_UP.get(current_font, "L")
            new_spacing = _SPACING_LOOSER.get(current_spacing, "loose")
            sizing["font_scale"] = new_font
            sizing["block_spacing"] = new_spacing
            logger.info(
                "Fit adjustment: underfill → font %s→%s, spacing %s→%s (surface=%.2f)",
                current_font, new_font, current_spacing, new_spacing, report.surface_ratio,
            )

        slide_data["sizing"] = sizing
        return slide_data

    except Exception as e:
        logger.warning("adjust_sizing_for_fit failed: %s", e)
        return slide_data


def _adjust_by_surface_heuristic(slide_data: dict[str, Any]) -> dict[str, Any]:
    """Fallback: use surface ratio alone (no template)."""
    content_json = slide_data.get("content_json", [])
    sizing = dict(slide_data.get("sizing") or {})

    ratio = _estimate_surface_ratio(content_json, sizing=sizing)
    current_font = sizing.get("font_scale", "M")
    current_spacing = sizing.get("block_spacing", "normal")

    if ratio > 1.05:  # Overflow
        sizing["font_scale"] = _FONT_DOWN.get(current_font, "S")
        sizing["block_spacing"] = _SPACING_TIGHTER.get(current_spacing, "tight")
    elif ratio < 0.30:  # Significant underfill
        sizing["font_scale"] = _FONT_UP.get(current_font, "L")
        sizing["block_spacing"] = _SPACING_LOOSER.get(current_spacing, "loose")

    slide_data["sizing"] = sizing
    return slide_data
