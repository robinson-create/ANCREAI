"""Post-LLM design normalization pipeline.

The LLM proposes, the normalizer civilizes.

Pipeline: generation → schema validation → **design normalization** → repair → result
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.presentation_icons import is_valid_icon, resolve_icon
from app.services.presentation_templates import SlideTemplate, get_template

logger = logging.getLogger(__name__)

# ── Normalization limits ──

MAX_TITLE_WORDS = 10
MAX_DESCRIPTION_WORDS = 25
MAX_CARD_DESCRIPTION_WORDS = 15
MAX_ITEMS_IN_GROUP = 4
MAX_ICONS_PER_SLIDE = 5
MAX_TOP_LEVEL_BLOCKS = 4  # title + 2-3 content blocks
MAX_HEADING_LEVELS = 2  # Only h1/h2 + h3 — no h4/h5/h6 in presentation slides


# ── Main entry point ──


def normalize_slide(
    slide_data: dict,
    template: SlideTemplate | None = None,
    theme: dict | None = None,
) -> dict:
    """Apply all normalization passes to a slide.

    Mutates and returns slide_data.
    """
    content = slide_data.get("content_json", [])
    if not isinstance(content, list):
        return slide_data

    content = normalize_icons(content)
    content = normalize_density(content)
    content = normalize_heading_levels(content)
    content = enforce_text_limits(content)

    if template:
        content = enforce_template_constraints(content, template)

    if theme:
        content = normalize_card_variants(content, theme)

    slide_data["content_json"] = content
    return slide_data


# ── Icon normalization ──


def normalize_icons(nodes: list[dict]) -> list[dict]:
    """Resolve icon queries to Lucide names. Remove unresolvable icons.

    For each node with type "icon":
    - If icon_name is already set and valid → keep
    - If query is set → resolve to icon_name
    - If unresolvable → remove the icon node (don't break the parent)
    """
    icon_count = 0

    def _process(node: dict) -> dict | None:
        nonlocal icon_count

        if node.get("type") == "icon":
            # Already resolved and valid
            existing_name = node.get("icon_name")
            if existing_name and is_valid_icon(existing_name):
                icon_count += 1
                if icon_count > MAX_ICONS_PER_SLIDE:
                    return None  # Drop excess icons
                return node

            # Try to resolve from query
            query = node.get("query", "")
            resolved = resolve_icon(query)
            if resolved:
                node["icon_name"] = resolved
                node.setdefault("icon_role", "card")
                icon_count += 1
                if icon_count > MAX_ICONS_PER_SLIDE:
                    return None
                return node

            # Unresolvable — drop this icon node
            logger.debug("Dropping unresolvable icon: query=%s", query)
            return None

        # Recurse into children
        children = node.get("children")
        if isinstance(children, list):
            new_children = []
            for child in children:
                if isinstance(child, dict) and "type" in child:
                    result = _process(child)
                    if result is not None:
                        new_children.append(result)
                else:
                    # TextLeaf — keep as-is
                    new_children.append(child)
            node["children"] = new_children

        return node

    return [n for n in (_process(node) for node in nodes) if n is not None]


# ── Density normalization ──


def normalize_density(nodes: list[dict]) -> list[dict]:
    """Enforce maximum density rules.

    - Max 1 main title (h1 or h2)
    - Max MAX_TOP_LEVEL_BLOCKS top-level blocks
    - Max MAX_ITEMS_IN_GROUP items in any group element
    """
    # Cap top-level blocks
    if len(nodes) > MAX_TOP_LEVEL_BLOCKS:
        logger.debug("Trimming top-level blocks from %d to %d", len(nodes), MAX_TOP_LEVEL_BLOCKS)
        nodes = nodes[:MAX_TOP_LEVEL_BLOCKS]

    # Ensure max 1 main title
    title_count = 0
    result = []
    for node in nodes:
        ntype = node.get("type", "")
        if ntype in ("h1", "h2"):
            title_count += 1
            if title_count > 1:
                # Demote to h3
                node["type"] = "h3"
        result.append(node)

    # Cap items in group elements
    _GROUP_TYPES = {
        "box_group", "bullet_group", "icon_list", "timeline_group",
        "staircase_group", "cycle_group", "arrow_list", "sequence_arrow_group",
        "pyramid_group", "stats_group", "image_gallery_group",
    }

    for node in result:
        if node.get("type") in _GROUP_TYPES:
            children = node.get("children", [])
            if len(children) > MAX_ITEMS_IN_GROUP:
                logger.debug(
                    "Trimming %s items from %d to %d",
                    node["type"], len(children), MAX_ITEMS_IN_GROUP,
                )
                node["children"] = children[:MAX_ITEMS_IN_GROUP]

    return result


# ── Heading level normalization ──


def normalize_heading_levels(nodes: list[dict]) -> list[dict]:
    """Ensure only h1/h2/h3 are used. Demote h4/h5/h6 to h3."""

    def _process(node: dict) -> dict:
        ntype = node.get("type", "")
        if ntype in ("h4", "h5", "h6"):
            node["type"] = "h3"

        children = node.get("children")
        if isinstance(children, list):
            node["children"] = [
                _process(c) if isinstance(c, dict) and "type" in c else c
                for c in children
            ]
        return node

    return [_process(n) for n in nodes]


# ── Text limits ──


def enforce_text_limits(nodes: list[dict]) -> list[dict]:
    """Truncate text that exceeds word limits."""

    def _truncate_text(text: str, max_words: int) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "…"

    def _process(node: dict, context: str = "body") -> dict:
        ntype = node.get("type", "")

        # Determine context for word limit
        if ntype in ("h1", "h2"):
            ctx = "title"
        elif ntype == "h3":
            ctx = "subtitle"
        else:
            ctx = context

        # Process text leaves in children
        children = node.get("children")
        if isinstance(children, list):
            new_children = []
            for child in children:
                if isinstance(child, dict):
                    if "text" in child and "type" not in child:
                        # TextLeaf
                        text = child["text"]
                        if ctx == "title":
                            child["text"] = _truncate_text(text, MAX_TITLE_WORDS)
                        elif ctx == "subtitle":
                            child["text"] = _truncate_text(text, MAX_TITLE_WORDS)
                        else:
                            # Check if inside a card-like parent
                            parent_type = node.get("type", "")
                            is_card_child = parent_type in (
                                "box_item", "bullet_item", "icon_list_item",
                                "timeline_item", "stair_item", "cycle_item",
                                "arrow_list_item", "sequence_arrow_item", "pyramid_item",
                            )
                            limit = MAX_CARD_DESCRIPTION_WORDS if is_card_child else MAX_DESCRIPTION_WORDS
                            child["text"] = _truncate_text(text, limit)
                        new_children.append(child)
                    elif "type" in child:
                        new_children.append(_process(child, ctx))
                    else:
                        new_children.append(child)
                else:
                    new_children.append(child)
            node["children"] = new_children

        return node

    return [_process(n) for n in nodes]


# ── Template constraints ──


def enforce_template_constraints(
    nodes: list[dict],
    template: SlideTemplate,
) -> list[dict]:
    """Enforce template-specific constraints (min/max items, etc.)."""
    constraints = template.constraints

    max_items = constraints.get("max_items")
    min_items = constraints.get("min_items")
    max_blocks = constraints.get("max_blocks")

    # Cap top-level blocks to template max
    if max_blocks and len(nodes) > max_blocks:
        nodes = nodes[:max_blocks]

    # Cap/pad group items
    _ITEM_TYPES = {
        "box_group": "box_item",
        "bullet_group": "bullet_item",
        "icon_list": "icon_list_item",
        "timeline_group": "timeline_item",
        "staircase_group": "stair_item",
        "cycle_group": "cycle_item",
        "arrow_list": "arrow_list_item",
        "sequence_arrow_group": "sequence_arrow_item",
        "pyramid_group": "pyramid_item",
        "stats_group": "stats_item",
        "image_gallery_group": "image_gallery_item",
    }

    for node in nodes:
        ntype = node.get("type", "")
        if ntype in _ITEM_TYPES:
            children = node.get("children", [])
            item_type = _ITEM_TYPES[ntype]

            # Cap items
            if max_items and len(children) > max_items:
                node["children"] = children[:max_items]

            # Minimum items — only pad if significantly under
            if min_items and len(children) < min_items:
                # Don't pad with empty items — let the content stand
                # Just log for awareness
                logger.debug(
                    "Template %s expects min %d items, got %d",
                    template.id, min_items, len(children),
                )

    return nodes


# ── Card variant normalization ──


def normalize_card_variants(nodes: list[dict], theme: dict) -> list[dict]:
    """Ensure consistent card variants within a single slide.

    If multiple box_groups exist (rare but possible), unify their variants.
    """
    box_groups = [n for n in nodes if n.get("type") == "box_group"]
    if len(box_groups) <= 1:
        return nodes  # Nothing to unify

    # Use the first box_group's variant as reference
    reference_variant = box_groups[0].get("variant", "solid")
    for bg in box_groups[1:]:
        if bg.get("variant") != reference_variant:
            logger.debug(
                "Unifying box_group variant from %s to %s",
                bg.get("variant"), reference_variant,
            )
            bg["variant"] = reference_variant

    return nodes
