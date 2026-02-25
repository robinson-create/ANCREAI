"""Layout resolution: convert Plate JSON slides to absolute bounding boxes.

All dimensions are in INCHES (the native unit for pptxgenjs / python-pptx).

Conversions:
  - px → inches : px / 96
  - pt → inches : pt / 72
  - inches → pt  : inches * 72
  - px → pt      : px * 0.75
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ── Constants ──

PT_PER_PX = 72 / 96  # 0.75

# Font metrics approximation (Inter). Measured empirically.
# font_size_pt → (avg_char_width_inches, line_height_inches)
FONT_METRICS: dict[int, tuple[float, float]] = {
    36: (0.30, 0.60),   # h1
    28: (0.23, 0.47),   # h2
    22: (0.18, 0.38),   # h3
    18: (0.15, 0.32),   # h4
    16: (0.13, 0.28),   # body / p
    14: (0.12, 0.25),   # small
    12: (0.10, 0.22),   # caption
    10: (0.09, 0.20),   # min font
}

# Default font sizes for node types
NODE_FONT_SIZES: dict[str, int] = {
    "h1": 36,
    "h2": 28,
    "h3": 22,
    "h4": 18,
    "h5": 16,
    "h6": 14,
    "p": 16,
    "bullet_item": 16,
}

MIN_FONT_SIZE = 10
SHRINK_STEP = 2


# ── Data classes ──


@dataclass
class PageSize:
    width: float = 10.0       # inches (16:9 standard)
    height: float = 5.625     # inches
    margin: float = 0.5       # inches

    @property
    def content_w(self) -> float:
        return self.width - 2 * self.margin

    @property
    def content_h(self) -> float:
        return self.height - 2 * self.margin


@dataclass
class ResolvedBox:
    """Absolute bounding box in inches, ready for pptxgenjs."""

    x: float
    y: float
    w: float
    h: float
    node_type: str  # text | image | shape | chart | svg
    content: dict = field(default_factory=dict)
    font_size_pt: int | None = None  # Final font size after shrink
    truncated: bool = False


# ── Text fitting ──


def _get_metrics(font_size_pt: int) -> tuple[float, float]:
    """Get (char_width, line_height) for a font size, interpolating if needed."""
    if font_size_pt in FONT_METRICS:
        return FONT_METRICS[font_size_pt]
    # Find nearest
    sizes = sorted(FONT_METRICS.keys())
    if font_size_pt <= sizes[0]:
        return FONT_METRICS[sizes[0]]
    if font_size_pt >= sizes[-1]:
        return FONT_METRICS[sizes[-1]]
    # Linear interpolation
    for i in range(len(sizes) - 1):
        if sizes[i] <= font_size_pt <= sizes[i + 1]:
            ratio = (font_size_pt - sizes[i]) / (sizes[i + 1] - sizes[i])
            lo = FONT_METRICS[sizes[i]]
            hi = FONT_METRICS[sizes[i + 1]]
            return (
                lo[0] + (hi[0] - lo[0]) * ratio,
                lo[1] + (hi[1] - lo[1]) * ratio,
            )
    return FONT_METRICS[16]  # fallback


def estimate_text_height(text: str, font_size_pt: int,
                         available_width: float) -> float:
    """Estimate wrapped text height in inches."""
    char_w, line_h = _get_metrics(font_size_pt)
    chars_per_line = max(1, int(available_width / char_w))
    num_lines = max(1, math.ceil(len(text) / chars_per_line))
    return num_lines * line_h


def fit_text_to_box(text: str, font_size_pt: int, box_h: float,
                    box_w: float) -> tuple[str, int, bool]:
    """Shrink font then truncate to fit text in box.

    Returns (adjusted_text, final_font_size, was_truncated).
    """
    current_size = font_size_pt
    truncated = False

    # Step 1: shrink font
    while current_size >= MIN_FONT_SIZE:
        h = estimate_text_height(text, current_size, box_w)
        if h <= box_h:
            return text, current_size, False
        current_size -= SHRINK_STEP

    current_size = max(current_size, MIN_FONT_SIZE)

    # Step 2: truncate
    char_w, line_h = _get_metrics(current_size)
    chars_per_line = max(1, int(box_w / char_w))
    max_lines = max(1, int(box_h / line_h))
    max_chars = chars_per_line * max_lines - 3
    if len(text) > max_chars and max_chars > 0:
        text = text[:max_chars] + "..."
        truncated = True

    return text, current_size, truncated


# ── Node helpers ──


def _extract_text(node: dict) -> str:
    """Recursively extract plain text from a Plate node."""
    if "text" in node:
        return node["text"]
    children = node.get("children", [])
    return " ".join(_extract_text(c) for c in children if isinstance(c, dict))


def _classify_node(node: dict) -> str:
    """Classify a Plate node into export categories."""
    t = node.get("type", "p")
    if t in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
        return "text"
    if t == "img":
        return "image"
    if t.endswith("_chart"):
        return "chart"
    if t in ("bullet_group", "bullet_item", "timeline_group", "pyramid_group",
             "staircase_group", "cycle_group", "arrow_list", "box_group",
             "compare_group", "before_after_group", "pros_cons_group",
             "sequence_arrow_group", "icon_list"):
        return "text"  # Complex layouts rendered as text in MVP
    return "text"


def _node_font_size(node: dict) -> int:
    """Get default font size for a node type."""
    return NODE_FONT_SIZES.get(node.get("type", "p"), 16)


def _estimate_node_height(node: dict, available_width: float) -> float:
    """Estimate the height of a single node in inches."""
    t = node.get("type", "p")
    text = _extract_text(node)

    if t.endswith("_chart"):
        return 2.5  # Fixed chart height

    if t == "bullet_group":
        children = node.get("children", [])
        total = 0.0
        for child in children:
            child_text = _extract_text(child)
            total += estimate_text_height(child_text, 16, available_width) + 0.1
        return max(total, 0.5)

    if t == "img":
        return 2.0  # Default inline image height

    font_size = _node_font_size(node)
    return estimate_text_height(text, font_size, available_width)


# ── Layout zones ──


def _compute_zones(
    layout_type: str, page: PageSize
) -> tuple[tuple[float, float, float, float] | None, tuple[float, float, float, float]]:
    """Compute (image_zone, text_zone) as (x, y, w, h) tuples.

    Returns (None, text_zone) if no image zone.
    """
    m = page.margin
    cw = page.content_w
    ch = page.content_h

    if layout_type == "left":
        img = (m, m, cw * 0.42, ch)
        txt = (m + cw * 0.45, m, cw * 0.55, ch)
    elif layout_type == "right":
        txt = (m, m, cw * 0.55, ch)
        img = (m + cw * 0.58, m, cw * 0.42, ch)
    elif layout_type == "background":
        img = (0, 0, page.width, page.height)
        txt = (m * 1.5, m * 1.5, cw * 0.7, ch * 0.7)  # Smaller text area on bg
    else:  # vertical (default)
        img = (m, m, cw, ch * 0.38)
        txt = (m, m + ch * 0.42, cw, ch * 0.58)

    return img, txt


# ── Main resolver ──


def resolve_layout(
    theme: dict,
    slide: dict,
    page: PageSize | None = None,
) -> list[ResolvedBox]:
    """Transform a slide (Plate JSON + layout_type + root_image) into absolute boxes.

    Args:
        theme: Theme data dict with colors, fonts.
        slide: Dict with keys: content_json, layout_type, root_image, bg_color.
        page: Page dimensions (defaults to 16:9).

    Returns:
        List of ResolvedBox with absolute positions in inches.
    """
    if page is None:
        page = PageSize()

    layout_type = slide.get("layout_type", "vertical")
    content_nodes = slide.get("content_json", [])
    root_image = slide.get("root_image")

    boxes: list[ResolvedBox] = []

    img_zone, txt_zone = _compute_zones(layout_type, page)

    # Background color box
    bg_color = slide.get("bg_color")
    if bg_color:
        boxes.append(ResolvedBox(
            x=0, y=0, w=page.width, h=page.height,
            node_type="shape",
            content={"fill": bg_color},
        ))

    # Root image box
    if root_image and img_zone and root_image.get("asset_id"):
        boxes.append(ResolvedBox(
            x=img_zone[0], y=img_zone[1], w=img_zone[2], h=img_zone[3],
            node_type="image",
            content=root_image,
        ))

    # Content nodes — stack vertically in text zone
    tx, ty, tw, th = txt_zone
    y_cursor = ty
    gap = 0.1  # inches between nodes
    remaining_h = th

    for node in content_nodes:
        if not isinstance(node, dict):
            continue

        est_h = _estimate_node_height(node, tw)
        node_h = min(est_h, remaining_h)

        if node_h <= 0:
            break

        node_type = _classify_node(node)
        font_size = _node_font_size(node) if node_type == "text" else None

        box = ResolvedBox(
            x=tx, y=y_cursor, w=tw, h=node_h,
            node_type=node_type,
            content=node,
            font_size_pt=font_size,
        )
        boxes.append(box)

        y_cursor += node_h + gap
        remaining_h -= (node_h + gap)

    return boxes
