"""Semantic slide briefs — the LLM's output before template assignment.

A SlideBrief captures WHAT a slide communicates, not HOW it looks.
The template selector and composer handle the visual realization.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NarrativeRole(str, Enum):
    """The rhetorical function of a slide in the presentation arc."""

    COVER = "cover"
    HOOK = "hook"
    CONTEXT = "context"
    PROBLEM = "problem"
    INSIGHT = "insight"
    PROOF = "proof"
    PROCESS = "process"
    PLAN = "plan"
    COMPARISON = "comparison"
    TEAM = "team"
    TAKEAWAY = "takeaway"
    CLOSING = "closing"


class SlideBlock(BaseModel):
    """A semantic content block — what the slide says, not how it looks."""

    kind: str  # "point", "step", "metric", "quote", "comparison_side", "team_member"
    priority: int = Field(default=1, ge=1, le=3)  # 1 = most important
    title: str
    body: str = ""
    metrics: list[str] = Field(default_factory=list)  # e.g. ["+142%", "3.2M"]
    visual_weight: str = "medium"  # "low" | "medium" | "high"
    can_pair_with_icon: bool = True


class SlideBrief(BaseModel):
    """Semantic brief for a single slide — produced by LLM, consumed by template engine.

    The LLM describes WHAT to communicate, the engine decides HOW to display it.
    """

    slide_goal: str  # e.g. "explain_process", "show_results", "introduce_team"
    narrative_role: NarrativeRole
    key_message: str  # The single takeaway of this slide
    title: str
    subtitle: str | None = None
    density_target: str = "medium"  # "low" | "medium" | "high"
    preferred_visual: str | None = None  # "timeline", "cards", "stats", "comparison", "quote"
    blocks: list[SlideBlock] = Field(default_factory=list)
    asset_need: str = "none"  # "none" | "photo" | "icon" | "chart"
    proof_level: str = "none"  # "none" | "low" | "medium" | "high"


class DeckContext(BaseModel):
    """Tracks deck-level state during generation for diversity and coherence."""

    deck_title: str = ""
    deck_prompt: str = ""
    total_slides: int = 0
    generated_briefs: list[SlideBrief] = Field(default_factory=list)
    used_templates: list[str] = Field(default_factory=list)
    used_layouts: list[str] = Field(default_factory=list)
