"""Deterministic slide planner — maps narrative roles to visual constraints.

No LLM call here. The planner translates the semantic outline into concrete
layout/component constraints that the per-slide generator must follow.

Diversity is enforced via sliding-window clusters (not just previous-slide checks).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
#  Models
# ══════════════════════════════════════════════


class SlidePlan(BaseModel):
    """Constraints for a single slide, derived deterministically from the outline."""

    slide_number: int
    role: str
    title: str
    goal: str
    key_points: list[str] = Field(default_factory=list)
    # Deterministic constraints
    layout: str
    allowed_components: list[str] = Field(default_factory=list)
    preferred_component: str | None = None
    allowed_variants: dict[str, list[str]] = Field(default_factory=dict)
    min_items: int = 0
    max_items: int = 6
    needs_image: bool = False
    density: str = "medium"  # "low" | "medium" | "high"
    font_scale: str = "M"   # "S" | "M" | "L"


class DeckPlan(BaseModel):
    """Full deck plan — all slides planned together for diversity enforcement."""

    presentation_title: str
    audience: str = "general"
    tone: str = "professional"
    slides: list[SlidePlan] = Field(default_factory=list)


# ══════════════════════════════════════════════
#  Role → Plan mapping table
# ══════════════════════════════════════════════

_RolePlanDef = dict[str, Any]

ROLE_PLAN_TABLE: dict[str, _RolePlanDef] = {
    "cover": {
        "layouts": ["background"],
        "components": [],
        "preferred": None,
        "variants": {},
        "min_items": 0,
        "max_items": 0,
        "needs_image": True,
        "density": "low",
        "font_scale": "L",
    },
    "hook": {
        "layouts": ["background", "left-fit"],
        "components": ["QUOTE", "STATS"],
        "preferred": "QUOTE",
        "variants": {"QUOTE": ["large", "sidebar"]},
        "min_items": 0,
        "max_items": 1,
        "needs_image": True,
        "density": "low",
        "font_scale": "L",
    },
    "context": {
        "layouts": ["left-fit", "right-fit", "accent-top"],
        "components": ["ICONS", "BOXES", "BULLETS"],
        "preferred": "ICONS",
        "variants": {"BOXES": ["sideline", "icons"], "ICONS": ["default"]},
        "min_items": 2,
        "max_items": 4,
        "needs_image": True,
        "density": "medium",
        "font_scale": "M",
    },
    "problem": {
        "layouts": ["accent-top", "left-fit"],
        "components": ["ARROWS", "BOXES", "BEFORE-AFTER"],
        "preferred": "ARROWS",
        "variants": {"BOXES": ["sideline", "outline"]},
        "min_items": 2,
        "max_items": 4,
        "needs_image": False,
        "density": "medium",
        "font_scale": "M",
    },
    "insight": {
        "layouts": ["right-fit", "left-fit", "accent-top"],
        "components": ["STATS", "ICONS", "BOXES", "STAIRCASE"],
        "preferred": "STATS",
        "variants": {"BOXES": ["sideline", "icons"], "STATS": ["bar", "circle"]},
        "min_items": 2,
        "max_items": 4,
        "needs_image": True,
        "density": "medium",
        "font_scale": "M",
    },
    "proof": {
        "layouts": ["accent-top", "right-fit"],
        "components": ["STATS", "CHART", "BOXES", "QUOTE"],
        "preferred": "STATS",
        "variants": {"STATS": ["bar", "circle"], "CHART": ["donut", "bar"], "QUOTE": ["sidebar"]},
        "min_items": 2,
        "max_items": 4,
        "needs_image": False,
        "density": "medium",
        "font_scale": "M",
    },
    "process": {
        "layouts": ["accent-top", "left-fit"],
        "components": ["TIMELINE", "STAIRCASE", "ARROWS", "CYCLE"],
        "preferred": "TIMELINE",
        "variants": {"TIMELINE": ["pills", "default"]},
        "min_items": 3,
        "max_items": 4,
        "needs_image": False,
        "density": "high",
        "font_scale": "S",
    },
    "plan": {
        "layouts": ["accent-top", "right-fit"],
        "components": ["TIMELINE", "BOXES", "STAIRCASE"],
        "preferred": "TIMELINE",
        "variants": {"TIMELINE": ["pills", "default"]},
        "min_items": 3,
        "max_items": 4,
        "needs_image": False,
        "density": "high",
        "font_scale": "S",
    },
    "comparison": {
        "layouts": ["accent-top", "left-fit"],
        "components": ["COMPARE", "BEFORE-AFTER", "PROS-CONS", "TABLE"],
        "preferred": "COMPARE",
        "variants": {},
        "min_items": 2,
        "max_items": 2,
        "needs_image": False,
        "density": "medium",
        "font_scale": "M",
    },
    "team": {
        "layouts": ["accent-top"],
        "components": ["IMAGE-GALLERY", "BOXES"],
        "preferred": "IMAGE-GALLERY",
        "variants": {"IMAGE-GALLERY": ["team", "with-text"]},
        "min_items": 2,
        "max_items": 5,
        "needs_image": False,
        "density": "high",
        "font_scale": "S",
    },
    "takeaway": {
        "layouts": ["accent-top", "left-fit"],
        "components": ["BULLETS", "BOXES"],
        "preferred": "BULLETS",
        "variants": {"BULLETS": ["arrow", "numbered"]},
        "min_items": 3,
        "max_items": 4,
        "needs_image": False,
        "density": "medium",
        "font_scale": "M",
    },
    "closing": {
        "layouts": ["background"],
        "components": ["QUOTE"],
        "preferred": None,
        "variants": {},
        "min_items": 0,
        "max_items": 1,
        "needs_image": True,
        "density": "low",
        "font_scale": "L",
    },
}

# Fallback for unknown roles
_DEFAULT_PLAN: _RolePlanDef = {
    "layouts": ["accent-top", "left-fit", "right-fit"],
    "components": ["BOXES", "BULLETS", "ICONS"],
    "preferred": "BOXES",
    "variants": {"BOXES": ["sideline", "outline"]},
    "min_items": 2,
    "max_items": 4,
    "needs_image": False,
    "density": "medium",
    "font_scale": "M",
}


# ══════════════════════════════════════════════
#  Cluster diversity settings
# ══════════════════════════════════════════════

LAYOUT_WINDOW = 3       # Sliding window for layout diversity
COMPONENT_WINDOW = 4    # Sliding window for component diversity (larger = more variety)
MAX_IMAGELESS_STREAK = 2  # Max consecutive slides without image


# ══════════════════════════════════════════════
#  Planner logic
# ══════════════════════════════════════════════


def _pick_layout(
    available: list[str],
    recent_layouts: list[str],
) -> str:
    """Pick a layout maximizing diversity within the cluster window."""
    if not available:
        return "accent-top"

    # Try to pick one not used in the recent window
    for layout in available:
        if layout not in recent_layouts:
            return layout

    # All used in recent window — pick the least recently used
    for layout in available:
        if layout != recent_layouts[-1]:  # At least avoid immediate repeat
            return layout

    return available[0]


def _pick_component(
    available: list[str],
    preferred: str | None,
    recent_components: list[str],
) -> str | None:
    """Pick a preferred component avoiding cluster repetition."""
    if not available:
        return preferred

    # Preferred is not in recent window → use it
    if preferred and preferred not in recent_components:
        return preferred

    # Pick first not in recent window
    for comp in available:
        if comp not in recent_components:
            return comp

    # All used in recent window — avoid immediate repeat
    if recent_components:
        for comp in available:
            if comp != recent_components[-1]:
                return comp

    return available[0] if available else preferred


def build_deck_plan(outline: Any) -> DeckPlan:
    """Build a complete deck plan from a GeneratedOutline.

    Args:
        outline: GeneratedOutline with .slides, .presentation_title, .audience, .tone

    Returns:
        DeckPlan with one SlidePlan per slide, constraints assigned deterministically.
    """
    plans: list[SlidePlan] = []
    recent_layouts: list[str] = []
    recent_components: list[str] = []
    imageless_streak = 0

    for slide in outline.slides:
        role_str = slide.role.value if hasattr(slide.role, "value") else str(slide.role)
        plan_def = ROLE_PLAN_TABLE.get(role_str, _DEFAULT_PLAN)

        # Pick layout with cluster diversity
        available_layouts = plan_def["layouts"]
        layout = _pick_layout(available_layouts, recent_layouts[-LAYOUT_WINDOW:])

        # Pick component with cluster diversity
        available_components = plan_def["components"]
        preferred = plan_def.get("preferred")
        component = _pick_component(
            available_components,
            preferred,
            recent_components[-COMPONENT_WINDOW:],
        )

        # Image streak enforcement
        needs_image = plan_def["needs_image"]
        if not needs_image and imageless_streak >= MAX_IMAGELESS_STREAK:
            needs_image = True  # Force image after N imageless slides
            logger.debug(
                "Slide %d: forcing image (streak=%d)", slide.number, imageless_streak
            )

        plan = SlidePlan(
            slide_number=slide.number,
            role=role_str,
            title=slide.title,
            goal=slide.goal,
            key_points=list(slide.key_points) if slide.key_points else [],
            layout=layout,
            allowed_components=list(available_components),
            preferred_component=component,
            allowed_variants=dict(plan_def.get("variants", {})),
            min_items=plan_def["min_items"],
            max_items=plan_def["max_items"],
            needs_image=needs_image,
            density=plan_def["density"],
            font_scale=plan_def["font_scale"],
        )
        plans.append(plan)

        # Update tracking
        recent_layouts.append(layout)
        if component:
            recent_components.append(component)
        if needs_image:
            imageless_streak = 0
        else:
            imageless_streak += 1

    return DeckPlan(
        presentation_title=outline.presentation_title,
        audience=getattr(outline, "audience", "general"),
        tone=getattr(outline, "tone", "professional"),
        slides=plans,
    )
