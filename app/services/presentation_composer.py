"""Deterministic slide composer — transforms filled template slots into PlateJS content_json.

No LLM involved. This is pure structural transformation.
The composer produces the exact SlideNode tree that the frontend renders.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.presentation_template_registry import TemplateDefinition

logger = logging.getLogger(__name__)

# ── Density → SlideSizing mapping ──

_DENSITY_TO_SIZING: dict[str, dict[str, str]] = {
    "low": {
        "font_scale": "L",
        "block_spacing": "loose",
        "card_width": "M",
    },
    "medium": {
        "font_scale": "M",
        "block_spacing": "normal",
        "card_width": "M",
    },
    "high": {
        "font_scale": "S",
        "block_spacing": "tight",
        "card_width": "L",  # Wider to accommodate more blocks
    },
}


def compose_slide(
    template: TemplateDefinition,
    filled_content: dict[str, Any],
    theme_data: dict | None = None,
) -> dict[str, Any]:
    """Compose a final SlideContent-compatible dict from template + filled slots.

    Returns: {content_json, layout_type, root_image, bg_color, sizing}
    """
    composer = _COMPOSERS.get(template.id)
    if not composer:
        logger.warning("No composer for template %s, using generic", template.id)
        composer = _compose_generic

    content_json = composer(filled_content, template, theme_data)

    # Build root_image if template needs one
    root_image = None
    if template.needs_root_image:
        title = filled_content.get("header") or filled_content.get("title") or ""
        root_image = _build_root_image(title, template.layout_type)

    # Compute sizing from template density
    sizing = _DENSITY_TO_SIZING.get(template.density, _DENSITY_TO_SIZING["medium"])

    return {
        "content_json": content_json,
        "layout_type": template.layout_type,
        "root_image": root_image,
        "bg_color": None,
        "sizing": sizing,
    }


# ── Composer functions per template ──


def _compose_cover_hero(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    title = filled.get("title", "Présentation")
    subtitle = filled.get("subtitle")

    nodes: list[dict] = [
        {"type": "h1", "children": [{"text": title}]},
    ]
    if subtitle:
        nodes.append({"type": "p", "children": [{"text": subtitle}]})

    return nodes


def _compose_big_statement(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    statement = filled.get("statement", "")
    context = filled.get("context")

    nodes: list[dict] = [
        {"type": "h2", "children": [{"text": statement}]},
    ]
    if context:
        nodes.append({"type": "p", "children": [{"text": context}]})

    return nodes


def _compose_cards_3(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "")
    cards = filled.get("cards", [])

    box_items = []
    for card in cards[:3]:
        box_items.append({
            "type": "box_item",
            "children": [
                {"type": "h3", "children": [{"text": card.get("title", "")}]},
                {"type": "p", "children": [{"text": card.get("body", "")}]},
            ],
        })

    # Pad to 3 if needed
    while len(box_items) < 3:
        box_items.append({
            "type": "box_item",
            "children": [
                {"type": "h3", "children": [{"text": "—"}]},
                {"type": "p", "children": [{"text": ""}]},
            ],
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "box_group", "variant": "sideline", "children": box_items},
    ]


def _compose_cards_4(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "")
    cards = filled.get("cards", [])

    box_items = []
    for card in cards[:4]:
        icon_query = card.get("icon_query", "star")
        box_items.append({
            "type": "box_item",
            "children": [
                {"type": "icon", "query": icon_query},
                {"type": "h3", "children": [{"text": card.get("title", "")}]},
                {"type": "p", "children": [{"text": card.get("body", "")}]},
            ],
        })

    # Pad to 4 if needed
    while len(box_items) < 4:
        box_items.append({
            "type": "box_item",
            "children": [
                {"type": "icon", "query": "star"},
                {"type": "h3", "children": [{"text": "—"}]},
                {"type": "p", "children": [{"text": ""}]},
            ],
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "box_group", "variant": "icons", "children": box_items},
    ]


def _compose_timeline_4(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "")
    steps = filled.get("steps", [])

    timeline_items = []
    for step in steps[:5]:
        timeline_items.append({
            "type": "timeline_item",
            "children": [
                {"type": "h3", "children": [{"text": step.get("title", "")}]},
                {"type": "p", "children": [{"text": step.get("body", "")}]},
            ],
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "timeline_group", "variant": "pills", "children": timeline_items},
    ]


def _compose_process_grid(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "")
    steps = filled.get("steps", [])

    stair_items = []
    for step in steps[:4]:
        stair_items.append({
            "type": "stair_item",
            "children": [
                {"type": "h3", "children": [{"text": step.get("title", "")}]},
                {"type": "p", "children": [{"text": step.get("body", "")}]},
            ],
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "staircase_group", "children": stair_items},
    ]


def _compose_comparison_2col(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "")
    sides = filled.get("sides", [])

    compare_sides = []
    for side in sides[:2]:
        compare_sides.append({
            "type": "compare_side",
            "children": [
                {"type": "h3", "children": [{"text": side.get("title", "")}]},
                {"type": "p", "children": [{"text": side.get("body", "")}]},
            ],
        })

    # Pad to 2 if needed
    while len(compare_sides) < 2:
        compare_sides.append({
            "type": "compare_side",
            "children": [
                {"type": "h3", "children": [{"text": "—"}]},
                {"type": "p", "children": [{"text": ""}]},
            ],
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "compare_group", "children": compare_sides},
    ]


def _compose_kpi_row(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "")
    kpis = filled.get("kpis", [])

    stats_items = []
    for kpi in kpis[:4]:
        stats_items.append({
            "type": "stats_item",
            "value": kpi.get("value", "—"),
            "children": [
                {"type": "h3", "children": [{"text": kpi.get("label", "")}]},
                {"type": "p", "children": [{"text": kpi.get("context", "")}]},
            ],
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "stats_group", "variant": "bar", "children": stats_items},
    ]


def _compose_quote_proof(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    quote_text = filled.get("quote_text", "")
    attribution = filled.get("attribution")

    children: list[dict] = [
        {"type": "p", "children": [{"text": quote_text}]},
    ]
    if attribution:
        children.append({"type": "p", "children": [{"text": f"— {attribution}"}]})

    return [
        {"type": "quote", "variant": "large", "children": children},
    ]


def _compose_closing_takeaway(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "À retenir")
    points = filled.get("points", [])

    bullet_items = []
    for point in points[:4]:
        bullet_items.append({
            "type": "bullet_item",
            "children": [
                {"type": "h3", "children": [{"text": point.get("text", "")}]},
                {"type": "p", "children": [{"text": ""}]},
            ],
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "bullet_group", "variant": "arrow", "children": bullet_items},
    ]


def _compose_cards_6(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "")
    cards = filled.get("cards", [])

    box_items = []
    for card in cards[:6]:
        box_items.append({
            "type": "box_item",
            "children": [
                {"type": "h3", "children": [{"text": card.get("title", "")}]},
                {"type": "p", "children": [{"text": card.get("body", "")}]},
            ],
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "box_group", "variant": "sideline", "children": box_items},
    ]


def _compose_team_grid(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "")
    cards = filled.get("cards", [])

    box_items = []
    for card in cards[:6]:
        icon_query = card.get("icon_query", "user")
        box_items.append({
            "type": "box_item",
            "children": [
                {"type": "icon", "query": icon_query},
                {"type": "h3", "children": [{"text": card.get("title", "")}]},
                {"type": "p", "children": [{"text": card.get("body", "")}]},
            ],
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "box_group", "variant": "icons", "children": box_items},
    ]


def _compose_bullet_dense(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    header = filled.get("header", "")
    points = filled.get("points", [])

    bullet_items = []
    for point in points[:6]:
        children: list[dict] = [
            {"type": "h3", "children": [{"text": point.get("title", point.get("text", ""))}]},
        ]
        body = point.get("body", "")
        if body:
            children.append({"type": "p", "children": [{"text": body}]})
        else:
            children.append({"type": "p", "children": [{"text": ""}]})
        bullet_items.append({
            "type": "bullet_item",
            "children": children,
        })

    return [
        {"type": "h2", "children": [{"text": header}]},
        {"type": "bullet_group", "variant": "arrow", "children": bullet_items},
    ]


def _compose_generic(
    filled: dict[str, Any],
    template: TemplateDefinition,
    theme: dict | None,
) -> list[dict]:
    """Generic fallback composer — produces cards_3 layout."""
    header = filled.get("header", filled.get("title", ""))
    cards = filled.get("cards", [])

    if not cards:
        # Try to extract from other formats
        for key in ("steps", "kpis", "sides", "points"):
            if key in filled and isinstance(filled[key], list):
                cards = [{"title": item.get("title", item.get("label", item.get("text", ""))),
                          "body": item.get("body", item.get("context", ""))}
                         for item in filled[key]]
                break

    box_items = []
    for card in cards[:3]:
        box_items.append({
            "type": "box_item",
            "children": [
                {"type": "h3", "children": [{"text": card.get("title", "")}]},
                {"type": "p", "children": [{"text": card.get("body", "")}]},
            ],
        })

    nodes: list[dict] = []
    if header:
        nodes.append({"type": "h2", "children": [{"text": header}]})
    if box_items:
        nodes.append({"type": "box_group", "variant": "sideline", "children": box_items})

    return nodes


# ── Root image builder ──


def _build_root_image(title: str, layout_type: str) -> dict[str, Any]:
    """Build a contextual root_image query from the slide title."""
    # Generate a descriptive image query
    query = f"professional high quality photograph related to {title}, modern office environment, natural lighting"
    return {
        "query": query,
        "layout_type": layout_type,
    }


# ── Composer registry ──


_COMPOSERS: dict[str, Any] = {
    "cover_hero": _compose_cover_hero,
    "big_statement": _compose_big_statement,
    "cards_3": _compose_cards_3,
    "cards_4": _compose_cards_4,
    "cards_6": _compose_cards_6,
    "timeline_4": _compose_timeline_4,
    "process_grid": _compose_process_grid,
    "comparison_2col": _compose_comparison_2col,
    "kpi_row": _compose_kpi_row,
    "quote_proof": _compose_quote_proof,
    "closing_takeaway": _compose_closing_takeaway,
    "team_grid": _compose_team_grid,
    "bullet_dense": _compose_bullet_dense,
}
