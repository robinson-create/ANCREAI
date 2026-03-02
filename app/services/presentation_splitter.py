"""Auto-split dense briefs into multiple slides.

If a brief has too many blocks or text is too long,
it's better to produce 2 good slides than 1 cramped one.
"""

from __future__ import annotations

import logging

from app.services.presentation_briefs import NarrativeRole, SlideBlock, SlideBrief

logger = logging.getLogger(__name__)

# Thresholds
MAX_BLOCKS_BEFORE_SPLIT = 9
MAX_AVG_BODY_CHARS_DENSE = 450  # Templates now support ~400-500 char bodies
MIN_BLOCKS_FOR_DENSE_SPLIT = 7  # More blocks before dense-split triggers

# Rule 3 thresholds — hybrid volume-based split
MAX_TOTAL_BODY_CHARS = 3500        # Absolute total (raised for richer content)
DENSE_AVG_BODY_THRESHOLD = 600     # High per-block average
DENSE_MIN_BLOCKS = 4               # Minimum blocks for avg-based split
SINGLE_BLOCK_MAX_BODY = 800        # Single block too large


def maybe_split_brief(brief: SlideBrief) -> list[SlideBrief]:
    """Split a brief if it's too dense for a single slide.

    Returns a list of 1 or 2 briefs.
    """
    # Never split cover, closing, quote, or big_statement roles
    if brief.narrative_role in (
        NarrativeRole.COVER,
        NarrativeRole.CLOSING,
        NarrativeRole.HOOK,
    ):
        return [brief]

    block_count = len(brief.blocks)

    # Rule 1: Too many blocks
    if block_count > MAX_BLOCKS_BEFORE_SPLIT:
        logger.info(
            "Splitting brief '%s': %d blocks > %d max",
            brief.title, block_count, MAX_BLOCKS_BEFORE_SPLIT,
        )
        return _split_by_blocks(brief)

    # Rule 2: Dense text with many blocks (≥6)
    if block_count >= MIN_BLOCKS_FOR_DENSE_SPLIT:
        avg_body = _avg_body_length(brief.blocks)
        if avg_body > MAX_AVG_BODY_CHARS_DENSE:
            logger.info(
                "Splitting brief '%s': avg body %d chars > %d threshold with %d blocks",
                brief.title, avg_body, MAX_AVG_BODY_CHARS_DENSE, block_count,
            )
            return _split_by_blocks(brief)

    # Rule 3: Volume-based hybrid split (handles 3-5 dense blocks)
    if block_count >= 2:
        total_body = sum(len(b.body) for b in brief.blocks)
        avg_body = total_body / block_count if block_count else 0
        max_body = max((len(b.body) for b in brief.blocks), default=0)

        should_split = False
        reason = ""

        # 3a: Total body exceeds single-slide capacity
        if total_body > MAX_TOTAL_BODY_CHARS:
            should_split = True
            reason = f"total body {total_body} > {MAX_TOTAL_BODY_CHARS}"

        # 3b: High average with enough blocks
        elif avg_body > DENSE_AVG_BODY_THRESHOLD and block_count >= DENSE_MIN_BLOCKS:
            should_split = True
            reason = f"avg body {avg_body:.0f} > {DENSE_AVG_BODY_THRESHOLD} with {block_count} blocks"

        # 3c: Single block too dense
        elif max_body > SINGLE_BLOCK_MAX_BODY:
            should_split = True
            reason = f"max body {max_body} > {SINGLE_BLOCK_MAX_BODY}"

        if should_split:
            logger.info("Splitting brief '%s': %s", brief.title, reason)
            return _split_by_blocks(brief)

    return [brief]


def _split_by_blocks(brief: SlideBrief) -> list[SlideBrief]:
    """Split blocks roughly in half, producing 2 briefs."""
    blocks = brief.blocks
    mid = len(blocks) // 2

    first_blocks = blocks[:mid]
    second_blocks = blocks[mid:]

    first = SlideBrief(
        slide_goal=brief.slide_goal,
        narrative_role=brief.narrative_role,
        key_message=brief.key_message,
        title=brief.title,
        subtitle=brief.subtitle,
        density_target=_reduce_density(brief.density_target),
        preferred_visual=brief.preferred_visual,
        blocks=first_blocks,
        asset_need=brief.asset_need,
        proof_level=brief.proof_level,
    )

    second = SlideBrief(
        slide_goal=brief.slide_goal,
        narrative_role=brief.narrative_role,
        key_message=brief.key_message,
        title=f"{brief.title} (suite)",
        subtitle=None,
        density_target=_reduce_density(brief.density_target),
        preferred_visual=brief.preferred_visual,
        blocks=second_blocks,
        asset_need=brief.asset_need,
        proof_level=brief.proof_level,
    )

    return [first, second]


def _avg_body_length(blocks: list[SlideBlock]) -> int:
    """Average body length in characters."""
    if not blocks:
        return 0
    total = sum(len(b.body) for b in blocks)
    return total // len(blocks)


def _reduce_density(density: str) -> str:
    """Reduce density target after split."""
    if density == "high":
        return "medium"
    return density
