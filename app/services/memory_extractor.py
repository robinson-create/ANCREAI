"""Structured memory extraction from conversations (JSON format).

Invariants:
- #1: NEVER index raw Q/A — only structured summaries
- #2: Always use extraction prompt forcing objectives/decisions/constraints
- #3: Every chunk gets explicit source_type='conversation_summary'
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings
from app.services.memory_prompts import MEMORY_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)
settings = get_settings()

MEMORY_CATEGORIES = ("goals", "decisions", "constraints", "facts", "hypotheses", "preferences")


def _parse_memory_json(raw: str) -> dict[str, list[str]] | None:
    """Parse LLM response as structured memory JSON.

    Returns None if empty or unparseable.
    """
    text = raw.strip()
    if not text or text == "{}":
        return None

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("memory_extraction_json_parse_failed", extra={"raw": text[:200]})
        return None

    if not isinstance(data, dict):
        return None

    # Keep only known categories with non-empty lists
    result: dict[str, list[str]] = {}
    for key in MEMORY_CATEGORIES:
        if key in data and isinstance(data[key], list) and data[key]:
            result[key] = [str(item) for item in data[key] if item]

    return result if result else None


def memory_to_indexable_text(memory: dict[str, list[str]]) -> str:
    """Convert structured memory JSON to indexable text for FTS + embeddings.

    Each category becomes a section header with bullet points.
    This is what gets chunked and embedded — not the raw JSON.
    """
    category_labels = {
        "goals": "Objectifs",
        "decisions": "Décisions",
        "constraints": "Contraintes",
        "facts": "Données factuelles",
        "hypotheses": "Hypothèses",
        "preferences": "Préférences stables",
    }

    sections = []
    for key in MEMORY_CATEGORIES:
        items = memory.get(key, [])
        if items:
            label = category_labels.get(key, key)
            lines = [f"- {item}" for item in items]
            sections.append(f"## {label}\n" + "\n".join(lines))

    return "\n\n".join(sections)


async def extract_memory(transcript: str) -> dict[str, Any] | None:
    """Extract structured memory from a conversation transcript.

    Returns a dict with:
    - "structured": the parsed JSON dict (categories → lists)
    - "text": the indexable text version for FTS + embeddings

    Returns None if the conversation contains no exploitable information.
    """
    if not transcript or not transcript.strip():
        return None

    client = AsyncOpenAI(
        api_key=settings.mistral_api_key,
        base_url="https://api.mistral.ai/v1",
    )

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
            {"role": "user", "content": transcript},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content or ""

    structured = _parse_memory_json(raw)
    if not structured:
        return None

    text = memory_to_indexable_text(structured)
    if not text.strip():
        return None

    return {"structured": structured, "text": text}
