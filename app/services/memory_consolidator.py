"""Periodic memory consolidation — structured JSON merge.

Invariant #6: Without consolidation, memory degrades over time
(redundancy, conflicts, decreasing relevance).
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings
from app.services.memory_prompts import MEMORY_CONSOLIDATION_PROMPT
from app.services.memory_extractor import (
    _parse_memory_json,
    memory_to_indexable_text,
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def consolidate_memories(summaries: list[dict[str, list[str]]]) -> dict[str, Any] | None:
    """Consolidate multiple structured memory dicts into one.

    Takes a list of parsed memory dicts (category → list[str]) and produces
    a single merged, deduplicated, conflict-resolved memory.

    Returns a dict with:
    - "structured": the consolidated JSON dict
    - "text": the indexable text version

    Returns None if input is empty or consolidation produces nothing.
    """
    if not summaries:
        return None

    # Format each memory as numbered JSON for the LLM
    parts = []
    for i, mem in enumerate(summaries):
        parts.append(f"[Mémoire {i + 1}]\n{json.dumps(mem, ensure_ascii=False, indent=2)}")

    combined = "\n\n---\n\n".join(parts)

    client = AsyncOpenAI(
        api_key=settings.mistral_api_key,
        base_url="https://api.mistral.ai/v1",
    )

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": MEMORY_CONSOLIDATION_PROMPT},
            {"role": "user", "content": combined},
        ],
        temperature=0.3,
        max_tokens=3000,
    )

    raw = response.choices[0].message.content or ""

    structured = _parse_memory_json(raw)
    if not structured:
        return None

    text = memory_to_indexable_text(structured)
    if not text.strip():
        return None

    return {"structured": structured, "text": text}
