"""Slide validation with auto-fixes — 3-level validation + deterministic corrections.

The validator runs AFTER XML parsing and BEFORE normalize_slide().
It catches structural issues that the parser can't detect and fixes
what it can deterministically, leaving only real errors for LLM repair.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Valid values ──

VALID_LAYOUTS = {"left", "right", "vertical", "left-fit", "right-fit", "accent-top", "background"}

# Map XML component tag → SlideNode group type produced by the parser
COMPONENT_TO_GROUP_TYPE: dict[str, str] = {
    "BOXES": "box_group",
    "BULLETS": "bullet_group",
    "ICONS": "icon_list",
    "TIMELINE": "timeline_group",
    "STATS": "stats_group",
    "CYCLE": "cycle_group",
    "ARROWS": "arrow_list",
    "STAIRCASE": "staircase_group",
    "PYRAMID": "pyramid_group",
    "COMPARE": "compare_group",
    "BEFORE-AFTER": "before_after_group",
    "PROS-CONS": "pros_cons_group",
    "QUOTE": "quote",
    "CHART": "chart",
    "TABLE": "table",
    "IMAGE-GALLERY": "image_gallery_group",
    "COLUMNS": "columns",
}

# Reverse: group type → XML component name
GROUP_TYPE_TO_COMPONENT: dict[str, str] = {v: k for k, v in COMPONENT_TO_GROUP_TYPE.items()}

# Group types that contain countable items
COUNTABLE_GROUP_TYPES: dict[str, str] = {
    "box_group": "box_item",
    "bullet_group": "bullet_item",
    "icon_list": "icon_list_item",
    "timeline_group": "timeline_item",
    "stats_group": "stats_item",
    "cycle_group": "cycle_item",
    "arrow_list": "arrow_list_item",
    "staircase_group": "stair_item",
    "pyramid_group": "pyramid_item",
    "image_gallery_group": "image_gallery_item",
}

# Non-countable group types (fixed structure, not item-based)
FIXED_STRUCTURE_TYPES = {"compare_group", "before_after_group", "pros_cons_group", "quote", "chart", "table", "columns"}

MAX_TITLE_WORDS = 18
MAX_DESCRIPTION_WORDS = 120


@dataclass
class ValidationResult:
    """Result of slide validation with auto-fixes."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    auto_fixed: list[str] = field(default_factory=list)
    slide_data: dict = field(default_factory=dict)


def _count_words(text: str) -> int:
    return len(text.split())


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "\u2026"


def _find_main_group(content_json: list[dict]) -> tuple[dict | None, str | None]:
    """Find the main component group node in content_json.

    Returns (group_node, component_name) or (None, None).
    """
    for node in content_json:
        node_type = node.get("type", "")
        if node_type in GROUP_TYPE_TO_COMPONENT:
            return node, GROUP_TYPE_TO_COMPONENT[node_type]
    return None, None


def _count_items_in_group(group_node: dict) -> int:
    """Count child items in a group node."""
    group_type = group_node.get("type", "")
    if group_type in FIXED_STRUCTURE_TYPES:
        return 0  # Not countable
    children = group_node.get("children", [])
    item_type = COUNTABLE_GROUP_TYPES.get(group_type)
    if not item_type:
        return len(children)
    return sum(1 for c in children if c.get("type") == item_type)


def _truncate_text_in_nodes(nodes: list[dict], max_words: int, fixes: list[str]) -> list[dict]:
    """Recursively truncate text that exceeds word limits."""
    for node in nodes:
        node_type = node.get("type", "")
        # Truncate heading text
        if node_type in ("h1", "h2"):
            children = node.get("children", [])
            for child in children:
                if isinstance(child, dict) and "text" in child:
                    text = child["text"]
                    if _count_words(text) > MAX_TITLE_WORDS:
                        child["text"] = _truncate_words(text, MAX_TITLE_WORDS)
                        fixes.append(f"Truncated {node_type} title from {_count_words(text)} to {MAX_TITLE_WORDS} words")
        # Truncate paragraph text in items
        elif node_type == "p":
            children = node.get("children", [])
            for child in children:
                if isinstance(child, dict) and "text" in child:
                    text = child["text"]
                    if _count_words(text) > max_words:
                        child["text"] = _truncate_words(text, max_words)
                        fixes.append(f"Truncated paragraph from {_count_words(text)} to {max_words} words")
        # Recurse into children
        if "children" in node and isinstance(node["children"], list):
            _truncate_text_in_nodes(node["children"], max_words, fixes)
    return nodes


def auto_fix_slide(slide_data: dict, plan: Any) -> tuple[dict, list[str]]:
    """Apply deterministic auto-fixes to a slide. Returns (fixed_data, list_of_fixes)."""
    fixes: list[str] = []
    content = slide_data.get("content_json", [])

    if not isinstance(content, list):
        return slide_data, fixes

    # ── Layout mismatch fix ──
    current_layout = slide_data.get("layout_type", "vertical")
    if current_layout != plan.layout:
        if current_layout in VALID_LAYOUTS:
            fixes.append(f"Layout auto-fixed: {current_layout} → {plan.layout}")
        else:
            fixes.append(f"Invalid layout '{current_layout}' replaced with plan layout '{plan.layout}'")
        slide_data["layout_type"] = plan.layout

    # ── Item count fixes ──
    group_node, component_name = _find_main_group(content)
    if group_node and group_node.get("type") in COUNTABLE_GROUP_TYPES:
        item_type = COUNTABLE_GROUP_TYPES[group_node["type"]]
        children = group_node.get("children", [])
        items = [c for c in children if c.get("type") == item_type]
        non_items = [c for c in children if c.get("type") != item_type]

        # Too many items → truncate
        if len(items) > plan.max_items and plan.max_items > 0:
            truncated = items[:plan.max_items]
            group_node["children"] = non_items + truncated
            fixes.append(f"Truncated items: {len(items)} → {plan.max_items}")

    # ── Image query fixes ──
    root_image = slide_data.get("root_image")
    if plan.needs_image and not root_image:
        slide_data["root_image"] = {
            "query": f"{plan.title} professional business context high quality photo",
        }
        fixes.append(f"Auto-generated image query from slide title")
    elif root_image and isinstance(root_image, dict):
        query = root_image.get("query", "")
        if query and _count_words(query) < 5:
            root_image["query"] = f"{query} professional business context"
            fixes.append(f"Enriched short image query: '{query}' → '{root_image['query']}'")

    # ── Stats without value ──
    for node in content:
        if node.get("type") == "stats_group":
            for child in node.get("children", []):
                if child.get("type") == "stats_item" and not child.get("value"):
                    child["value"] = "—"
                    fixes.append("Added placeholder value to stats_item without value")

    # ── Text truncation ──
    _truncate_text_in_nodes(content, MAX_DESCRIPTION_WORDS, fixes)

    slide_data["content_json"] = content
    return slide_data, fixes


def validate_slide(slide_data: dict, plan: Any) -> ValidationResult:
    """Validate a slide against its plan. Run auto_fix_slide() first.

    Returns ValidationResult with errors (trigger repair), warnings (logged),
    and auto_fixed (deterministic corrections already applied).
    """
    # Apply auto-fixes first
    slide_data, auto_fixed = auto_fix_slide(slide_data, plan)

    errors: list[str] = []
    warnings: list[str] = []
    content = slide_data.get("content_json", [])

    # ── Level 1: Syntactic ──
    if not isinstance(content, list) or len(content) == 0:
        errors.append("content_json is empty or not a list")
        return ValidationResult(
            valid=False, errors=errors, warnings=warnings,
            auto_fixed=auto_fixed, slide_data=slide_data,
        )

    layout = slide_data.get("layout_type", "vertical")
    if layout not in VALID_LAYOUTS:
        errors.append(f"Invalid layout_type: '{layout}' (valid: {', '.join(sorted(VALID_LAYOUTS))})")

    for i, node in enumerate(content):
        if not isinstance(node, dict) or "type" not in node:
            errors.append(f"Node at index {i} has no 'type' field")

    # ── Level 2: Structural (against plan) ──
    group_node, component_name = _find_main_group(content)

    # Check component is in allowed list (skip for cover/closing which may have no group)
    if plan.allowed_components and component_name:
        if component_name not in plan.allowed_components:
            errors.append(
                f"Component '{component_name}' not in allowed list: {plan.allowed_components}"
            )

    # Check item count in bounds
    if group_node and group_node.get("type") in COUNTABLE_GROUP_TYPES:
        item_count = _count_items_in_group(group_node)
        if plan.min_items > 0 and item_count < plan.min_items:
            warnings.append(f"Item count ({item_count}) below minimum ({plan.min_items})")
        if plan.max_items > 0 and item_count > plan.max_items:
            warnings.append(f"Item count ({item_count}) above maximum ({plan.max_items})")

    # Check image presence when required
    if plan.needs_image:
        root_image = slide_data.get("root_image")
        if not root_image or not root_image.get("query"):
            warnings.append("Plan requires image but root_image is missing or has no query")

    # ── Level 3: UX quality ──
    has_visible_content = False
    for node in content:
        node_type = node.get("type", "")
        if node_type not in ("h1", "h2", "h3", "p"):
            has_visible_content = True
            break
        # Headings and paragraphs count as visible
        children = node.get("children", [])
        for child in children:
            if isinstance(child, dict) and child.get("text", "").strip():
                has_visible_content = True
                break

    if not has_visible_content:
        errors.append("Slide appears empty — no visible content beyond headings")

    valid = len(errors) == 0

    if auto_fixed:
        logger.info("Slide %d auto-fixes: %s", plan.slide_number, "; ".join(auto_fixed))
    if warnings:
        logger.info("Slide %d warnings: %s", plan.slide_number, "; ".join(warnings))
    if errors:
        logger.warning("Slide %d errors: %s", plan.slide_number, "; ".join(errors))

    return ValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        auto_fixed=auto_fixed,
        slide_data=slide_data,
    )
