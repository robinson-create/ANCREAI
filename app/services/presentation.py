"""Presentation service — CRUD, AI generation (outline + slides), export orchestration."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any
from uuid import UUID

from openai import AsyncOpenAI
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.presentation import (
    Presentation,
    PresentationAsset,
    PresentationExport,
    PresentationGenerationRun,
    PresentationSlide,
    PresentationStatus,
    PresentationTheme,
    AssetStatus,
    RunPurpose,
)
from app.schemas.presentation import (
    ExportRequest,
    GenerateSlidesRequest,
    OutlineItem,
    PresentationCreate,
    PresentationUpdate,
    RegenerateSlideRequest,
    SlideContent,
    SlideUpdate,
    ThemeCreate,
    ThemeData,
)
from app.services.presentation_briefs import (
    DeckContext,
    NarrativeRole,
    SlideBlock,
    SlideBrief,
)
from app.services.presentation_design_normalizer import normalize_slide
from app.services.presentation_icons import (
    get_icon_names_for_prompt,
    get_icon_policy_for_prompt,
    suggest_icons_for_content,
)
from app.services.presentation_xml_parser import XMLSlideParser
from app.services.presentation_outline_generator import generate_outline as _generate_outline_v2
from app.services.presentation_prompts import (
    CURRENT_CONTENT_SECTION,
    DESIGN_CONSTRAINTS_SECTION,
    ICON_POLICY_SECTION,
    OUTLINE_CONTEXT_SECTION,
    REPAIR_SYSTEM_PROMPT,
    REPAIR_USER_TEMPLATE,
    SLIDE_BRIEF_SYSTEM_PROMPT,
    SLIDE_BRIEF_USER_TEMPLATE,
    SLIDE_SYSTEM_PROMPT,
    SLIDES_BATCH_SYSTEM_PROMPT,
    SPLIT_SYSTEM_PROMPT,
    TEMPLATE_HINT_SECTION,
    THEME_CONTEXT_SECTION,
    USER_INSTRUCTION_SECTION,
    XML_SLIDES_SYSTEM_PROMPT,
    XML_SINGLE_SLIDE_PROMPT,
)
from app.services.presentation_slide_generator import generate_slide_xml as _generate_slide_xml_v2
from app.services.presentation_slide_planner import build_deck_plan as _build_deck_plan_v2
from app.services.presentation_splitter import maybe_split_brief
from app.services.presentation_template_registry import (
    TemplateDefinition,
    get_template_def,
)
from app.services.presentation_template_selector import select_template as select_template_deterministic
from app.services.presentation_templates import (
    SlideIntent,
    TemplateSuggestion,
    get_template,
    get_template_hint_for_prompt,
    get_safe_fallback,
    suggest_template,
)
from app.services.retrieval import RetrievalService, RetrievedChunk

settings = get_settings()
logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = 2
_SLIDE_MAX_TOKENS = 4096


# ── Slide metrics instrumentation (Fix 6) ──


def _estimate_rendered_chars(composed: dict) -> int:
    """Estimate total text chars in the composed slide."""
    total = 0
    for key in ("header", "title", "statement", "subtitle", "context", "quote_text", "attribution"):
        if key in composed and isinstance(composed[key], str):
            total += len(composed[key])
    for key in ("cards", "steps", "kpis", "sides", "points"):
        if key in composed and isinstance(composed[key], list):
            for item in composed[key]:
                if isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, str):
                            total += len(v)
    return total


def _log_slide_metrics(
    detailed_content: str,
    brief: SlideBrief,
    template: TemplateDefinition,
    composed: dict,
) -> None:
    """Log per-slide compression metrics for diagnostics."""
    source_chars = len(detailed_content) if detailed_content else 0
    block_total = sum(len(b.body) for b in brief.blocks)
    body_slots = [s for s in template.slots if s.max_body_chars > 0]
    template_capacity = sum(s.max_body_chars for s in body_slots[:len(brief.blocks)])
    rendered_chars = _estimate_rendered_chars(composed)
    ratio = rendered_chars / source_chars if source_chars > 0 else 1.0
    logger.info(
        "SLIDE_METRICS | source=%d | blocks=%d | block_chars=%d | "
        "template=%s | capacity=%d | rendered=%d | compression=%.0f%%",
        source_chars, len(brief.blocks), block_total,
        template.id, template_capacity, rendered_chars, ratio * 100,
    )


# ── Deterministic brief-building helpers ──


def _infer_narrative_role(
    title: str,
    bullets: list[str],
    slide_index: int,
    total_slides: int,
) -> NarrativeRole:
    """Infer narrative role from position and content keywords."""
    if slide_index == 0:
        return NarrativeRole.COVER
    if slide_index == total_slides - 1:
        return NarrativeRole.TAKEAWAY

    combined = f"{title} {' '.join(bullets)}".lower()

    _ROLE_KEYWORDS: dict[NarrativeRole, list[str]] = {
        NarrativeRole.TEAM: [
            "équipe", "team", "profil", "membre", "fondateur", "co-fondateur",
            "collaborateur", "directeur", "responsable", "cto", "ceo", "coo",
        ],
        NarrativeRole.COMPARISON: [
            "comparaison", "versus", " vs ", "comparer", "avant/après",
            "pour et contre", "avantage", "inconvénient",
        ],
        NarrativeRole.PROOF: [
            "chiffre", "kpi", "résultat", "performance", "statistique",
            "métrique", "roi", "croissance", "impact",
        ],
        NarrativeRole.PROCESS: [
            "processus", "étape", "workflow", "méthode", "pipeline",
            "timeline", "chronologie", "déroulement",
        ],
        NarrativeRole.PLAN: [
            "roadmap", "plan", "feuille de route", "jalon", "phase",
            "planning", "stratégie", "objectif",
        ],
        NarrativeRole.PROBLEM: [
            "problème", "défi", "challenge", "obstacle", "risque",
            "enjeu", "difficulté", "limite",
        ],
        NarrativeRole.CONTEXT: [
            "contexte", "marché", "situation", "environnement", "secteur",
            "introduction", "présentation",
        ],
        NarrativeRole.HOOK: [
            "accroche", "saviez-vous", "question", "pourquoi",
        ],
    }

    # Check for percentage/number patterns → PROOF
    if re.search(r'\d+[%€$]|\d+\s*%|roi\b|\+\d+', combined):
        return NarrativeRole.PROOF

    for role, keywords in _ROLE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return role

    # Default for middle slides
    return NarrativeRole.INSIGHT


# ── Structured content parser (Fix 1) ──

_CONTENT_STRUCTURE_PATTERNS = [
    # "Bloc 1 - Title", "Block 2 — Title", "Section 3 : Title"
    re.compile(r'(?:^|\n)\s*(?:bloc|block|section|partie)\s*\d+\s*[\-–—:]\s*(.+)', re.IGNORECASE),
    # "1. Title" ou "1) Title" at line start
    re.compile(r'(?:^|\n)\s*\d+[.)]\s+(.+)'),
    # "- Title:" (first-level dash with colon = section header)
    re.compile(r'(?:^|\n)\s*[-•]\s+"?([^":\n]+)"?\s*:'),
]

# Guard-rails against false positives
_MIN_SECTION_BODY_CHARS = 80
_MIN_TOTAL_PARSED_CHARS = 300
_MIN_COVERAGE_RATIO = 0.5


def _parse_structured_content(text: str) -> list[tuple[str, str]]:
    """Parse structured content into (title, body) pairs with false-positive guards."""
    if not text or len(text) < 200:
        return []

    for pattern in _CONTENT_STRUCTURE_PATTERNS:
        matches = list(pattern.finditer(text))
        if len(matches) < 2:
            continue

        sections: list[tuple[str, str]] = []
        total_parsed_chars = 0
        for idx, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            total_parsed_chars += len(body)
            sections.append((title, body))

        # Guard 1: at least 2 sections with substantial body
        substantial = [s for s in sections if len(s[1]) >= _MIN_SECTION_BODY_CHARS]
        if len(substantial) < 2:
            continue

        # Guard 2: total parsed content is significant
        if total_parsed_chars < _MIN_TOTAL_PARSED_CHARS:
            continue

        # Guard 3: sections cover enough of the source text
        coverage = total_parsed_chars / len(text)
        if coverage < _MIN_COVERAGE_RATIO:
            continue

        logger.info("Parsed %d structured sections (coverage=%.0f%%)", len(sections), coverage * 100)
        return sections

    return []


# Safety cap for block body — real truncation happens in content_rewriter
BLOCK_BODY_MAX_RAW = 800


def _build_blocks_from_outline(
    bullets: list[str],
    detailed_content: str,
    role: NarrativeRole,
) -> list[SlideBlock]:
    """Build SlideBlocks from outline data, preserving all content."""
    # Determine block kind from role
    _ROLE_TO_KIND: dict[NarrativeRole, str] = {
        NarrativeRole.PROCESS: "step",
        NarrativeRole.PLAN: "step",
        NarrativeRole.PROOF: "metric",
        NarrativeRole.COMPARISON: "comparison_side",
        NarrativeRole.TEAM: "team_member",
    }
    kind = _ROLE_TO_KIND.get(role, "point")

    blocks: list[SlideBlock] = []

    # Priority 1: parse structured content from detailed_content (Fix 1)
    if detailed_content and len(detailed_content) > 200:
        parsed = _parse_structured_content(detailed_content)
        if parsed:
            for i, (title, body) in enumerate(parsed[:8]):
                blocks.append(SlideBlock(
                    kind=kind,
                    priority=min(i + 1, 3),
                    title=title[:80],
                    body=body[:BLOCK_BODY_MAX_RAW],
                    can_pair_with_icon=True,
                ))
            return blocks

    # Priority 2: distribute detailed_content among bullets
    if detailed_content and len(detailed_content) > 100 and bullets:
        paragraphs = [p.strip() for p in detailed_content.split("\n") if p.strip()]

        if len(paragraphs) >= len(bullets):
            chunk_size = max(1, len(paragraphs) // len(bullets))
            for i, bullet in enumerate(bullets):
                start = i * chunk_size
                end = (i + 1) * chunk_size if i < len(bullets) - 1 else len(paragraphs)
                body = "\n".join(paragraphs[start:end])[:BLOCK_BODY_MAX_RAW]
                blocks.append(SlideBlock(
                    kind=kind,
                    priority=min(i + 1, 3),
                    title=bullet,
                    body=body,
                    can_pair_with_icon=True,
                ))
        else:
            chunk_size = len(detailed_content) // len(bullets) if bullets else len(detailed_content)
            for i, bullet in enumerate(bullets):
                start = i * chunk_size
                end = (i + 1) * chunk_size if i < len(bullets) - 1 else len(detailed_content)
                body = detailed_content[start:end].strip()[:BLOCK_BODY_MAX_RAW]
                blocks.append(SlideBlock(
                    kind=kind,
                    priority=min(i + 1, 3),
                    title=bullet,
                    body=body,
                    can_pair_with_icon=True,
                ))
    elif detailed_content and len(detailed_content) > 100 and not bullets:
        paragraphs = [p.strip() for p in detailed_content.split("\n") if p.strip()]
        for i, para in enumerate(paragraphs[:6]):
            words = para.split()
            block_title = " ".join(words[:6]) if len(words) > 6 else para
            block_body = " ".join(words[6:])[:BLOCK_BODY_MAX_RAW] if len(words) > 6 else ""
            blocks.append(SlideBlock(
                kind=kind,
                priority=min(i + 1, 3),
                title=block_title,
                body=block_body,
                can_pair_with_icon=True,
            ))
    else:
        for i, bullet in enumerate(bullets):
            blocks.append(SlideBlock(
                kind=kind,
                priority=min(i + 1, 3),
                title=bullet,
                body="",
                can_pair_with_icon=True,
            ))

    return blocks


# ── Prompt section extractor — bypass LLM summarization ──

# Patterns that detect structured slide sections in user prompts
_SLIDE_SECTION_PATTERNS = [
    # "SLIDE 1", "Slide 1 –", "SLIDE 1:", "slide 1 -"
    re.compile(r'(?:^|\n)\s*(?:slide|diapo|diapositive)\s*(\d+)\s*[\-–—:.]', re.IGNORECASE),
    # "1.", "1)", "1 -" at line start (numbered list)
    re.compile(r'(?:^|\n)\s*(\d+)\s*[.)]\s*[\-–—]?\s*(?=[A-ZÀ-Ü])'),
]


def _extract_sections_from_prompt(prompt: str, expected_count: int) -> list[str] | None:
    """Try to extract per-slide text sections from a structured user prompt.

    Returns a list of raw text sections (one per slide), or None if the prompt
    is not structured enough to extract sections.
    """
    if not prompt or len(prompt) < 100:
        return None

    # Try each pattern
    for pattern in _SLIDE_SECTION_PATTERNS:
        matches = list(pattern.finditer(prompt))
        if len(matches) >= expected_count - 1:  # Allow for intro text before section 1
            sections: list[str] = []
            for idx, match in enumerate(matches):
                start = match.start()
                end = matches[idx + 1].start() if idx + 1 < len(matches) else len(prompt)
                section_text = prompt[start:end].strip()
                sections.append(section_text)
            if sections:
                return sections

    # Fallback: try splitting by double newlines if prompt has enough structure
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', prompt) if p.strip()]
    # Skip the intro paragraph (general instructions)
    if len(paragraphs) >= expected_count + 1:
        # First paragraph is likely the general intro, rest are slides
        return paragraphs[1:expected_count + 1]
    if len(paragraphs) == expected_count:
        return paragraphs

    return None




# ── Section split helpers (replaces outline LLM) ──


def _normalize_text(text: str) -> str:
    """Normalize text for marker matching: lowercase, strip, simplify punctuation."""
    import unicodedata
    t = text.strip().lower()
    # Normalize unicode dashes/quotes to ASCII
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t)
    return t


def _find_marker_position(prompt: str, marker: str) -> int | None:
    """Find marker position in prompt using hierarchical strategy.

    1. Exact match
    2. Normalized exact match (trim, lowercase, simplified punctuation)
    3. Unique substring match
    4. Fuzzy match (score >= 80%)
    5. None if not found or ambiguous
    """
    if not marker or not prompt:
        return None

    # Strategy 1: Exact match
    pos = prompt.find(marker)
    if pos >= 0:
        return pos

    # Strategy 2: Normalized match
    norm_prompt = _normalize_text(prompt)
    norm_marker = _normalize_text(marker)
    if norm_marker:
        pos = norm_prompt.find(norm_marker)
        if pos >= 0:
            # Map back to original prompt position (approximate)
            # Find the closest match in original around that position
            window = min(len(norm_marker) + 50, len(prompt))
            search_start = max(0, pos - 20)
            search_end = min(len(prompt), pos + window)
            # Try to find something close in the original
            chunk = prompt[search_start:search_end].lower()
            sub_pos = chunk.find(norm_marker)
            if sub_pos >= 0:
                return search_start + sub_pos
            # If exact normalized not found in window, use approximate position
            return pos

    # Strategy 3: Unique substring match (first 40 chars of marker)
    short_marker = norm_marker[:40] if len(norm_marker) > 40 else norm_marker
    if short_marker:
        all_positions = []
        search_lower = prompt.lower()
        start = 0
        while True:
            pos = search_lower.find(short_marker, start)
            if pos < 0:
                break
            all_positions.append(pos)
            start = pos + 1
        if len(all_positions) == 1:
            return all_positions[0]

    # Strategy 4: Fuzzy match — sliding window
    marker_words = norm_marker.split()
    if len(marker_words) >= 3:
        # Try to find a window with enough matching words
        prompt_words = prompt.lower().split()
        best_pos = None
        best_score = 0.0
        marker_set = set(marker_words)

        for wi in range(len(prompt_words) - len(marker_words) + 1):
            window_words = prompt_words[wi:wi + len(marker_words)]
            window_set = set(window_words)
            overlap = len(marker_set & window_set) / len(marker_set)
            if overlap > best_score and overlap >= 0.80:
                best_score = overlap
                # Convert word index to char position
                best_pos = len(' '.join(prompt_words[:wi]))
                if wi > 0:
                    best_pos += 1  # account for the space before

        if best_pos is not None:
            return best_pos

    return None


def _resolve_sections_from_markers(
    prompt: str,
    sections_data: list[dict],
) -> list[dict] | None:
    """Resolve LLM markers to exact text ranges in the original prompt.

    Returns list of {title, raw_text} or None if resolution fails.
    A partially resolved split is worse than no split — reject if ANY section fails.
    """
    if not sections_data:
        return None

    positions: list[tuple[int, int, str]] = []  # (start, end, title)

    for i, section in enumerate(sections_data):
        title = section.get("title", f"Section {i + 1}")
        start_marker = section.get("start_marker", "")
        end_marker = section.get("end_marker", "")

        # Resolve start position
        start_pos = _find_marker_position(prompt, start_marker)
        if start_pos is None:
            logger.warning(
                "Split marker resolution failed: start_marker not found for section '%s': '%s'",
                title, start_marker[:50],
            )
            return None  # REJECT ENTIRE SPLIT

        # Resolve end position
        end_pos = _find_marker_position(prompt, end_marker)
        if end_pos is None:
            logger.warning(
                "Split marker resolution failed: end_marker not found for section '%s': '%s'",
                title, end_marker[:50],
            )
            return None  # REJECT ENTIRE SPLIT

        # End position should be after the end marker text
        end_pos = end_pos + len(end_marker)

        positions.append((start_pos, end_pos, title))

    # Validate order: each section start must be >= previous section start
    for i in range(1, len(positions)):
        if positions[i][0] < positions[i - 1][0]:
            logger.warning("Split marker resolution failed: sections out of order at index %d", i)
            return None  # REJECT

    # Validate no zero-length sections
    for i, (start, end, title) in enumerate(positions):
        if end <= start:
            logger.warning("Split marker resolution failed: zero-length section '%s'", title)
            return None  # REJECT

    # Build sections — use start of next section as end of current (avoids gaps)
    result: list[dict] = []
    for i, (start, end, title) in enumerate(positions):
        # Extend to next section start to avoid gaps
        actual_end = positions[i + 1][0] if i + 1 < len(positions) else len(prompt)
        raw_text = prompt[start:actual_end].strip()

        if not raw_text:
            logger.warning("Split marker resolution failed: empty raw_text for section '%s'", title)
            return None  # REJECT

        result.append({"title": title, "raw_text": raw_text})

    return result


def _validate_sections(
    sections: list[dict],
    original_prompt: str,
) -> list[dict] | None:
    """Validate split quality. Returns sections or None if invalid.

    Checks:
    1. Coverage: sum(raw_text lengths) >= 70% of prompt length
    2. Balance: no middle section > 2.5x average (first/last exempt)
    3. Balance: no middle section < 0.2x average (first/last exempt)
    4. Min content: every section has at least 50 characters
    5. No duplicates: no two sections have identical raw_text
    """
    if not sections or len(sections) < 2:
        return None

    lengths = [len(s.get("raw_text", "")) for s in sections]
    total_raw = sum(lengths)
    prompt_len = len(original_prompt)

    # Check 1: Coverage
    if prompt_len > 0:
        coverage = total_raw / prompt_len
        if coverage < 0.70:
            logger.warning("Section validation failed: coverage %.0f%% < 70%%", coverage * 100)
            return None

    # Check 4: Min content
    for i, section in enumerate(sections):
        if lengths[i] < 50:
            logger.warning(
                "Section validation failed: section '%s' has only %d chars",
                section.get("title", "?"), lengths[i],
            )
            return None

    # Check 2 & 3: Balance (exclude first and last sections)
    if len(sections) > 2:
        avg_len = total_raw / len(sections) if sections else 1
        for i in range(1, len(sections) - 1):
            ratio = lengths[i] / avg_len if avg_len > 0 else 0
            if ratio > 2.5:
                logger.warning(
                    "Section validation failed: section '%s' is %.1fx average (too large)",
                    sections[i].get("title", "?"), ratio,
                )
                return None
            if ratio < 0.2:
                logger.warning(
                    "Section validation failed: section '%s' is %.1fx average (too small)",
                    sections[i].get("title", "?"), ratio,
                )
                return None

    # Check 5: No duplicates
    texts = [s.get("raw_text", "") for s in sections]
    if len(set(texts)) != len(texts):
        logger.warning("Section validation failed: duplicate sections detected")
        return None

    logger.info(
        "Section validation passed: %d sections, coverage=%.0f%%, avg=%d chars",
        len(sections), (total_raw / prompt_len * 100) if prompt_len > 0 else 100,
        total_raw // len(sections),
    )
    return sections


def _infer_section_roles(sections: list[dict]) -> list[dict]:
    """Infer narrative roles for each section based on position, title, and content.

    Cover/takeaway are strong preferences, not absolutes.
    Role is NEVER determined by the LLM — always inferred by code.
    """
    total = len(sections)
    for i, section in enumerate(sections):
        raw_text = section.get("raw_text", "")
        title = section.get("title", "")

        role = _infer_narrative_role(
            title=title,
            bullets=[],
            slide_index=i,
            total_slides=total,
        )

        # Override: don't force COVER on dense analytical first section
        if i == 0 and len(raw_text) > 300:
            keywords_check = raw_text[:200].lower()
            if any(kw in keywords_check for kw in ["contexte", "marché", "problème", "enjeu", "situation"]):
                role = _infer_narrative_role(title, [], 1, total)

        # Override: don't force TAKEAWAY on dense last section
        if i == total - 1 and len(raw_text) > 500:
            role = _infer_narrative_role(title, [], max(0, total - 2), total)

        section["role"] = role.value

    return sections


def _fallback_paragraph_split(prompt: str, slide_count: int) -> list[dict]:
    """Split prompt into N roughly equal sections by paragraphs.

    Last-resort fallback when deterministic parsing and LLM markers both fail.
    """
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', prompt) if p.strip()]

    if not paragraphs:
        # Single block of text — split by sentences
        sentences = re.split(r'(?<=[.!?])\s+', prompt)
        paragraphs = sentences if sentences else [prompt]

    if len(paragraphs) < slide_count:
        # Fewer paragraphs than slides — try splitting by sentences
        all_sentences = []
        for para in paragraphs:
            sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', para) if s.strip()]
            all_sentences.extend(sents if sents else [para])

        if len(all_sentences) >= slide_count:
            # Enough sentences — distribute across sections
            sections_out: list[dict] = []
            chunk_size = max(1, len(all_sentences) // slide_count)
            for i in range(slide_count):
                start = i * chunk_size
                end = (i + 1) * chunk_size if i < slide_count - 1 else len(all_sentences)
                text = " ".join(all_sentences[start:end])
                words = text.split()
                title = " ".join(words[:6]) if len(words) > 6 else text[:80]
                sections_out.append({"title": title.strip("- –—:1234567890.)"), "raw_text": text})
            return sections_out

        # Still not enough — return what we have (LLM will expand)
        result = []
        for i, para in enumerate(paragraphs):
            words = para.split()
            title = " ".join(words[:6]) if len(words) > 6 else para[:80]
            result.append({"title": title.strip("- –—:1234567890.)"), "raw_text": para})
        return result

    if len(paragraphs) == slide_count:
        # Exact match — use paragraphs as-is
        result = []
        for i, para in enumerate(paragraphs):
            words = para.split()
            title = " ".join(words[:6]) if len(words) > 6 else para[:80]
            result.append({"title": title.strip("- –—:1234567890.)"), "raw_text": para})
        return result

    # Distribute paragraphs across slide_count sections
    sections: list[dict] = []
    chunk_size = max(1, len(paragraphs) // slide_count)
    for i in range(slide_count):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < slide_count - 1 else len(paragraphs)
        text = "\n\n".join(paragraphs[start:end])
        words = text.split()
        title = " ".join(words[:6]) if len(words) > 6 else text[:80]
        sections.append({"title": title.strip("- –—:1234567890.)"), "raw_text": text})

    return sections


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to repair JSON truncated by max_tokens."""
    open_stack: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n:
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
        elif c in ('{', '['):
            open_stack.append('}' if c == '{' else ']')
        elif c in ('}', ']'):
            if open_stack:
                open_stack.pop()
        i += 1

    if not open_stack:
        return None

    trimmed = text.rstrip()
    while trimmed and trimmed[-1] not in (',', ':', '{', '[', '}', ']', '"'):
        trimmed = trimmed[:-1]
    if trimmed and trimmed[-1] == ':':
        trimmed += '""'
    elif trimmed and trimmed[-1] == ',':
        trimmed = trimmed[:-1]

    open_stack = []
    i = 0
    n2 = len(trimmed)
    while i < n2:
        c = trimmed[i]
        if c == '"':
            i += 1
            while i < n2:
                if trimmed[i] == '\\':
                    i += 2
                    continue
                if trimmed[i] == '"':
                    break
                i += 1
        elif c in ('{', '['):
            open_stack.append('}' if c == '{' else ']')
        elif c in ('}', ']'):
            if open_stack:
                open_stack.pop()
        i += 1

    suffix = "".join(reversed(open_stack))
    try:
        return json.loads(trimmed + suffix)
    except json.JSONDecodeError:
        return None


class PresentationService:
    """Service for presentation CRUD and AI-assisted slide generation."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.mistral_api_key,
            base_url="https://api.mistral.ai/v1",
        )
        self.retrieval = RetrievalService()
        self.model = settings.llm_model
        self.slide_model = settings.llm_slide_model  # Mistral Large for slide generation
        self.max_tokens = settings.llm_max_tokens

    # ══════════════════════════════════════════════
    #  CRUD — Presentations
    # ══════════════════════════════════════════════

    async def create(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        data: PresentationCreate,
    ) -> Presentation:
        pres = Presentation(
            tenant_id=tenant_id,
            title=data.title,
            prompt=data.prompt,
            settings=data.settings,
            theme_id=data.theme_id,
        )
        db.add(pres)
        await db.flush()
        await db.refresh(pres, attribute_names=["id", "tenant_id", "title", "prompt", "status", "outline", "settings", "slide_order", "version", "theme_id", "error_message", "created_at", "updated_at"])
        return pres

    async def get(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        *,
        with_slides: bool = False,
    ) -> Presentation | None:
        q = select(Presentation).where(
            Presentation.id == pres_id,
            Presentation.tenant_id == tenant_id,
        )
        if with_slides:
            q = q.options(
                selectinload(Presentation.slides),
                selectinload(Presentation.theme),
            )
        result = await db.execute(q)
        return result.scalar_one_or_none()

    async def list(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Presentation]:
        q = (
            select(Presentation)
            .where(Presentation.tenant_id == tenant_id)
            .order_by(Presentation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            q = q.where(Presentation.status == status)
        result = await db.execute(q)
        return list(result.scalars().all())

    async def update(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        data: PresentationUpdate,
    ) -> Presentation | None:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(pres, key, value)

        await db.flush()
        await db.refresh(pres)
        return pres

    async def delete(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
    ) -> bool:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return False
        await db.delete(pres)
        await db.flush()
        return True

    async def duplicate(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
    ) -> Presentation | None:
        source = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not source:
            return None

        new_pres = Presentation(
            tenant_id=tenant_id,
            title=f"{source.title} (copie)",
            prompt=source.prompt,
            status=PresentationStatus.READY.value,
            theme_id=source.theme_id,
            outline=source.outline,
            settings=source.settings,
        )
        db.add(new_pres)
        await db.flush()

        slide_ids = []
        for slide in source.slides:
            new_slide = PresentationSlide(
                presentation_id=new_pres.id,
                position=slide.position,
                layout_type=slide.layout_type,
                content_json=slide.content_json,
                root_image=slide.root_image,
                bg_color=slide.bg_color,
                speaker_notes=slide.speaker_notes,
            )
            db.add(new_slide)
            await db.flush()
            slide_ids.append(str(new_slide.id))

        new_pres.slide_order = slide_ids
        await db.flush()
        await db.refresh(new_pres)
        return new_pres

    # ══════════════════════════════════════════════
    #  CRUD — Slides
    # ══════════════════════════════════════════════

    async def get_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
    ) -> PresentationSlide | None:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return None
        result = await db.execute(
            select(PresentationSlide).where(
                PresentationSlide.id == slide_id,
                PresentationSlide.presentation_id == pres_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
        data: SlideUpdate,
    ) -> PresentationSlide | None:
        slide = await self.get_slide(db, tenant_id, pres_id, slide_id)
        if not slide:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(slide, key, value)

        # Bump presentation version
        pres = await self.get(db, tenant_id, pres_id)
        if pres:
            pres.version = pres.version + 1

        await db.flush()
        await db.refresh(slide)
        return slide

    async def add_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
    ) -> PresentationSlide | None:
        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not pres:
            return None

        position = len(pres.slides)
        slide = PresentationSlide(
            presentation_id=pres_id,
            position=position,
            layout_type="vertical",
            content_json=[
                {"type": "h2", "children": [{"text": "Nouveau slide"}]},
                {"type": "p", "children": [{"text": ""}]},
            ],
        )
        db.add(slide)
        await db.flush()

        pres.slide_order = [*pres.slide_order, str(slide.id)]
        pres.version = pres.version + 1
        await db.flush()
        await db.refresh(slide)
        return slide

    async def delete_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
    ) -> bool:
        slide = await self.get_slide(db, tenant_id, pres_id, slide_id)
        if not slide:
            return False

        pres = await self.get(db, tenant_id, pres_id)
        if pres:
            pres.slide_order = [
                sid for sid in pres.slide_order if sid != str(slide_id)
            ]
            pres.version = pres.version + 1

        await db.delete(slide)
        await db.flush()
        return True

    async def reorder_slides(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_ids: list[UUID],
    ) -> Presentation | None:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return None

        pres.slide_order = [str(sid) for sid in slide_ids]
        # Update positions to match
        for i, sid in enumerate(slide_ids):
            result = await db.execute(
                select(PresentationSlide).where(
                    PresentationSlide.id == sid,
                    PresentationSlide.presentation_id == pres_id,
                )
            )
            slide = result.scalar_one_or_none()
            if slide:
                slide.position = i

        pres.version = pres.version + 1
        await db.flush()
        await db.refresh(pres)
        return pres

    # ══════════════════════════════════════════════
    #  CRUD — Themes
    # ══════════════════════════════════════════════

    async def list_themes(
        self,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> list[PresentationTheme]:
        """List built-in themes + tenant's custom themes."""
        result = await db.execute(
            select(PresentationTheme).where(
                (PresentationTheme.tenant_id == tenant_id)
                | (PresentationTheme.is_builtin == True)  # noqa: E712
            ).order_by(PresentationTheme.is_builtin.desc(), PresentationTheme.name)
        )
        return list(result.scalars().all())

    async def create_theme(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        data: ThemeCreate,
    ) -> PresentationTheme:
        theme = PresentationTheme(
            tenant_id=tenant_id,
            name=data.name,
            is_builtin=False,
            theme_data=data.theme_data.model_dump(),
        )
        db.add(theme)
        await db.flush()
        await db.refresh(theme)
        return theme

    # ══════════════════════════════════════════════
    #  Outline update
    # ══════════════════════════════════════════════

    async def update_outline(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        outline: list[OutlineItem],
    ) -> Presentation | None:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return None
        pres.outline = [item.model_dump() for item in outline]
        pres.status = PresentationStatus.OUTLINE_READY.value
        pres.version = pres.version + 1
        await db.flush()
        await db.refresh(pres)
        return pres

    # ══════════════════════════════════════════════
    #  Prompt splitting — replaces outline LLM
    # ══════════════════════════════════════════════

    async def _split_prompt_into_sections(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        prompt: str,
        slide_count: int,
        language: str,
    ) -> list[dict]:
        """Split prompt into validated sections with metadata.

        Returns list of {title, raw_text, role, split_method}.

        Three-tier strategy:
        1. Deterministic parsing (structured prompts: "SLIDE 1 -", "1.", etc.)
        2. Lightweight LLM (returns only markers, no role, no content)
        3. Fallback paragraph split (last resort)
        """
        # Tier 1: Deterministic parsing
        det_sections = _extract_sections_from_prompt(prompt, slide_count)
        if det_sections and len(det_sections) >= slide_count - 1:
            result = []
            for i, text in enumerate(det_sections):
                first_line = text.split("\n")[0][:80]
                title = first_line.strip("- –—:1234567890.)")
                result.append({
                    "title": title.strip(),
                    "raw_text": text,
                    "split_method": "deterministic",
                })
            result = _infer_section_roles(result)
            validated = _validate_sections(result, prompt)
            if validated:
                logger.info("Split tier 1 (deterministic) succeeded: %d sections", len(validated))
                return validated
            logger.info("Split tier 1 (deterministic) found sections but failed validation")

        # Tier 2: Lightweight LLM (markers only, no role)
        try:
            system = SPLIT_SYSTEM_PROMPT.format(
                slide_count=slide_count,
                language=language,
            )
            raw = await self._tracked_llm_call(
                db=db,
                tenant_id=tenant_id,
                presentation_id=pres_id,
                slide_id=None,
                purpose=RunPurpose.OUTLINE.value,
                system_prompt=system,
                user_prompt=prompt,
                max_tokens=2048,
            )
            parsed = self._parse_json(raw)

            if parsed and "sections" in parsed:
                resolved = _resolve_sections_from_markers(prompt, parsed["sections"])
                if resolved:
                    # Copy titles from LLM, add split_method
                    for section in resolved:
                        section["split_method"] = "llm_markers"
                    resolved = _infer_section_roles(resolved)
                    validated = _validate_sections(resolved, prompt)
                    if validated:
                        logger.info("Split tier 2 (LLM markers) succeeded: %d sections", len(validated))
                        return validated
                    logger.warning("LLM split failed validation, falling back to paragraph split")
                else:
                    logger.warning("LLM markers unresolvable, falling back to paragraph split")
            else:
                logger.warning("LLM split returned invalid JSON, falling back to paragraph split")
        except Exception as e:
            logger.warning("LLM split call failed: %s, falling back to paragraph split", e)

        # Tier 3: Fallback paragraph split
        logger.info("Split tier 3 (fallback paragraph) for %d sections", slide_count)
        result = _fallback_paragraph_split(prompt, slide_count)
        for section in result:
            section["split_method"] = "fallback_paragraph"
        result = _infer_section_roles(result)
        return result

    # ══════════════════════════════════════════════
    #  AI Generation — called from Arq workers
    # ══════════════════════════════════════════════

    async def generate_slides(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        request: GenerateSlidesRequest,
        on_slide_progress: Any | None = None,
    ) -> list[PresentationSlide]:
        """Generate slides using multi-step pipeline or legacy single-call XML.

        V2 pipeline (default):
        1. LLM outline generation (JSON) → structured narrative plan
        2. Deterministic slide planning → layout/component constraints
        3. Per-slide XML generation → parse → validate → repair → normalize → save

        V1 legacy (fallback via use_pipeline_v2=False):
        1. Split prompt into sections (deterministic or lightweight LLM)
        2. Single LLM call generates ALL slides in XML format
        3. Parse → normalize → save
        """
        settings = get_settings()
        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not pres:
            raise ValueError(f"Presentation {pres_id} not found")
        if not pres.prompt:
            raise ValueError("No prompt — set prompt first")

        pres.status = PresentationStatus.GENERATING_SLIDES.value
        await db.flush()

        # Optional RAG context
        rag_context = "Aucun contexte additionnel."
        if request.collection_ids:
            chunks = await self.retrieval.retrieve(
                query=pres.prompt or pres.title,
                tenant_id=tenant_id,
                collection_ids=request.collection_ids,
                db=db,
            )
            rag_context = self.retrieval.build_context(chunks)

        lang = pres.settings.get("language", "fr-FR")
        style = pres.settings.get("style", "professional")
        slide_count = pres.settings.get("slide_count", 8)

        # Resolve theme data
        theme_data = None
        if pres.theme_id:
            theme = await db.get(PresentationTheme, pres.theme_id)
            if theme:
                theme_data = theme.theme_data

        if settings.use_pipeline_v2:
            return await self._generate_slides_v2(
                db, tenant_id, pres_id, pres,
                slide_count=slide_count,
                lang=lang,
                style=style,
                rag_context=rag_context,
                theme_data=theme_data,
                on_slide_progress=on_slide_progress,
            )
        else:
            return await self._generate_slides_v1(
                db, tenant_id, pres_id, pres,
                slide_count=slide_count,
                lang=lang,
                style=style,
                rag_context=rag_context,
                theme_data=theme_data,
                on_slide_progress=on_slide_progress,
            )

    async def _generate_slides_v2(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        pres: Presentation,
        *,
        slide_count: int,
        lang: str,
        style: str,
        rag_context: str,
        theme_data: dict | None,
        on_slide_progress: Any | None = None,
    ) -> list[PresentationSlide]:
        """V2 pipeline: outline → plan → per-slide generation."""
        try:
            # ── Step 1: Generate outline ──
            async def _split_fallback(prompt: str, sc: int, language: str) -> list[dict]:
                return await self._split_prompt_into_sections(
                    db, tenant_id, pres_id, prompt, sc, language,
                )

            outline = await _generate_outline_v2(
                prompt=pres.prompt,
                slide_count=slide_count,
                language=lang,
                style=style,
                rag_context=rag_context,
                llm_call=lambda sys, usr: self._tracked_llm_call(
                    db=db,
                    tenant_id=tenant_id,
                    presentation_id=pres_id,
                    slide_id=None,
                    purpose=RunPurpose.OUTLINE.value,
                    system_prompt=sys,
                    user_prompt=usr,
                    max_tokens=4096,
                ),
                split_fallback=_split_fallback,
            )

            # Store outline (same format as V1 for frontend compatibility)
            pres.outline = [
                {
                    "title": s.title,
                    "bullets": list(s.key_points),
                    "detailed_content": s.goal,
                    "source_mode": "llm_outline",
                }
                for s in outline.slides
            ]
            pres.title = outline.presentation_title or pres.title
            await db.flush()

            # ── Step 1.5: Auto-create theme if none selected ──
            if not theme_data and outline.suggested_theme:
                try:
                    from app.schemas.presentation import ThemeColors, ThemeData, ThemeFonts
                    suggested = outline.suggested_theme
                    auto_theme_data = ThemeData(
                        colors=ThemeColors(
                            primary=suggested.primary,
                            secondary=suggested.secondary,
                            accent=suggested.accent,
                            background=suggested.background,
                            text=suggested.text,
                            heading=suggested.heading,
                            muted=suggested.muted,
                        ),
                        fonts=ThemeFonts(
                            heading=suggested.heading_font,
                            body=suggested.body_font,
                        ),
                    )
                    auto_theme = PresentationTheme(
                        tenant_id=tenant_id,
                        name=f"Auto — {suggested.palette_name or pres.title[:30]}",
                        is_builtin=False,
                        theme_data=auto_theme_data.model_dump(),
                    )
                    db.add(auto_theme)
                    await db.flush()
                    await db.refresh(auto_theme)

                    pres.theme_id = auto_theme.id
                    await db.flush()

                    theme_data = auto_theme.theme_data
                    logger.info(
                        "V2: Auto-created theme '%s' for %s (palette: %s)",
                        auto_theme.name, pres_id, suggested.palette_name,
                    )
                except Exception as theme_err:
                    logger.warning("Failed to auto-create theme: %s", theme_err)

            # ── Step 2: Build deck plan (deterministic, zero LLM) ──
            deck_plan = _build_deck_plan_v2(outline)

            # ── Step 3: Generate slides one by one ──
            extra_sections = self._build_xml_extra_sections(theme_data, lang)

            # Delete existing slides
            for existing in pres.slides:
                await db.delete(existing)
            await db.flush()

            slides: list[PresentationSlide] = []
            slide_ids: list[str] = []
            previously_generated: list[dict] = []

            for plan in deck_plan.slides:
                # generate_slide_xml never raises — fallback is built in
                slide_data = await _generate_slide_xml_v2(
                    slide_plan=plan,
                    deck_plan=deck_plan,
                    previously_generated=previously_generated,
                    original_prompt=pres.prompt or pres.title,
                    rag_context=rag_context,
                    language=lang,
                    style=style,
                    theme_extra_sections=extra_sections,
                    llm_call_xml=lambda sys, usr: self._tracked_llm_call_xml(
                        db=db,
                        tenant_id=tenant_id,
                        presentation_id=pres_id,
                        slide_id=None,
                        purpose="SLIDE_GEN",
                        system_prompt=sys,
                        user_prompt=usr,
                        max_tokens=4096,
                        model=self.slide_model,
                    ),
                    llm_call_json=lambda sys, usr: self._tracked_llm_call_xml(
                        db=db,
                        tenant_id=tenant_id,
                        presentation_id=pres_id,
                        slide_id=None,
                        purpose="REPAIR",
                        system_prompt=sys,
                        user_prompt=usr,
                        max_tokens=4096,
                    ),
                )

                slide = PresentationSlide(
                    presentation_id=pres_id,
                    position=plan.slide_number - 1,
                    layout_type=slide_data.get("layout_type", "vertical"),
                    content_json=slide_data.get("content_json", []),
                    root_image=slide_data.get("root_image"),
                    bg_color=slide_data.get("bg_color"),
                    sizing=slide_data.get("sizing"),
                )
                db.add(slide)
                await db.flush()
                await db.refresh(slide)

                slides.append(slide)
                slide_ids.append(str(slide.id))
                previously_generated.append(slide_data)

                logger.info(
                    f"V2: Saved slide {plan.slide_number}/{len(deck_plan.slides)} "
                    f"(layout={slide.layout_type}, role={plan.role}) for {pres_id}"
                )

                if on_slide_progress:
                    try:
                        await on_slide_progress(slide, plan.slide_number - 1, len(deck_plan.slides))
                    except Exception as cb_err:
                        logger.warning(f"Progress callback failed: {cb_err}")

            pres.slide_order = slide_ids
            pres.status = PresentationStatus.READY.value
            pres.version = pres.version + 1
            await db.flush()

            return slides

        except Exception as fatal:
            logger.exception(f"Fatal error in V2 slide generation for {pres_id}: {fatal}")
            pres.status = PresentationStatus.ERROR.value
            await db.flush()
            raise

    async def _generate_slides_v1(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        pres: Presentation,
        *,
        slide_count: int,
        lang: str,
        style: str,
        rag_context: str,
        theme_data: dict | None,
        on_slide_progress: Any | None = None,
    ) -> list[PresentationSlide]:
        """V1 legacy pipeline: split → single XML LLM call → parse → save."""
        # ── Split prompt into sections ──
        sections = await self._split_prompt_into_sections(
            db, tenant_id, pres_id, pres.prompt, slide_count, lang,
        )

        # Store sections as outline for DB/frontend compatibility
        pres.outline = [
            {
                "title": s["title"],
                "bullets": [],
                "detailed_content": s["raw_text"],
                "source_mode": "raw_section",
                "split_method": s.get("split_method", "unknown"),
            }
            for s in sections
        ]
        pres.title = sections[0]["title"] if sections else pres.title
        await db.flush()

        actual_slide_count = slide_count

        # Build outline formatted for XML prompt
        outline_formatted = ""
        if len(sections) < actual_slide_count:
            outline_formatted += (
                f"(Le prompt utilisateur est court. Développe-le en exactement "
                f"{actual_slide_count} slides variés et complets. "
                f"Commence par un slide de couverture, termine par un slide de conclusion/contact.)\n\n"
            )
        for i, section in enumerate(sections):
            outline_formatted += f"## Slide {i + 1}: {section['title']}\n"
            raw = section.get("raw_text", "")
            if raw:
                outline_formatted += f"{raw[:500]}\n\n"

        extra_sections = self._build_xml_extra_sections(theme_data, lang)

        # Delete existing slides
        for existing in pres.slides:
            await db.delete(existing)
        await db.flush()

        slides: list[PresentationSlide] = []
        slide_ids: list[str] = []

        try:
            import datetime
            current_date = datetime.datetime.now().strftime("%A %d %B %Y")

            system_prompt = XML_SLIDES_SYSTEM_PROMPT.replace(
                "{{SLIDE_COUNT}}", str(actual_slide_count)
            ).replace(
                "{{TITLE}}", pres.title
            ).replace(
                "{{PROMPT}}", pres.prompt or pres.title
            ).replace(
                "{{CURRENT_DATE}}", current_date
            ).replace(
                "{{LANGUAGE}}", lang
            ).replace(
                "{{TONE}}", style
            ).replace(
                "{{OUTLINE_FORMATTED}}", outline_formatted
            ).replace(
                "{{RAG_CONTEXT}}", rag_context
            ).replace(
                "{{EXTRA_SECTIONS}}", extra_sections
            )

            user_prompt = (
                f"Génère une présentation de {actual_slide_count} slides en XML "
                f"sur le sujet : {pres.prompt or pres.title}"
            )

            xml_response = await self._tracked_llm_call_xml(
                db=db,
                tenant_id=tenant_id,
                presentation_id=pres_id,
                slide_id=None,
                purpose="SLIDE_GEN",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=16384,
                model=self.slide_model,
            )

            parser = XMLSlideParser()
            slide_datas = parser.parse_presentation(xml_response)

            if not slide_datas:
                logger.error(f"XML parser returned 0 slides for {pres_id}, falling back to legacy")
                raise ValueError("XML parser returned no slides")

            logger.info(
                f"XML pipeline: generated {len(slide_datas)} slides "
                f"(expected {actual_slide_count}) for {pres_id}"
            )

            for i, slide_data in enumerate(slide_datas):
                try:
                    slide_data = normalize_slide(slide_data)

                    slide = PresentationSlide(
                        presentation_id=pres_id,
                        position=i,
                        layout_type=slide_data.get("layout_type", "vertical"),
                        content_json=slide_data.get("content_json", []),
                        root_image=slide_data.get("root_image"),
                        bg_color=slide_data.get("bg_color"),
                        sizing=slide_data.get("sizing"),
                    )
                    db.add(slide)
                    await db.flush()
                    await db.refresh(slide)

                    slides.append(slide)
                    slide_ids.append(str(slide.id))

                    logger.info(
                        f"Saved slide {i + 1}/{len(slide_datas)} "
                        f"(layout={slide.layout_type}) for {pres_id}"
                    )

                    if on_slide_progress:
                        try:
                            await on_slide_progress(slide, i, len(slide_datas))
                        except Exception as cb_err:
                            logger.warning(f"Progress callback failed: {cb_err}")
                except Exception as persist_err:
                    logger.error(f"Failed to persist slide {i}: {persist_err}")
                    continue

            pres.slide_order = slide_ids
            pres.status = PresentationStatus.READY.value
            pres.version = pres.version + 1
            await db.flush()

        except Exception as fatal:
            logger.exception(f"Fatal error in slide generation for {pres_id}: {fatal}")
            pres.status = PresentationStatus.ERROR.value
            await db.flush()
            raise

        return slides

    def _build_xml_extra_sections(self, theme_data: dict | None, lang: str) -> str:
        """Build extra prompt sections for XML generation (theme, icon policy)."""
        parts: list[str] = []

        if theme_data:
            colors = theme_data.get("colors", {})
            fonts = theme_data.get("fonts", {})
            parts.append(
                f"\n## THÈME ACTIF\n"
                f"- Couleur primaire : {colors.get('primary', '#6C63FF')}\n"
                f"- Couleur secondaire : {colors.get('secondary', '#2D2B55')}\n"
                f"- Couleur accent : {colors.get('accent', '#FF6584')}\n"
                f"- Police titres : {fonts.get('heading', 'Inter')}\n"
                f"- Police corps : {fonts.get('body', 'Inter')}\n"
            )

        icon_names = get_icon_names_for_prompt()
        if icon_names:
            parts.append(
                f"\n## ICÔNES DISPONIBLES\n"
                f"Pour les tags <ICON query=\"...\"/>, utilise des termes sémantiques.\n"
                f"Noms Lucide disponibles : {icon_names[:500]}\n"
            )

        return "\n".join(parts)

    async def _pipeline_outline_to_slides(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        presentation_id: UUID,
        outline_item: dict,
        slide_index: int,
        total_slides: int,
        deck_context: DeckContext,
        rag_context: str,
        language: str,
        style: str,
        theme_data: dict | None,
        outline_context: str,
        original_prompt: str = "",
    ) -> list[dict]:
        """Pipeline: deterministic brief → split → select → rewrite (LLM) → compose → evaluate → normalize.

        Returns a list of 1 or 2 slide dicts (if split).
        """
        # Step 1: Build SlideBrief deterministically (NO LLM — preserves all data)
        brief = self._brief_from_outline_enhanced(
            outline_item=outline_item,
            slide_index=slide_index,
            total_slides=total_slides,
        )

        # Step 2: Maybe split dense briefs
        briefs = maybe_split_brief(brief)
        deck_context.generated_briefs.extend(briefs)

        # Extract detailed_content from outline item for the rewriter
        slide_detailed_content = outline_item.get("detailed_content") or ""

        # Step 3-7: Process each brief
        results: list[dict] = []
        for sub_brief in briefs:
            slide_data = await self._pipeline_brief_to_slide(
                db=db,
                tenant_id=tenant_id,
                presentation_id=presentation_id,
                brief=sub_brief,
                deck_context=deck_context,
                rag_context=rag_context,
                language=language,
                style=style,
                theme_data=theme_data,
                original_prompt=original_prompt,
                detailed_content=slide_detailed_content,
            )
            results.append(slide_data)

        return results

    async def _pipeline_brief_to_slide(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        presentation_id: UUID,
        brief: SlideBrief,
        deck_context: DeckContext,
        rag_context: str,
        language: str,
        style: str,
        theme_data: dict | None,
        original_prompt: str = "",
        detailed_content: str = "",
    ) -> dict:
        """Process a single brief through the deterministic pipeline.

        Steps: select_template → rewrite → compose → evaluate → normalize
        """
        # Step 3: Deterministic template selection
        template = select_template_deterministic(brief, deck_context)
        deck_context.used_templates.append(template.id)

        # Step 4: Rewrite content for the selected template
        async def _llm_call(system_prompt: str, user_prompt: str) -> str:
            return await self._tracked_llm_call(
                db=db,
                tenant_id=tenant_id,
                presentation_id=presentation_id,
                slide_id=None,
                purpose=RunPurpose.SLIDE_GEN.value,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=2048,
                model=self.slide_model,
            )

        filled_content = await rewrite_brief_for_template(
            brief=brief,
            template=template,
            language=language,
            style=style,
            rag_context=rag_context,
            llm_call=_llm_call,
            original_prompt=original_prompt,
            detailed_content=detailed_content,
        )

        # Step 5: Deterministic composition → PlateJS content_json
        composed = compose_slide(template, filled_content, theme_data)

        # Step 6: Evaluate fit
        fit_report = evaluate_fit(composed, template)
        logger.info(
            "Fit report for %s: score=%d surface=%.2f rec=%s",
            template.id, fit_report.score, fit_report.surface_ratio, fit_report.recommendation,
        )

        # If score too low, try alternate template
        if fit_report.score < 60 and fit_report.recommendation == "alternate_template":
            logger.warning("Score too low (%d), trying alternate template", fit_report.score)
            # Force a different template by temporarily adding current to used
            alt_context = DeckContext(
                deck_title=deck_context.deck_title,
                deck_prompt=deck_context.deck_prompt,
                total_slides=deck_context.total_slides,
                used_templates=[*deck_context.used_templates, template.id],
                used_layouts=[*deck_context.used_layouts, composed.get("layout_type", "")],
            )
            alt_template = select_template_deterministic(brief, alt_context)
            if alt_template.id != template.id:
                alt_filled = await rewrite_brief_for_template(
                    brief=brief,
                    template=alt_template,
                    language=language,
                    style=style,
                    rag_context=rag_context,
                    llm_call=_llm_call,
                    original_prompt=original_prompt,
                    detailed_content=detailed_content,
                )
                composed = compose_slide(alt_template, alt_filled, theme_data)
                template = alt_template
                # Update last used template
                deck_context.used_templates[-1] = template.id

        # Step 7: Apply existing normalizer (template_def overrides max_items)
        legacy_template = get_template(template.legacy_template_id)
        composed = normalize_slide(composed, template=legacy_template, theme=theme_data, template_def=template)

        # Fix 4: Persist source data as speaker notes
        if detailed_content and len(detailed_content) > 300:
            composed["speaker_notes"] = detailed_content

        # Fix 6: Log compression metrics
        _log_slide_metrics(detailed_content, brief, template, composed)

        return composed

    async def _generate_brief(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        presentation_id: UUID,
        outline_item: dict,
        slide_index: int,
        total_slides: int,
        rag_context: str,
        language: str,
        style: str,
        outline_context: str,
        original_prompt: str = "",
    ) -> SlideBrief:
        """Generate a SlideBrief from an outline item via LLM."""
        title = outline_item.get("title", "")
        bullets = outline_item.get("bullets", [])
        detailed_content = outline_item.get("detailed_content") or ""

        # Build detailed content section
        if detailed_content:
            detailed_content_section = f"CONTENU DÉTAILLÉ POUR CE SLIDE (à préserver fidèlement) :\n{detailed_content}"
        else:
            detailed_content_section = ""

        system_prompt = SLIDE_BRIEF_SYSTEM_PROMPT.format(
            language=language,
            style=style,
            rag_context=rag_context,
        )

        user_prompt = SLIDE_BRIEF_USER_TEMPLATE.format(
            slide_number=slide_index + 1,
            total_slides=total_slides,
            title=title,
            bullets="\n".join(f"- {b}" for b in bullets),
            detailed_content_section=detailed_content_section,
            original_prompt=original_prompt,
            outline_context=outline_context,
        )

        raw = await self._tracked_llm_call(
            db=db,
            tenant_id=tenant_id,
            presentation_id=presentation_id,
            slide_id=None,
            purpose=RunPurpose.SLIDE_GEN.value,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
            model=self.slide_model,
        )

        # Parse brief
        try:
            parsed = json.loads(raw)
            brief = SlideBrief.model_validate(parsed)
            logger.info(
                "Brief generated: role=%s blocks=%d density=%s for '%s'",
                brief.narrative_role.value, len(brief.blocks), brief.density_target, title,
            )
            return brief
        except Exception as e:
            logger.warning("Brief parse failed: %s, building from outline", e)
            return self._brief_from_outline(outline_item, slide_index, total_slides)

    @staticmethod
    def _brief_from_outline(
        outline_item: dict,
        slide_index: int,
        total_slides: int,
    ) -> SlideBrief:
        """Build a minimal SlideBrief directly from outline (no LLM)."""
        title = outline_item.get("title", f"Slide {slide_index + 1}")
        bullets = outline_item.get("bullets", [])

        # Determine role from position
        if slide_index == 0:
            role = NarrativeRole.COVER
        elif slide_index == total_slides - 1:
            role = NarrativeRole.TAKEAWAY
        else:
            role = NarrativeRole.INSIGHT

        blocks = [
            SlideBlock(
                kind="point",
                priority=1,
                title=b,
                body="",
            )
            for b in bullets[:4]
        ]

        return SlideBrief(
            slide_goal="inform",
            narrative_role=role,
            key_message=title,
            title=title,
            density_target="medium",
            blocks=blocks,
        )

    @staticmethod
    def _brief_from_outline_enhanced(
        outline_item: dict,
        slide_index: int,
        total_slides: int,
    ) -> SlideBrief:
        """Build a rich SlideBrief deterministically from outline data (no LLM).

        Preserves ALL data from the outline item's detailed_content.
        """
        title = outline_item.get("title", f"Slide {slide_index + 1}")
        bullets = outline_item.get("bullets", [])
        detailed_content = outline_item.get("detailed_content") or ""

        # 1. Infer narrative role from position + keyword analysis
        role = _infer_narrative_role(title, bullets, slide_index, total_slides)

        # 2. Determine density target from content volume
        content_length = len(detailed_content) + sum(len(b) for b in bullets)
        if content_length > 500:
            density = "high"
        elif content_length > 200:
            density = "medium"
        else:
            density = "low"

        # 3. Determine preferred visual from role
        _ROLE_TO_VISUAL: dict[NarrativeRole, str | None] = {
            NarrativeRole.COVER: None,
            NarrativeRole.HOOK: None,
            NarrativeRole.CONTEXT: "cards",
            NarrativeRole.PROBLEM: "cards",
            NarrativeRole.INSIGHT: "cards",
            NarrativeRole.PROOF: "stats",
            NarrativeRole.PROCESS: "timeline",
            NarrativeRole.PLAN: "timeline",
            NarrativeRole.COMPARISON: "comparison",
            NarrativeRole.TEAM: "cards",
            NarrativeRole.TAKEAWAY: None,
            NarrativeRole.CLOSING: None,
        }
        preferred_visual = _ROLE_TO_VISUAL.get(role)

        # 4. Build blocks from bullets + detailed_content
        blocks = _build_blocks_from_outline(bullets, detailed_content, role)

        # 5. Determine asset need
        needs_photo = role not in (
            NarrativeRole.TAKEAWAY, NarrativeRole.CLOSING,
        ) and density != "high"
        asset_need = "photo" if needs_photo else "none"

        return SlideBrief(
            slide_goal=f"slide_{slide_index + 1}_{role.value}",
            narrative_role=role,
            key_message=title,
            title=title,
            subtitle=bullets[0] if bullets and role in (NarrativeRole.COVER, NarrativeRole.HOOK) else None,
            density_target=density,
            preferred_visual=preferred_visual,
            blocks=blocks,
            asset_need=asset_need,
            proof_level="medium" if role == NarrativeRole.PROOF else "none",
        )

    @staticmethod
    def _pick_alternative_template(
        current_id: str,
        used: list[str],
        outline_item: dict,
        slide_index: int,
        total_slides: int,
    ) -> TemplateSuggestion | None:
        """Pick a different template to avoid consecutive duplicates."""
        # Alternatives by category
        _ALTERNATIVES = {
            "cards_3": ["features_icons", "kpi_3", "timeline"],
            "cards_4": ["cards_3", "features_icons", "kpi_3"],
            "features_icons": ["cards_3", "cards_4", "timeline"],
            "kpi_3": ["chart", "big_number", "cards_3"],
            "big_number": ["kpi_3", "chart", "cards_3"],
            "timeline": ["process_steps", "roadmap", "cards_3"],
            "process_steps": ["timeline", "roadmap", "features_icons"],
            "roadmap": ["timeline", "process_steps", "cards_3"],
            "comparison_2col": ["pros_cons", "before_after", "cards_3"],
            "pros_cons": ["comparison_2col", "before_after", "kpi_3"],
            "before_after": ["comparison_2col", "pros_cons", "cards_3"],
            "chart": ["kpi_3", "big_number", "cards_3"],
            "quote": ["big_number", "cards_3", "features_icons"],
        }
        alts = _ALTERNATIVES.get(current_id, ["cards_3", "features_icons", "timeline"])
        recent = set(used[-2:]) if len(used) >= 2 else set(used)
        for alt_id in alts:
            if alt_id not in recent:
                template = get_template(alt_id)
                if template:
                    return TemplateSuggestion(
                        template_id=alt_id,
                        confidence=0.65,
                        reason=f"diversity: replaced consecutive {current_id}",
                        intent=template.intent,
                    )
        return None

    @staticmethod
    def _detect_template_from_instruction(instruction: str) -> TemplateSuggestion | None:
        """Detect visual type from user instruction and return matching template."""
        lower = instruction.lower()
        _INSTRUCTION_KEYWORDS = [
            (["graphique", "chart", "courbe", "diagramme", "camembert", "barres", "pie", "donut"], "chart"),
            (["timeline", "chronologie", "frise", "étapes", "processus"], "timeline"),
            (["stats", "chiffres", "kpi", "métriques", "statistiques", "chiffre clé", "nombre"], "kpi_3"),
            (["comparaison", "comparer", "versus", " vs ", "côte à côte"], "comparison_2col"),
            (["pour contre", "pros cons", "avantages", "inconvénients"], "pros_cons"),
            (["avant après", "before after", "transformation"], "before_after"),
            (["cartes", "cards", "box", "grille"], "cards_3"),
            (["icônes", "icons", "features", "fonctionnalités"], "features_icons"),
            (["citation", "quote", "témoignage"], "quote"),
            (["pyramide", "funnel", "entonnoir"], "pyramid_group"),
            (["escalier", "staircase", "progression"], "process_steps"),
            (["équipe", "team", "profils"], "team"),
        ]
        for keywords, template_id in _INSTRUCTION_KEYWORDS:
            if any(kw in lower for kw in keywords):
                template = get_template(template_id)
                if template:
                    return TemplateSuggestion(
                        template_id=template_id,
                        confidence=1.0,
                        reason=f"instruction-detected: {template_id}",
                        intent=template.intent,
                    )
        return None

    def _parse_batch_slides(
        self,
        raw: str,
        outline: list[dict],
        expected_count: int,
    ) -> list[dict]:
        """Parse the batch LLM response into individual slide dicts.

        Handles: valid JSON array, truncated JSON, and fallback to safe templates.
        """
        parsed = self._parse_json(raw)
        if not parsed:
            logger.error("Batch slide generation: failed to parse JSON, using fallbacks")
            return [
                get_safe_fallback(
                    outline[i] if i < len(outline) else {"title": f"Slide {i+1}", "bullets": []},
                    i,
                    expected_count,
                )
                for i in range(expected_count)
            ]

        # Extract slides array
        raw_slides = parsed.get("slides", [])
        if not isinstance(raw_slides, list):
            raw_slides = [parsed] if "content_json" in parsed else []

        # Validate each slide, fallback for invalid ones
        result: list[dict] = []
        for i in range(expected_count):
            if i < len(raw_slides):
                slide_data = raw_slides[i]
                try:
                    validated = SlideContent.model_validate(slide_data)
                    result.append(validated.model_dump())
                    continue
                except (ValidationError, Exception) as e:
                    logger.warning(f"Slide {i} validation failed: {e}")

            # Fallback for missing/invalid slides
            outline_item = outline[i] if i < len(outline) else {"title": f"Slide {i+1}", "bullets": []}
            result.append(get_safe_fallback(outline_item, i, expected_count))

        return result

    async def regenerate_slide(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        slide_id: UUID,
        request: RegenerateSlideRequest,
    ) -> PresentationSlide | None:
        """Regenerate a single slide with optional user instruction.

        V2: builds a SlidePlan from outline + role, uses constrained generation.
        V1: uses XML_SINGLE_SLIDE_PROMPT with freeform generation.
        Both fall back to _legacy_generate_slide() if primary pipeline fails.
        """
        slide = await self.get_slide(db, tenant_id, pres_id, slide_id)
        if not slide:
            return None

        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not pres or not pres.outline:
            return None

        # Find matching outline item by position
        outline_item = (
            pres.outline[slide.position]
            if slide.position < len(pres.outline)
            else {"title": "Slide", "bullets": []}
        )

        rag_context = "Aucun contexte additionnel."
        if request.collection_ids:
            chunks = await self.retrieval.retrieve(
                query=request.instruction or pres.prompt or pres.title,
                tenant_id=tenant_id,
                collection_ids=request.collection_ids,
                db=db,
            )
            rag_context = self.retrieval.build_context(chunks)

        lang = pres.settings.get("language", "fr-FR")
        style = pres.settings.get("style", "professional")

        # Resolve theme data for prompt enrichment
        theme_data = None
        if pres.theme_id:
            theme = await db.get(PresentationTheme, pres.theme_id)
            if theme:
                theme_data = theme.theme_data

        settings = get_settings()

        if settings.use_pipeline_v2:
            slide_data = await self._regenerate_slide_v2(
                db=db,
                tenant_id=tenant_id,
                pres=pres,
                slide=slide,
                outline_item=outline_item,
                rag_context=rag_context,
                lang=lang,
                style=style,
                theme_data=theme_data,
                instruction=request.instruction,
            )
        else:
            slide_data = await self._regenerate_slide_v1(
                db=db,
                tenant_id=tenant_id,
                pres=pres,
                slide=slide,
                slide_id=slide_id,
                outline_item=outline_item,
                rag_context=rag_context,
                lang=lang,
                style=style,
                theme_data=theme_data,
                instruction=request.instruction,
            )

        slide.layout_type = slide_data.get("layout_type", "vertical")
        slide.content_json = slide_data.get("content_json", [])
        slide.root_image = slide_data.get("root_image")
        slide.bg_color = slide_data.get("bg_color")
        if slide_data.get("sizing"):
            slide.sizing = slide_data["sizing"]

        pres.version = pres.version + 1
        await db.flush()
        await db.refresh(slide)
        return slide

    async def _regenerate_slide_v2(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        pres: Presentation,
        slide: PresentationSlide,
        outline_item: dict,
        rag_context: str,
        lang: str,
        style: str,
        theme_data: dict | None,
        instruction: str | None,
    ) -> dict:
        """V2 regeneration: build SlidePlan → constrained generation."""
        from app.services.presentation_outline_generator import (
            GeneratedOutline,
            OutlineSlide,
            normalize_role,
        )

        try:
            # Build a single-slide outline + plan
            role_str = outline_item.get("source_mode", "")
            if role_str != "llm_outline":
                # Infer role from position/title
                role = _infer_narrative_role(
                    title=outline_item.get("title", ""),
                    bullets=outline_item.get("bullets", []),
                    slide_index=slide.position,
                    total_slides=len(pres.outline),
                )
                role_str = role.value
            else:
                # Use saved role or infer
                role = _infer_narrative_role(
                    title=outline_item.get("title", ""),
                    bullets=outline_item.get("bullets", []),
                    slide_index=slide.position,
                    total_slides=len(pres.outline),
                )
                role_str = role.value

            slide_role = normalize_role(role_str)

            # Build a minimal outline for the planner
            outline_slide = OutlineSlide(
                number=slide.position + 1,
                role=slide_role,
                title=outline_item.get("title", "Slide"),
                goal=outline_item.get("detailed_content", ""),
                key_points=outline_item.get("bullets", []),
            )
            outline = GeneratedOutline(
                presentation_title=pres.title,
                slides=[outline_slide],
            )
            deck_plan = _build_deck_plan_v2(outline)

            if not deck_plan.slides:
                raise ValueError("Deck plan produced no slides")

            plan = deck_plan.slides[0]
            extra_sections = self._build_xml_extra_sections(theme_data, lang)

            # Build context from sibling slides
            previously_generated: list[dict] = []
            for sib in sorted(pres.slides, key=lambda s: s.position):
                if sib.id != slide.id:
                    previously_generated.append({
                        "layout_type": sib.layout_type,
                        "content_json": sib.content_json or [],
                    })

            slide_data = await _generate_slide_xml_v2(
                slide_plan=plan,
                deck_plan=deck_plan,
                previously_generated=previously_generated,
                original_prompt=pres.prompt or pres.title,
                rag_context=rag_context,
                language=lang,
                style=style,
                theme_extra_sections=extra_sections,
                llm_call_xml=lambda sys, usr: self._tracked_llm_call_xml(
                    db=db,
                    tenant_id=tenant_id,
                    presentation_id=pres.id,
                    slide_id=slide.id,
                    purpose="REGENERATE",
                    system_prompt=sys,
                    user_prompt=usr,
                    max_tokens=4096,
                    model=self.slide_model,
                ),
                llm_call_json=lambda sys, usr: self._tracked_llm_call_xml(
                    db=db,
                    tenant_id=tenant_id,
                    presentation_id=pres.id,
                    slide_id=slide.id,
                    purpose="REPAIR",
                    system_prompt=sys,
                    user_prompt=usr,
                    max_tokens=4096,
                ),
                instruction=instruction,
            )
            return slide_data

        except Exception as e:
            logger.error(f"V2 regenerate failed: {e}, falling back to legacy")
            return await self._legacy_generate_slide(
                db=db,
                tenant_id=tenant_id,
                presentation_id=pres.id,
                outline_item=outline_item,
                slide_index=slide.position,
                total_slides=len(pres.outline),
                prev_layout="",
                rag_context=rag_context,
                language=lang,
                style=style,
                theme_data=theme_data,
            )

    async def _regenerate_slide_v1(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        pres: Presentation,
        slide: PresentationSlide,
        slide_id: UUID,
        outline_item: dict,
        rag_context: str,
        lang: str,
        style: str,
        theme_data: dict | None,
        instruction: str | None,
    ) -> dict:
        """V1 regeneration: freeform XML single-slide prompt."""
        try:
            extra_sections = self._build_xml_extra_sections(theme_data, lang)

            # Build outline context
            outline_context = f"Titre : {pres.title}\nSujet : {pres.prompt or pres.title}\n\nPLAN COMPLET :\n"
            for idx, item in enumerate(pres.outline):
                t = item.get("title", f"Section {idx + 1}")
                outline_context += f"  {idx + 1}. {t}\n"

            system_prompt = XML_SINGLE_SLIDE_PROMPT.replace(
                "{{LANGUAGE}}", lang
            ).replace(
                "{{TONE}}", style
            ).replace(
                "{{EXTRA_SECTIONS}}", extra_sections
            )

            user_parts = [
                f"Slide {slide.position + 1}/{len(pres.outline)}.",
                f"Titre : {outline_item.get('title', 'Slide')}",
            ]
            detailed = outline_item.get("detailed_content")
            if detailed:
                user_parts.append(f"Contenu détaillé :\n{detailed[:1000]}")
            user_parts.append(f"\nOutline complet :\n{outline_context}")
            user_parts.append(f"\nContexte RAG : {rag_context[:1000]}")

            if instruction and instruction.strip():
                user_parts.append(f"\nINSTRUCTION UTILISATEUR : {instruction.strip()}")

            current_content = slide.content_json if isinstance(slide.content_json, list) else None
            if current_content:
                user_parts.append(f"\nCONTENU ACTUEL (à modifier) :\n{json.dumps(current_content, ensure_ascii=False)[:2000]}")

            user_prompt = "\n".join(user_parts)

            xml_response = await self._tracked_llm_call_xml(
                db=db,
                tenant_id=tenant_id,
                presentation_id=pres.id,
                slide_id=slide_id,
                purpose="REGENERATE",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=4096,
                model=self.slide_model,
            )

            parser = XMLSlideParser()
            slide_data = parser.parse_single_section(xml_response)
            slide_data = normalize_slide(slide_data)
            return slide_data

        except Exception as e:
            logger.error(f"XML regenerate failed: {e}, falling back to legacy")
            return await self._legacy_generate_slide(
                db=db,
                tenant_id=tenant_id,
                presentation_id=pres.id,
                outline_item=outline_item,
                slide_index=slide.position,
                total_slides=len(pres.outline),
                prev_layout="",
                rag_context=rag_context,
                language=lang,
                style=style,
                theme_data=theme_data,
            )

    # ══════════════════════════════════════════════
    #  Export — create export record, actual work done in Arq
    # ══════════════════════════════════════════════

    async def create_export(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
        request: ExportRequest,
    ) -> PresentationExport | None:
        pres = await self.get(db, tenant_id, pres_id, with_slides=True)
        if not pres:
            return None

        # Build payload hash for snapshot
        slides_data = []
        for slide in sorted(pres.slides, key=lambda s: s.position):
            slides_data.append({
                "position": slide.position,
                "layout_type": slide.layout_type,
                "content_json": slide.content_json,
                "root_image": slide.root_image,
                "bg_color": slide.bg_color,
            })
        payload_json = json.dumps(slides_data, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

        # Get theme snapshot
        theme_snapshot = None
        if pres.theme_id:
            theme = await db.get(PresentationTheme, pres.theme_id)
            if theme:
                theme_snapshot = theme.theme_data

        export = PresentationExport(
            presentation_id=pres_id,
            tenant_id=tenant_id,
            format=request.format,
            status="pending",
            presentation_version=pres.version,
            payload_hash=payload_hash,
            slide_count=len(pres.slides),
            theme_snapshot=theme_snapshot,
        )
        db.add(export)
        await db.flush()
        await db.refresh(export)
        return export

    async def list_exports(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        pres_id: UUID,
    ) -> list[PresentationExport]:
        pres = await self.get(db, tenant_id, pres_id)
        if not pres:
            return []
        result = await db.execute(
            select(PresentationExport)
            .where(
                PresentationExport.presentation_id == pres_id,
                PresentationExport.tenant_id == tenant_id,
            )
            .order_by(PresentationExport.created_at.desc())
        )
        return list(result.scalars().all())

    # ══════════════════════════════════════════════
    #  Internal — LLM calls with tracking
    # ══════════════════════════════════════════════

    async def _tracked_llm_call_xml(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        presentation_id: UUID,
        slide_id: UUID | None,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Make LLM call for XML output (no response_format constraint)."""
        effective_model = model or self.model
        run = PresentationGenerationRun(
            tenant_id=tenant_id,
            presentation_id=presentation_id,
            slide_id=slide_id,
            purpose=purpose,
            model=effective_model,
            input_hash=hashlib.sha256(
                (system_prompt + user_prompt).encode()
            ).hexdigest(),
            request_payload={
                "system_prompt": system_prompt[:2000],
                "user_prompt": user_prompt[:2000],
            },
            status="running",
        )
        db.add(run)
        await db.flush()

        t0 = time.monotonic()
        try:
            response = await self.client.chat.completions.create(
                model=effective_model,
                max_tokens=max_tokens or self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                # NO response_format — XML output, not JSON
            )
            content = response.choices[0].message.content or ""
            run.tokens_in = response.usage.prompt_tokens if response.usage else 0
            run.tokens_out = response.usage.completion_tokens if response.usage else 0
            run.response_excerpt = content[:500]
            run.status = "success"
            run.duration_ms = int((time.monotonic() - t0) * 1000)
            return content
        except Exception as e:
            run.status = "error"
            run.error = str(e)[:2000]
            run.duration_ms = int((time.monotonic() - t0) * 1000)
            raise
        finally:
            await db.flush()

    async def _tracked_llm_call(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        presentation_id: UUID,
        slide_id: UUID | None,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Make LLM call and log to generation_runs."""
        effective_model = model or self.model
        run = PresentationGenerationRun(
            tenant_id=tenant_id,
            presentation_id=presentation_id,
            slide_id=slide_id,
            purpose=purpose,
            model=effective_model,
            input_hash=hashlib.sha256(
                (system_prompt + user_prompt).encode()
            ).hexdigest(),
            request_payload={
                "system_prompt": system_prompt[:2000],
                "user_prompt": user_prompt[:2000],
            },
            status="running",
        )
        db.add(run)
        await db.flush()

        t0 = time.monotonic()
        try:
            response = await self.client.chat.completions.create(
                model=effective_model,
                max_tokens=max_tokens or self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            run.tokens_in = response.usage.prompt_tokens if response.usage else 0
            run.tokens_out = response.usage.completion_tokens if response.usage else 0
            run.response_excerpt = content[:500]
            run.status = "success"
            run.duration_ms = int((time.monotonic() - t0) * 1000)
            return content
        except Exception as e:
            run.status = "error"
            run.error = str(e)[:2000]
            run.duration_ms = int((time.monotonic() - t0) * 1000)
            raise
        finally:
            await db.flush()

    async def _legacy_generate_slide(
        self,
        *,
        db: AsyncSession,
        tenant_id: UUID,
        presentation_id: UUID,
        outline_item: dict,
        slide_index: int,
        total_slides: int,
        prev_layout: str,
        rag_context: str,
        language: str,
        style: str,
        user_instruction: str = "",
        target_template: str | None = None,
        current_content: list[dict] | None = None,
        theme_data: dict | None = None,
        full_outline_context: str = "",
        forced_template: TemplateSuggestion | None = None,
    ) -> dict:
        """Legacy slide generation — direct LLM → validation → normalization → repair → fallback.

        Kept as fallback for the new pipeline and for regenerate_slide with user instructions.
        """
        # 1. Determine template: instruction keywords > forced > target > auto-suggest
        instruction_template = self._detect_template_from_instruction(user_instruction) if user_instruction else None
        if instruction_template:
            suggestion = instruction_template
        elif forced_template:
            suggestion = forced_template
        elif target_template:
            template_obj = get_template(target_template)
            suggestion = TemplateSuggestion(
                template_id=target_template,
                confidence=1.0,
                reason=f"user-requested: {target_template}",
                intent=template_obj.intent if template_obj else SlideIntent.INFORM,
            )
        else:
            suggestion = suggest_template(outline_item, slide_index, total_slides)

        template_obj = get_template(suggestion.template_id)

        # 2. Suggest icons based on content
        combined_text = f"{outline_item.get('title', '')} {' '.join(outline_item.get('bullets', []))}"
        suggested_icons = suggest_icons_for_content(combined_text, max_results=5)

        # 3. Build enriched system prompt
        system_prompt = SLIDE_SYSTEM_PROMPT.format(
            language=language,
            style=style,
            rag_context=rag_context,
        )

        # Inject icon policy (compact: only names list)
        system_prompt += ICON_POLICY_SECTION.format(
            icon_names=get_icon_names_for_prompt(max_icons=40),
        )

        # Inject design constraints
        system_prompt += DESIGN_CONSTRAINTS_SECTION

        # Inject theme context if available
        if theme_data:
            colors = theme_data.get("colors", {})
            fonts = theme_data.get("fonts", {})
            system_prompt += THEME_CONTEXT_SECTION.format(
                primary=colors.get("primary", ""),
                secondary=colors.get("secondary", ""),
                accent=colors.get("accent", ""),
                heading_font=fonts.get("heading", "Inter"),
                body_font=fonts.get("body", "Inter"),
                border_radius=theme_data.get("border_radius", "12px"),
            )

        # 4. Build enriched user prompt — frame as visual topics, not text bullets
        topics = outline_item.get("bullets", [])
        user_prompt = (
            f"Slide {slide_index + 1}/{total_slides}.\n"
            f"Sujet : {outline_item.get('title', '')}\n"
            f"Thèmes à illustrer VISUELLEMENT (ne PAS copier en texte brut) :\n"
            + "\n".join(f"- {b}" for b in topics)
            + f"\n\nLayout précédent : {prev_layout or 'aucun'} (utilise un layout DIFFÉRENT)."
            + f"\n\nRAPPEL : suis le TEMPLATE OBLIGATOIRE ci-dessous. Ne génère PAS de bullet_group ni de texte seul."
        )

        # Inject full outline context (so each slide knows the full presentation plan)
        if full_outline_context:
            user_prompt += "\n" + OUTLINE_CONTEXT_SECTION.format(
                outline_context=full_outline_context,
                slide_number=slide_index + 1,
                total_slides=total_slides,
            )

        # Inject template hint
        user_prompt += "\n" + get_template_hint_for_prompt(suggestion)

        # Inject suggested icons
        if suggested_icons:
            user_prompt += f"\nIcônes recommandées : {', '.join(suggested_icons)}"

        # Inject user instruction (highest priority)
        if user_instruction:
            user_prompt += "\n" + USER_INSTRUCTION_SECTION.format(
                instruction=user_instruction,
            )

        # Inject current content for regeneration
        if current_content:
            truncated = json.dumps(current_content, ensure_ascii=False)[:1500]
            user_prompt += "\n" + CURRENT_CONTENT_SECTION.format(
                current_content=truncated,
            )

        # 5. Generate (using Mistral Large for quality)
        raw = await self._tracked_llm_call(
            db=db,
            tenant_id=tenant_id,
            presentation_id=presentation_id,
            slide_id=None,
            purpose=RunPurpose.SLIDE_GEN.value if not user_instruction else RunPurpose.REGENERATE.value,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=6144,  # Increased for complex slides
            model=self.slide_model,
        )

        # 6. Validate schema
        result, errors = self._validate_slide_json(raw)
        if result:
            # 7. Design normalization (LLM proposes, engine civilizes)
            result = normalize_slide(result, template=template_obj, theme=theme_data)
            return result

        # 8. Repair loop
        current_raw = raw
        for attempt in range(MAX_REPAIR_ATTEMPTS):
            logger.warning(
                f"Slide {slide_index} validation failed (attempt {attempt + 1}), "
                f"repairing: {errors[:200]}"
            )

            repair_prompt = REPAIR_USER_TEMPLATE.format(
                raw_json=current_raw[:3000],
                validation_errors=errors,
            )

            repaired = await self._tracked_llm_call(
                db=db,
                tenant_id=tenant_id,
                presentation_id=presentation_id,
                slide_id=None,
                purpose=RunPurpose.REPAIR.value,
                system_prompt=REPAIR_SYSTEM_PROMPT,
                user_prompt=repair_prompt,
            )

            result, errors = self._validate_slide_json(repaired)
            if result:
                result = normalize_slide(result, template=template_obj, theme=theme_data)
                return result
            current_raw = repaired

        # 9. Premium safe fallback (never a bare bullet_group)
        logger.error(
            f"Slide {slide_index} repair failed after {MAX_REPAIR_ATTEMPTS} attempts, "
            f"using safe template '{suggestion.template_id}'"
        )
        fallback = get_safe_fallback(outline_item, slide_index, total_slides)
        return normalize_slide(fallback, template=template_obj, theme=theme_data)

    def _validate_slide_json(self, raw: str) -> tuple[dict | None, str]:
        """Parse and validate slide JSON. Returns (data, errors)."""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            repaired = _repair_truncated_json(raw)
            if repaired:
                parsed = repaired
            else:
                return None, f"JSONDecodeError: invalid JSON"

        try:
            validated = SlideContent.model_validate(parsed)
            return validated.model_dump(), ""
        except ValidationError as e:
            return None, str(e)[:1000]

    def _parse_json(self, raw: str) -> dict | None:
        """Parse JSON with truncation repair."""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return _repair_truncated_json(raw)


# Singleton
presentation_service = PresentationService()
