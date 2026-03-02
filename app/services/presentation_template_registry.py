"""Template registry — 10 solid templates with strict constraints.

Each template defines:
- Which narrative roles it supports
- How many content blocks it accepts
- Character limits per slot
- The exact PlateJS node structure it produces
- Surface occupation targets
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.presentation_briefs import NarrativeRole


@dataclass(frozen=True)
class TemplateSlot:
    """A named slot in a template that must be filled with content."""

    id: str  # "header", "card_1", "step_2", "kpi_1", etc.
    slot_type: str  # "title", "card", "step", "metric", "quote", "bullet"
    max_title_chars: int = 40
    max_body_chars: int = 120
    required: bool = True


@dataclass(frozen=True)
class TemplateDefinition:
    """A fully constrained template definition.

    The composer uses this to produce deterministic SlideContent output.
    """

    id: str
    name: str
    category: str  # "opening", "content", "data", "process", "comparison", "closing"
    allowed_roles: tuple[NarrativeRole, ...]
    min_blocks: int
    max_blocks: int
    density: str  # "low" | "medium" | "high"
    slots: tuple[TemplateSlot, ...]
    layout_type: str  # "background", "accent-top", "left-fit", "right-fit"
    surface_target: tuple[float, float]  # (min_ratio, max_ratio)
    node_structure: str  # "box_group", "stats_group", "timeline_group", etc.
    variant: str  # "sideline", "icons", "bar", "pills", "arrow", "large", ""
    needs_root_image: bool
    # Maps to existing TEMPLATE_CATALOG id for normalizer compatibility
    legacy_template_id: str


# ── Registry ──

TEMPLATE_REGISTRY: dict[str, TemplateDefinition] = {}


def _reg(t: TemplateDefinition) -> TemplateDefinition:
    TEMPLATE_REGISTRY[t.id] = t
    return t


# ── 1. Cover Hero ──

_reg(TemplateDefinition(
    id="cover_hero",
    name="Slide de couverture",
    category="opening",
    allowed_roles=(NarrativeRole.COVER,),
    min_blocks=0,
    max_blocks=0,
    density="low",
    slots=(
        TemplateSlot(id="title", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="subtitle", slot_type="title", max_title_chars=150, max_body_chars=0, required=False),
    ),
    layout_type="background",
    surface_target=(0.55, 0.82),
    node_structure="",
    variant="",
    needs_root_image=True,
    legacy_template_id="cover",
))

# ── 2. Big Statement ──

_reg(TemplateDefinition(
    id="big_statement",
    name="Declaration forte",
    category="opening",
    allowed_roles=(NarrativeRole.HOOK, NarrativeRole.INSIGHT),
    min_blocks=0,
    max_blocks=1,
    density="low",
    slots=(
        TemplateSlot(id="statement", slot_type="title", max_title_chars=120, max_body_chars=0),
        TemplateSlot(id="context", slot_type="title", max_title_chars=200, max_body_chars=0, required=False),
    ),
    layout_type="background",
    surface_target=(0.45, 0.70),
    node_structure="",
    variant="",
    needs_root_image=True,
    legacy_template_id="big_number",
))

# ── 3. Cards 3 ──

_reg(TemplateDefinition(
    id="cards_3",
    name="3 cartes sideline",
    category="content",
    allowed_roles=(
        NarrativeRole.CONTEXT, NarrativeRole.INSIGHT, NarrativeRole.PROOF,
        NarrativeRole.PLAN, NarrativeRole.PROCESS,
    ),
    min_blocks=3,
    max_blocks=3,
    density="medium",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="card_1", slot_type="card", max_title_chars=60, max_body_chars=200),
        TemplateSlot(id="card_2", slot_type="card", max_title_chars=60, max_body_chars=200),
        TemplateSlot(id="card_3", slot_type="card", max_title_chars=60, max_body_chars=200),
    ),
    layout_type="left-fit",
    surface_target=(0.68, 0.88),
    node_structure="box_group",
    variant="sideline",
    needs_root_image=True,
    legacy_template_id="cards_3",
))

# ── 4. Cards 4 ──

_reg(TemplateDefinition(
    id="cards_4",
    name="4 cartes avec icones",
    category="content",
    allowed_roles=(
        NarrativeRole.CONTEXT, NarrativeRole.INSIGHT, NarrativeRole.PROCESS,
        NarrativeRole.PLAN,
    ),
    min_blocks=4,
    max_blocks=4,
    density="high",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="card_1", slot_type="card", max_title_chars=60, max_body_chars=180),
        TemplateSlot(id="card_2", slot_type="card", max_title_chars=60, max_body_chars=180),
        TemplateSlot(id="card_3", slot_type="card", max_title_chars=60, max_body_chars=180),
        TemplateSlot(id="card_4", slot_type="card", max_title_chars=60, max_body_chars=180),
    ),
    layout_type="accent-top",
    surface_target=(0.72, 0.90),
    node_structure="box_group",
    variant="icons",
    needs_root_image=False,
    legacy_template_id="cards_4",
))

# ── 5. Timeline 4 ──

_reg(TemplateDefinition(
    id="timeline_4",
    name="Timeline chronologique",
    category="process",
    allowed_roles=(NarrativeRole.PROCESS, NarrativeRole.PLAN),
    min_blocks=3,
    max_blocks=5,
    density="medium",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="step_1", slot_type="step", max_title_chars=60, max_body_chars=180),
        TemplateSlot(id="step_2", slot_type="step", max_title_chars=60, max_body_chars=180),
        TemplateSlot(id="step_3", slot_type="step", max_title_chars=60, max_body_chars=180),
        TemplateSlot(id="step_4", slot_type="step", max_title_chars=60, max_body_chars=180, required=False),
        TemplateSlot(id="step_5", slot_type="step", max_title_chars=60, max_body_chars=180, required=False),
    ),
    layout_type="accent-top",
    surface_target=(0.65, 0.88),
    node_structure="timeline_group",
    variant="pills",
    needs_root_image=False,
    legacy_template_id="timeline",
))

# ── 6. Process Grid (Staircase) ──

_reg(TemplateDefinition(
    id="process_grid",
    name="Processus en escalier",
    category="process",
    allowed_roles=(NarrativeRole.PROCESS, NarrativeRole.PLAN),
    min_blocks=3,
    max_blocks=4,
    density="medium",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="step_1", slot_type="step", max_title_chars=60, max_body_chars=180),
        TemplateSlot(id="step_2", slot_type="step", max_title_chars=60, max_body_chars=180),
        TemplateSlot(id="step_3", slot_type="step", max_title_chars=60, max_body_chars=180),
        TemplateSlot(id="step_4", slot_type="step", max_title_chars=60, max_body_chars=180, required=False),
    ),
    layout_type="left-fit",
    surface_target=(0.70, 0.90),
    node_structure="staircase_group",
    variant="",
    needs_root_image=True,
    legacy_template_id="process_steps",
))

# ── 7. Comparison 2 Col ──

_reg(TemplateDefinition(
    id="comparison_2col",
    name="Comparaison 2 colonnes",
    category="comparison",
    allowed_roles=(NarrativeRole.COMPARISON,),
    min_blocks=2,
    max_blocks=2,
    density="medium",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="side_1", slot_type="comparison_side", max_title_chars=70, max_body_chars=300),
        TemplateSlot(id="side_2", slot_type="comparison_side", max_title_chars=70, max_body_chars=300),
    ),
    layout_type="accent-top",
    surface_target=(0.62, 0.85),
    node_structure="compare_group",
    variant="",
    needs_root_image=False,
    legacy_template_id="comparison_2col",
))

# ── 8. KPI Row ──

_reg(TemplateDefinition(
    id="kpi_row",
    name="Metriques cles",
    category="data",
    allowed_roles=(NarrativeRole.PROOF, NarrativeRole.INSIGHT),
    min_blocks=2,
    max_blocks=4,
    density="medium",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="kpi_1", slot_type="metric", max_title_chars=50, max_body_chars=120),
        TemplateSlot(id="kpi_2", slot_type="metric", max_title_chars=50, max_body_chars=120),
        TemplateSlot(id="kpi_3", slot_type="metric", max_title_chars=50, max_body_chars=120, required=False),
        TemplateSlot(id="kpi_4", slot_type="metric", max_title_chars=50, max_body_chars=120, required=False),
    ),
    layout_type="accent-top",
    surface_target=(0.55, 0.80),
    node_structure="stats_group",
    variant="bar",
    needs_root_image=False,
    legacy_template_id="kpi_3",
))

# ── 9. Quote / Proof ──

_reg(TemplateDefinition(
    id="quote_proof",
    name="Citation / Preuve",
    category="content",
    allowed_roles=(NarrativeRole.PROOF, NarrativeRole.HOOK),
    min_blocks=1,
    max_blocks=1,
    density="low",
    slots=(
        TemplateSlot(id="quote_text", slot_type="quote", max_title_chars=0, max_body_chars=500),
        TemplateSlot(id="attribution", slot_type="title", max_title_chars=80, max_body_chars=0, required=False),
    ),
    layout_type="background",
    surface_target=(0.45, 0.72),
    node_structure="quote",
    variant="large",
    needs_root_image=True,
    legacy_template_id="quote",
))

# ── 10. Closing Takeaway ──

_reg(TemplateDefinition(
    id="closing_takeaway",
    name="Points cles a retenir",
    category="closing",
    allowed_roles=(NarrativeRole.TAKEAWAY, NarrativeRole.CLOSING),
    min_blocks=3,
    max_blocks=4,
    density="medium",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="point_1", slot_type="bullet", max_title_chars=80, max_body_chars=180),
        TemplateSlot(id="point_2", slot_type="bullet", max_title_chars=80, max_body_chars=180),
        TemplateSlot(id="point_3", slot_type="bullet", max_title_chars=80, max_body_chars=180),
        TemplateSlot(id="point_4", slot_type="bullet", max_title_chars=80, max_body_chars=180, required=False),
    ),
    layout_type="accent-top",
    surface_target=(0.50, 0.76),
    node_structure="bullet_group",
    variant="arrow",
    needs_root_image=False,
    legacy_template_id="takeaway",
))


# ── 11. Cards 6 (dense content) ──

_reg(TemplateDefinition(
    id="cards_6",
    name="6 cartes denses",
    category="content",
    allowed_roles=(
        NarrativeRole.CONTEXT, NarrativeRole.INSIGHT, NarrativeRole.PROOF,
        NarrativeRole.PLAN, NarrativeRole.PROCESS, NarrativeRole.PROBLEM,
    ),
    min_blocks=5,
    max_blocks=6,
    density="high",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="card_1", slot_type="card", max_title_chars=60, max_body_chars=150),
        TemplateSlot(id="card_2", slot_type="card", max_title_chars=60, max_body_chars=150),
        TemplateSlot(id="card_3", slot_type="card", max_title_chars=60, max_body_chars=150),
        TemplateSlot(id="card_4", slot_type="card", max_title_chars=60, max_body_chars=150),
        TemplateSlot(id="card_5", slot_type="card", max_title_chars=60, max_body_chars=150),
        TemplateSlot(id="card_6", slot_type="card", max_title_chars=60, max_body_chars=150, required=False),
    ),
    layout_type="accent-top",
    surface_target=(0.78, 0.95),
    node_structure="box_group",
    variant="sideline",
    needs_root_image=False,
    legacy_template_id="cards_4",
))

# ── 12. Team Grid ──

_reg(TemplateDefinition(
    id="team_grid",
    name="Equipe / Profils",
    category="content",
    allowed_roles=(NarrativeRole.TEAM,),
    min_blocks=2,
    max_blocks=6,
    density="high",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="card_1", slot_type="card", max_title_chars=60, max_body_chars=150),
        TemplateSlot(id="card_2", slot_type="card", max_title_chars=60, max_body_chars=150),
        TemplateSlot(id="card_3", slot_type="card", max_title_chars=60, max_body_chars=150, required=False),
        TemplateSlot(id="card_4", slot_type="card", max_title_chars=60, max_body_chars=150, required=False),
        TemplateSlot(id="card_5", slot_type="card", max_title_chars=60, max_body_chars=150, required=False),
        TemplateSlot(id="card_6", slot_type="card", max_title_chars=60, max_body_chars=150, required=False),
    ),
    layout_type="accent-top",
    surface_target=(0.70, 0.92),
    node_structure="box_group",
    variant="icons",
    needs_root_image=False,
    legacy_template_id="team",
))

# ── 13. Bullet Dense ──

_reg(TemplateDefinition(
    id="bullet_dense",
    name="Liste detaillee",
    category="content",
    allowed_roles=(
        NarrativeRole.CONTEXT, NarrativeRole.INSIGHT, NarrativeRole.PLAN,
        NarrativeRole.PROOF, NarrativeRole.PROBLEM,
    ),
    min_blocks=4,
    max_blocks=6,
    density="high",
    slots=(
        TemplateSlot(id="header", slot_type="title", max_title_chars=80, max_body_chars=0),
        TemplateSlot(id="point_1", slot_type="bullet", max_title_chars=70, max_body_chars=180),
        TemplateSlot(id="point_2", slot_type="bullet", max_title_chars=70, max_body_chars=180),
        TemplateSlot(id="point_3", slot_type="bullet", max_title_chars=70, max_body_chars=180),
        TemplateSlot(id="point_4", slot_type="bullet", max_title_chars=70, max_body_chars=180),
        TemplateSlot(id="point_5", slot_type="bullet", max_title_chars=70, max_body_chars=180, required=False),
        TemplateSlot(id="point_6", slot_type="bullet", max_title_chars=70, max_body_chars=180, required=False),
    ),
    layout_type="accent-top",
    surface_target=(0.68, 0.90),
    node_structure="bullet_group",
    variant="arrow",
    needs_root_image=False,
    legacy_template_id="takeaway",
))


# ── Lookup helpers ──


def get_template_def(template_id: str) -> TemplateDefinition | None:
    """Get a template definition by ID."""
    return TEMPLATE_REGISTRY.get(template_id)


def get_templates_for_role(role: NarrativeRole) -> list[TemplateDefinition]:
    """Get all templates compatible with a narrative role."""
    return [t for t in TEMPLATE_REGISTRY.values() if role in t.allowed_roles]


def get_all_template_ids() -> list[str]:
    """Get all registered template IDs."""
    return list(TEMPLATE_REGISTRY.keys())
