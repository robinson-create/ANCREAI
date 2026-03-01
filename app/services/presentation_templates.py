"""Internal slide template catalog with intents and auto-suggestion.

Templates are never exposed directly to the user.
They guide the LLM, power the normalizer, and serve as premium fallbacks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Slide Intent ──


class SlideIntent(str, Enum):
    """Communication intent of a slide — distinct from its visual template."""

    INFORM = "inform"
    COMPARE = "compare"
    SEQUENCE = "sequence"
    HIGHLIGHT_METRIC = "highlight_metric"
    PERSUADE = "persuade"
    SUMMARIZE = "summarize"
    INTRODUCE_SECTION = "introduce_section"
    SHOWCASE_TEAM = "showcase_team"
    QUOTE_INSIGHT = "quote_insight"
    OPEN = "open"  # Cover / opening slide
    CLOSE = "close"  # Takeaway / closing slide


# ── Template definition ──


@dataclass(frozen=True)
class SlideTemplate:
    id: str  # "cover", "kpi_3", "comparison_2col"
    name: str  # Human label
    category: str  # "opening", "content", "data", "process", "closing"
    intent: SlideIntent  # Primary communication intent
    description: str  # Concise — injected into LLM prompt
    layout_type: str  # Default layout for this template
    structure: list[dict[str, Any]]  # Reference content_json skeleton
    constraints: dict[str, Any]  # Max items, text limits, etc.
    icon_slots: int = 0  # Number of expected icon positions
    recommended_variants: tuple[str, ...] = ()


# ── Suggestion result ──


@dataclass
class TemplateSuggestion:
    template_id: str
    confidence: float  # 0.0 – 1.0
    reason: str  # Why this template was selected (debug / logs / future UI)
    intent: SlideIntent


# ── Template catalog ──

TEMPLATE_CATALOG: dict[str, SlideTemplate] = {}


def _register(t: SlideTemplate) -> SlideTemplate:
    TEMPLATE_CATALOG[t.id] = t
    return t


# ── OPENING ──

_register(SlideTemplate(
    id="cover",
    name="Slide de couverture",
    category="opening",
    intent=SlideIntent.OPEN,
    description="Grand titre centré (h1), sous-titre court (p). Fond image ou couleur d'accent. Aucun bloc de contenu.",
    layout_type="background",
    structure=[
        {"type": "h1", "children": [{"text": "{title}"}]},
        {"type": "p", "children": [{"text": "{subtitle}"}]},
    ],
    constraints={"max_words_title": 8, "max_words_subtitle": 15, "max_blocks": 2},
))

_register(SlideTemplate(
    id="section_divider",
    name="Intertitre de section",
    category="opening",
    intent=SlideIntent.INTRODUCE_SECTION,
    description="Titre de section large (h1), éventuellement numéroté, plus description courte. Layout accent-top ou coloré.",
    layout_type="accent-top",
    structure=[
        {"type": "h1", "children": [{"text": "{section_number}. {title}"}]},
        {"type": "p", "children": [{"text": "{description}"}]},
    ],
    constraints={"max_words_title": 6, "max_words_description": 20, "max_blocks": 2},
))

# ── CARDS ──

_register(SlideTemplate(
    id="cards_3",
    name="3 cartes avec bordure latérale",
    category="content",
    intent=SlideIntent.INFORM,
    description="Titre h2 + box_group (variant sideline) avec 3 box_items. Chaque carte a un bord gauche coloré, titre h3 percutant et description avec chiffre concret. Rendu premium type consulting.",
    layout_type="left-fit",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {
            "type": "box_group", "variant": "sideline",
            "children": [
                {"type": "box_item", "children": [
                    {"type": "h3", "children": [{"text": "{card_title}"}]},
                    {"type": "p", "children": [{"text": "{card_desc}"}]},
                ]}
            ] * 3,
        },
    ],
    constraints={"min_items": 3, "max_items": 3, "max_words_per_card": 15, "max_blocks": 2},
    icon_slots=0,
    recommended_variants=("sideline", "icons", "solid"),
))

_register(SlideTemplate(
    id="cards_4",
    name="4 cartes en grille avec icônes",
    category="content",
    intent=SlideIntent.INFORM,
    description="Titre h2 + box_group (variant icons) avec 4 box_items en grille 2×2. Chaque carte: icône en cercle coloré + titre h3 + description courte avec donnée concrète.",
    layout_type="accent-top",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {
            "type": "box_group", "variant": "icons",
            "children": [{"type": "box_item", "children": [
                {"type": "icon", "query": "{icon_query}"},
                {"type": "h3", "children": [{"text": "{card_title}"}]},
                {"type": "p", "children": [{"text": "{card_desc}"}]},
            ]}] * 4,
        },
    ],
    constraints={"min_items": 4, "max_items": 4, "max_words_per_card": 12, "max_blocks": 2},
    icon_slots=4,
    recommended_variants=("icons", "sideline"),
))

# ── DATA ──

_register(SlideTemplate(
    id="kpi_3",
    name="3 métriques clés avec barres",
    category="data",
    intent=SlideIntent.HIGHLIGHT_METRIC,
    description="Titre h2 + stats_group (variant bar) avec 2-3 stats_items. Chaque item: gros chiffre percutant (value), label h3, description comparative. Les barres de progression renforcent l'impact visuel.",
    layout_type="accent-top",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {
            "type": "stats_group", "variant": "bar",
            "children": [
                {"type": "stats_item", "value": "{value}", "children": [
                    {"type": "h3", "children": [{"text": "{label}"}]},
                    {"type": "p", "children": [{"text": "{desc}"}]},
                ]},
            ] * 3,
        },
    ],
    constraints={"min_items": 2, "max_items": 4, "max_blocks": 2},
    recommended_variants=("bar", "circle", "default"),
))

_register(SlideTemplate(
    id="big_number",
    name="Chiffre clé mis en avant",
    category="data",
    intent=SlideIntent.HIGHLIGHT_METRIC,
    description="Un seul stats_item centré: très gros chiffre (value), label h2, contexte p. Layout background ou accent-top.",
    layout_type="background",
    structure=[
        {"type": "stats_group", "variant": "default", "children": [
            {"type": "stats_item", "value": "{big_value}", "children": [
                {"type": "h2", "children": [{"text": "{label}"}]},
                {"type": "p", "children": [{"text": "{context}"}]},
            ]},
        ]},
    ],
    constraints={"max_items": 1, "max_blocks": 1},
    recommended_variants=("default", "circle"),
))

# ── COMPARISON ──

_register(SlideTemplate(
    id="comparison_2col",
    name="Comparatif en 2 colonnes",
    category="content",
    intent=SlideIntent.COMPARE,
    description="Titre h2 + compare_group avec 2 compare_sides. Chaque côté: titre h3 percutant + 2-3 paragraphes courts avec données comparatives chiffrées. Créer un contraste visuel fort entre les deux colonnes.",
    layout_type="accent-top",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {"type": "compare_group", "children": [
            {"type": "compare_side", "children": [
                {"type": "h3", "children": [{"text": "{col_title}"}]},
                {"type": "p", "children": [{"text": "{col_content_1}"}]},
                {"type": "p", "children": [{"text": "{col_content_2}"}]},
            ]},
        ] * 2},
    ],
    constraints={"max_words_per_side": 40, "max_blocks": 2},
))

_register(SlideTemplate(
    id="pros_cons",
    name="Pour / Contre",
    category="content",
    intent=SlideIntent.COMPARE,
    description="Titre h2 + pros_cons_group. Avantages (pros_item) et inconvénients (cons_item) avec h3 percutant + p avec données concrètes.",
    layout_type="accent-top",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {"type": "pros_cons_group", "children": [
            {"type": "pros_item", "children": [
                {"type": "h3", "children": [{"text": "Avantages"}]},
                {"type": "p", "children": [{"text": "{pro}"}]},
            ]},
            {"type": "cons_item", "children": [
                {"type": "h3", "children": [{"text": "Inconvénients"}]},
                {"type": "p", "children": [{"text": "{con}"}]},
            ]},
        ]},
    ],
    constraints={"max_items_per_side": 4, "max_blocks": 2},
))

_register(SlideTemplate(
    id="before_after",
    name="Avant / Après",
    category="content",
    intent=SlideIntent.COMPARE,
    description="Titre h2 + before_after_group. Deux côtés 'Avant' et 'Après' avec h3 + p contenant des données concrètes de transformation.",
    layout_type="accent-top",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {"type": "before_after_group", "children": [
            {"type": "before_after_side", "children": [
                {"type": "h3", "children": [{"text": "Avant"}]},
                {"type": "p", "children": [{"text": "{before_desc}"}]},
            ]},
            {"type": "before_after_side", "children": [
                {"type": "h3", "children": [{"text": "Après"}]},
                {"type": "p", "children": [{"text": "{after_desc}"}]},
            ]},
        ]},
    ],
    constraints={"max_words_per_side": 30, "max_blocks": 2},
))

# ── PROCESS ──

_register(SlideTemplate(
    id="timeline",
    name="Timeline / Chronologie",
    category="process",
    intent=SlideIntent.SEQUENCE,
    description="Titre h2 + timeline_group (variant pills) avec 3-5 timeline_items numérotés. Chaque étape: titre h3 daté ou numéroté + description avec résultat concret. Les pills colorés créent un parcours visuel fort.",
    layout_type="accent-top",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {"type": "timeline_group", "variant": "pills", "children": [
            {"type": "timeline_item", "children": [
                {"type": "h3", "children": [{"text": "{step_title}"}]},
                {"type": "p", "children": [{"text": "{step_desc}"}]},
            ]},
        ] * 4},
    ],
    constraints={"min_items": 3, "max_items": 5, "max_words_per_item": 12, "max_blocks": 2},
    recommended_variants=("pills", "default", "minimal"),
))

_register(SlideTemplate(
    id="process_steps",
    name="Processus en étapes",
    category="process",
    intent=SlideIntent.SEQUENCE,
    description="Titre h2 + staircase_group avec 3-4 stair_items numérotés. Chaque étape: h3 percutant + p avec résultat attendu.",
    layout_type="left-fit",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {"type": "staircase_group", "children": [
            {"type": "stair_item", "children": [
                {"type": "h3", "children": [{"text": "{step_title}"}]},
                {"type": "p", "children": [{"text": "{step_desc}"}]},
            ]},
        ] * 4},
    ],
    constraints={"min_items": 3, "max_items": 5, "max_blocks": 2},
))

_register(SlideTemplate(
    id="roadmap",
    name="Roadmap / Feuille de route",
    category="process",
    intent=SlideIntent.SEQUENCE,
    description="Titre h2 + timeline_group variant pills avec phases datées. 3-5 items.",
    layout_type="accent-top",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {"type": "timeline_group", "variant": "pills", "children": [
            {"type": "timeline_item", "children": [
                {"type": "h3", "children": [{"text": "{phase}"}]},
                {"type": "p", "children": [{"text": "{phase_desc}"}]},
            ]},
        ] * 4},
    ],
    constraints={"min_items": 3, "max_items": 6, "max_blocks": 2},
    recommended_variants=("pills", "minimal-boxes"),
))

# ── PEOPLE ──

_register(SlideTemplate(
    id="team",
    name="Équipe / Profils",
    category="content",
    intent=SlideIntent.SHOWCASE_TEAM,
    description="Titre h2 + image_gallery_group variant team avec 2-4 profils. Chaque profil: image, nom, rôle.",
    layout_type="vertical",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {"type": "image_gallery_group", "variant": "team", "children": [
            {"type": "image_gallery_item", "query": "{person_photo_query}", "children": [
                {"type": "p", "children": [{"text": "{name} — {role}"}]},
            ]},
        ] * 3},
    ],
    constraints={"min_items": 2, "max_items": 4, "max_blocks": 2},
))

# ── QUOTES ──

_register(SlideTemplate(
    id="quote",
    name="Citation / Insight",
    category="content",
    intent=SlideIntent.QUOTE_INSIGHT,
    description="Citation mise en avant (quote, variant large). 1-2 phrases max + attribution. Layout background.",
    layout_type="background",
    structure=[
        {"type": "quote", "variant": "large", "children": [
            {"type": "p", "children": [{"text": "{quote_text}"}]},
            {"type": "p", "children": [{"text": "— {attribution}"}]},
        ]},
    ],
    constraints={"max_words_quote": 30, "max_blocks": 1},
    recommended_variants=("large", "side-icon"),
))

# ── FEATURES ──

_register(SlideTemplate(
    id="features_icons",
    name="Features / Bénéfices avec icônes",
    category="content",
    intent=SlideIntent.PERSUADE,
    description="Titre h2 + icon_list avec 3-4 icon_list_items. Chaque item: icône en cercle coloré + titre percutant h3 + description avec chiffre/résultat concret. Rendu visuel riche type page de features SaaS.",
    layout_type="right-fit",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {"type": "icon_list", "children": [
            {"type": "icon_list_item", "children": [
                {"type": "icon", "query": "{icon_query}"},
                {"type": "h3", "children": [{"text": "{feature_title}"}]},
                {"type": "p", "children": [{"text": "{feature_desc}"}]},
            ]},
        ] * 3},
    ],
    constraints={"min_items": 3, "max_items": 4, "max_words_per_item": 15, "max_blocks": 2},
    icon_slots=4,
    recommended_variants=("default",),
))

# ── CHART ──

_register(SlideTemplate(
    id="chart",
    name="Graphique avec contexte",
    category="data",
    intent=SlideIntent.INFORM,
    description="Titre h2 percutant + graphique (chart-bar, chart-line, chart-pie ou chart-donut) avec 4-6 data points RÉALISTES et cohérents + paragraphe d'insight avec le chiffre clé à retenir. Choisis le type de chart adapté au sujet (donut pour répartition, bar pour comparaison, line pour évolution).",
    layout_type="right-fit",
    structure=[
        {"type": "h2", "children": [{"text": "{title}"}]},
        {"type": "chart-donut", "data": [
            {"label": "{category_1}", "value": 45},
            {"label": "{category_2}", "value": 28},
            {"label": "{category_3}", "value": 18},
            {"label": "{category_4}", "value": 9},
        ]},
        {"type": "p", "children": [{"text": "{insight_key_number}"}]},
    ],
    constraints={"max_data_points": 6, "max_blocks": 3},
))

# ── CLOSING ──

_register(SlideTemplate(
    id="takeaway",
    name="Points clés à retenir",
    category="closing",
    intent=SlideIntent.SUMMARIZE,
    description="Titre h2 'À retenir' + bullet_group variant arrow avec 3-4 points synthétiques.",
    layout_type="accent-top",
    structure=[
        {"type": "h2", "children": [{"text": "À retenir"}]},
        {"type": "bullet_group", "variant": "arrow", "children": [
            {"type": "bullet_item", "children": [
                {"type": "h3", "children": [{"text": "{point}"}]},
                {"type": "p", "children": [{"text": ""}]},
            ]},
        ] * 3},
    ],
    constraints={"min_items": 3, "max_items": 4, "max_blocks": 2},
    recommended_variants=("arrow", "numbered"),
))


# ── Template suggestion ──


# Keyword → (template_id, base_confidence)
_KEYWORD_MAP: list[tuple[list[str], str, float, SlideIntent]] = [
    # Data / Metrics
    (
        ["chiffre", "kpi", "métrique", "résultat", "performance", "stat", "indicateur", "mesure"],
        "kpi_3", 0.85, SlideIntent.HIGHLIGHT_METRIC,
    ),
    (
        ["%", "pourcentage", "taux", "score", "nombre clé", "big number"],
        "big_number", 0.75, SlideIntent.HIGHLIGHT_METRIC,
    ),
    # Process / Timeline
    (
        ["timeline", "chronologie", "planning", "calendrier", "historique", "dates"],
        "timeline", 0.85, SlideIntent.SEQUENCE,
    ),
    (
        ["roadmap", "feuille de route", "plan d'action", "jalons", "phases"],
        "roadmap", 0.80, SlideIntent.SEQUENCE,
    ),
    (
        ["processus", "étape", "workflow", "méthode", "procédure", "démarche", "pipeline"],
        "process_steps", 0.80, SlideIntent.SEQUENCE,
    ),
    # Comparison
    (
        ["comparaison", "versus", " vs ", "comparer", "différence", "alternative"],
        "comparison_2col", 0.85, SlideIntent.COMPARE,
    ),
    (
        ["avantage", "inconvénient", "pour", "contre", "bénéfice", "risque", "pros", "cons"],
        "pros_cons", 0.80, SlideIntent.COMPARE,
    ),
    (
        ["avant", "après", "transformation", "évolution", "migration"],
        "before_after", 0.75, SlideIntent.COMPARE,
    ),
    # People
    (
        ["équipe", "team", "profil", "membre", "expert", "fondateur", "co-fondateur"],
        "team", 0.90, SlideIntent.SHOWCASE_TEAM,
    ),
    # Quote
    (
        ["citation", "témoignage", "insight", "verbatim", "avis client"],
        "quote", 0.85, SlideIntent.QUOTE_INSIGHT,
    ),
    # Chart
    (
        ["graphique", "évolution", "tendance", "courbe", "répartition", "chart", "données"],
        "chart", 0.75, SlideIntent.INFORM,
    ),
    # Features
    (
        ["fonctionnalité", "feature", "bénéfice", "atout", "offre", "service", "solution"],
        "features_icons", 0.70, SlideIntent.PERSUADE,
    ),
]


def suggest_template(
    outline_item: dict,
    slide_index: int,
    total_slides: int,
) -> TemplateSuggestion:
    """Suggest the best template based on outline content and position.

    Returns a TemplateSuggestion with confidence score and reason.
    """
    title = outline_item.get("title", "")
    bullets = outline_item.get("bullets", [])
    combined = f"{title} {' '.join(bullets)}".lower()

    # Position-based overrides
    if slide_index == 0:
        return TemplateSuggestion(
            template_id="cover",
            confidence=0.95,
            reason="position: first slide → cover",
            intent=SlideIntent.OPEN,
        )

    if slide_index == total_slides - 1:
        # Check if the last slide content suggests a summary
        summary_kw = ["conclusion", "résumé", "retenir", "synthèse", "recap", "takeaway", "next step"]
        if any(kw in combined for kw in summary_kw):
            return TemplateSuggestion(
                template_id="takeaway",
                confidence=0.90,
                reason=f"position: last slide + keywords match summary",
                intent=SlideIntent.CLOSE,
            )
        return TemplateSuggestion(
            template_id="takeaway",
            confidence=0.70,
            reason="position: last slide (default takeaway)",
            intent=SlideIntent.CLOSE,
        )

    # Keyword-based scoring
    best_id = "cards_3"
    best_confidence = 0.0
    best_reason = "default: no keyword match → cards_3"
    best_intent = SlideIntent.INFORM

    for keywords, template_id, base_conf, intent in _KEYWORD_MAP:
        match_count = sum(1 for kw in keywords if kw in combined)
        if match_count > 0:
            # More keyword matches → higher confidence
            confidence = min(base_conf + (match_count - 1) * 0.05, 0.95)
            if confidence > best_confidence:
                matched = [kw for kw in keywords if kw in combined]
                best_id = template_id
                best_confidence = confidence
                best_reason = f"keywords: {', '.join(matched[:3])}"
                best_intent = intent

    # Fallback confidence for cards_3
    if best_confidence == 0.0:
        bullet_count = len(bullets)
        if bullet_count >= 4:
            best_id = "cards_4"
            best_confidence = 0.50
            best_reason = f"default: {bullet_count} bullets → cards_4"
        else:
            best_confidence = 0.45
            best_reason = f"default: {bullet_count} bullets → cards_3"

    return TemplateSuggestion(
        template_id=best_id,
        confidence=best_confidence,
        reason=best_reason,
        intent=best_intent,
    )


# ── Prompt helpers ──


def get_template(template_id: str) -> SlideTemplate | None:
    """Get a template by ID."""
    return TEMPLATE_CATALOG.get(template_id)


def get_template_hint_for_prompt(suggestion: TemplateSuggestion) -> str:
    """Generate a directive template hint for the LLM prompt.

    Includes the JSON skeleton so the LLM follows the exact structure.
    """
    import json as _json

    template = TEMPLATE_CATALOG.get(suggestion.template_id)
    if not template:
        return ""

    # Pick the best variant (first recommended, or first in structure)
    best_variant = ""
    if template.recommended_variants:
        best_variant = template.recommended_variants[0]

    # Include the JSON skeleton so the LLM follows the structure
    skeleton_json = _json.dumps(template.structure, ensure_ascii=False, indent=2)

    # Map layout to richer alternatives
    layout = template.layout_type
    if layout == "vertical":
        layout_instruction = 'Utilise "left-fit" ou "right-fit" pour un rendu premium (pas "vertical" seul).'
    elif layout == "accent-top":
        layout_instruction = f'Utilise "{layout}". Pas besoin de root_image (la bande colorée suffit).'
    elif layout == "background":
        layout_instruction = f'Utilise "{layout}" avec une root_image immersive et descriptive.'
    else:
        layout_instruction = f'Utilise "{layout}" avec une root_image pertinente.'

    # Variant-specific design guidance
    variant_guidance = ""
    if best_variant == "sideline":
        variant_guidance = 'Variant "sideline" : chaque carte a un bord gauche coloré (accent). PAS d\'icône dans ce mode. Focus sur titre h3 percutant + description avec donnée chiffrée.'
    elif best_variant == "icons":
        variant_guidance = 'Variant "icons" : chaque box_item COMMENCE par {{"type":"icon","query":"terme"}}. L\'icône apparaît en cercle coloré. Choisis des icônes SIGNIFICATIVES (pas génériques).'
    elif best_variant == "bar":
        variant_guidance = 'Variant "bar" : chaque stats_item affiche une barre de progression. Les values doivent être des pourcentages ou des chiffres comparatifs percutants.'
    elif best_variant == "circle":
        variant_guidance = 'Variant "circle" : chaque stats_item affiche une jauge circulaire. Idéal pour des pourcentages (ex: "94%", "+67%").'
    elif best_variant == "pills":
        variant_guidance = 'Variant "pills" : chaque étape est un badge coloré numéroté. Les titres h3 doivent être datés ou numérotés (ex: "Q1 — Fondations", "Étape 1").'

    return f"""\
TEMPLATE : {template.id}
- Intention : {suggestion.intent.value}
- {template.description}
- Variant à utiliser : "{best_variant}" (OBLIGATOIRE si applicable)
- {variant_guidance}
- {layout_instruction}
- Contraintes : {template.constraints}

STRUCTURE JSON À SUIVRE — remplace CHAQUE placeholder par du contenu UNIQUE et PERCUTANT :
```json
{skeleton_json}
```

CONSIGNES DE QUALITÉ :
- Chaque item doit avoir un contenu DIFFÉRENT et SPÉCIFIQUE (pas de remplissage générique).
- Inclus des CHIFFRES concrets et réalistes dans les descriptions (%, €, x multiplier, comparaisons vs période précédente).
- Les titres h3 doivent être COURTS et IMPACTANTS (3-5 mots max).
- Les descriptions doivent apporter un INSIGHT (donnée, résultat, comparaison) — jamais du texte vague.
- La root_image query doit décrire une photo CONTEXTUELLE et PROFESSIONNELLE liée au sujet (10+ mots). Ex: "modern office team meeting with whiteboard presentation" PAS "abstract gradient shapes".
- Ne copie PAS les exemples du system prompt — crée du contenu ORIGINAL adapté au sujet."""


def get_safe_fallback(outline_item: dict, slide_index: int, total_slides: int) -> dict:
    """Premium safe fallback using a known template.

    Never returns a bare bullet_group — always a proper template.
    """
    suggestion = suggest_template(outline_item, slide_index, total_slides)
    template = TEMPLATE_CATALOG.get(suggestion.template_id)

    title = outline_item.get("title", f"Slide {slide_index + 1}")
    bullets = outline_item.get("bullets", ["Point clé 1", "Point clé 2", "Point clé 3"])

    if not template or suggestion.template_id == "cover":
        if slide_index == 0:
            return {
                "layout_type": "background",
                "bg_color": None,
                "root_image": {"query": f"professional abstract background for {title}", "layout_type": "background"},
                "content_json": [
                    {"type": "h1", "children": [{"text": title}]},
                    {"type": "p", "children": [{"text": bullets[0] if bullets else ""}]},
                ],
            }

    if suggestion.template_id == "takeaway":
        return {
            "layout_type": "accent-top",
            "bg_color": None,
            "root_image": None,
            "content_json": [
                {"type": "h2", "children": [{"text": "À retenir"}]},
                {
                    "type": "bullet_group",
                    "variant": "arrow",
                    "children": [
                        {
                            "type": "bullet_item",
                            "children": [
                                {"type": "h3", "children": [{"text": b}]},
                                {"type": "p", "children": [{"text": ""}]},
                            ],
                        }
                        for b in bullets[:4]
                    ],
                },
            ],
        }

    if suggestion.template_id in ("kpi_3", "big_number"):
        return {
            "layout_type": "accent-top",
            "bg_color": None,
            "root_image": None,
            "content_json": [
                {"type": "h2", "children": [{"text": title}]},
                {
                    "type": "stats_group",
                    "variant": "default",
                    "children": [
                        {
                            "type": "stats_item",
                            "value": "—",
                            "children": [
                                {"type": "h3", "children": [{"text": b}]},
                                {"type": "p", "children": [{"text": ""}]},
                            ],
                        }
                        for b in bullets[:3]
                    ],
                },
            ],
        }

    # Default: cards_3 with icons (premium fallback)
    return {
        "layout_type": template.layout_type if template else "vertical",
        "bg_color": None,
        "root_image": None,
        "content_json": [
            {"type": "h2", "children": [{"text": title}]},
            {
                "type": "box_group",
                "variant": "icons",
                "children": [
                    {
                        "type": "box_item",
                        "children": [
                            {"type": "icon", "query": b.split()[0] if b else "star"},
                            {"type": "h3", "children": [{"text": b}]},
                            {"type": "p", "children": [{"text": ""}]},
                        ],
                    }
                    for b in bullets[:4]
                ],
            },
        ],
    }
