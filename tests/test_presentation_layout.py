"""Tests for presentation layout resolver and schema validation."""

import pytest
from pydantic import ValidationError

from app.services.presentation_layout import (
    PageSize,
    ResolvedBox,
    estimate_text_height,
    fit_text_to_box,
    resolve_layout,
    _get_metrics,
    _extract_text,
    _classify_node,
    _compute_zones,
)
from app.schemas.presentation import (
    SlideContent,
    SlideNode,
    TextLeaf,
    OutlineItem,
    ThemeData,
    RootImage,
    CropSettings,
)


# ─── PageSize ────────────────────────────────────────────────────────────────


class TestPageSize:
    def test_default_16_9(self):
        p = PageSize()
        assert p.width == 10.0
        assert p.height == 5.625
        assert p.margin == 0.5

    def test_content_dimensions(self):
        p = PageSize()
        assert p.content_w == pytest.approx(9.0)
        assert p.content_h == pytest.approx(4.625)

    def test_custom_size(self):
        p = PageSize(width=13.333, height=7.5, margin=0.75)
        assert p.content_w == pytest.approx(11.833)
        assert p.content_h == pytest.approx(6.0)


# ─── Font Metrics ────────────────────────────────────────────────────────────


class TestFontMetrics:
    def test_exact_lookup(self):
        cw, lh = _get_metrics(16)
        assert cw == 0.13
        assert lh == 0.28

    def test_interpolation(self):
        cw, lh = _get_metrics(20)
        # 20 is between 18 and 22
        assert 0.15 < cw < 0.18
        assert 0.32 < lh < 0.38

    def test_below_minimum(self):
        cw, lh = _get_metrics(6)
        assert cw == 0.09  # Clamps to 10pt metrics
        assert lh == 0.20

    def test_above_maximum(self):
        cw, lh = _get_metrics(72)
        assert cw == 0.30  # Clamps to 36pt metrics
        assert lh == 0.60


# ─── Text Height Estimation ──────────────────────────────────────────────────


class TestEstimateTextHeight:
    def test_short_text(self):
        h = estimate_text_height("Hello", 16, 5.0)
        assert h == pytest.approx(0.28)

    def test_wrapping(self):
        text = "A" * 100  # 100 chars
        h = estimate_text_height(text, 16, 5.0)
        # 5.0 / 0.13 ≈ 38 chars per line → ~3 lines → ~0.84
        assert h > 0.28
        assert h < 1.5

    def test_empty_text(self):
        h = estimate_text_height("", 16, 5.0)
        assert h >= 0.28  # At least 1 line


# ─── Fit Text to Box ─────────────────────────────────────────────────────────


class TestFitTextToBox:
    def test_fits_without_changes(self):
        text, size, truncated = fit_text_to_box("Short text", 16, 1.0, 5.0)
        assert text == "Short text"
        assert size == 16
        assert truncated is False

    def test_shrinks_font(self):
        long_text = "A" * 500
        text, size, truncated = fit_text_to_box(long_text, 36, 1.0, 5.0)
        assert size < 36  # Must have shrunk

    def test_truncates_when_cannot_shrink_enough(self):
        huge_text = "A" * 5000
        text, size, truncated = fit_text_to_box(huge_text, 36, 0.5, 3.0)
        assert truncated is True
        assert text.endswith("...")
        assert size >= 10  # MIN_FONT_SIZE


# ─── Node Helpers ─────────────────────────────────────────────────────────────


class TestExtractText:
    def test_flat_text(self):
        assert _extract_text({"text": "hello"}) == "hello"

    def test_nested_children(self):
        node = {
            "type": "p",
            "children": [
                {"text": "hello"},
                {"text": " world"},
            ],
        }
        assert _extract_text(node) == "hello  world"

    def test_deep_nesting(self):
        node = {
            "type": "h1",
            "children": [
                {
                    "type": "span",
                    "children": [{"text": "deep"}],
                }
            ],
        }
        assert "deep" in _extract_text(node)


class TestClassifyNode:
    def test_headings(self):
        for h in ("h1", "h2", "h3", "h4", "h5", "h6"):
            assert _classify_node({"type": h}) == "text"

    def test_paragraph(self):
        assert _classify_node({"type": "p"}) == "text"

    def test_image(self):
        assert _classify_node({"type": "img"}) == "image"

    def test_chart(self):
        assert _classify_node({"type": "bar_chart"}) == "chart"

    def test_bullet_group(self):
        assert _classify_node({"type": "bullet_group"}) == "text"

    def test_default_fallback(self):
        assert _classify_node({"type": "unknown_thing"}) == "text"


# ─── Compute Zones ───────────────────────────────────────────────────────────


class TestComputeZones:
    def test_vertical_layout(self):
        page = PageSize()
        img, txt = _compute_zones("vertical", page)
        assert img is not None
        assert txt[2] == pytest.approx(page.content_w)

    def test_left_layout(self):
        page = PageSize()
        img, txt = _compute_zones("left", page)
        assert img is not None
        assert img[0] == page.margin  # Image on left starts at margin

    def test_right_layout(self):
        page = PageSize()
        img, txt = _compute_zones("right", page)
        assert img is not None
        assert txt[0] == page.margin  # Text on left starts at margin

    def test_background_layout(self):
        page = PageSize()
        img, txt = _compute_zones("background", page)
        assert img is not None
        assert img[0] == 0  # Full-page image
        assert img[2] == page.width


# ─── Resolve Layout (Integration) ────────────────────────────────────────────


class TestResolveLayout:
    def _make_slide(self, nodes, layout_type="vertical", bg_color=None, root_image=None):
        return {
            "content_json": nodes,
            "layout_type": layout_type,
            "bg_color": bg_color,
            "root_image": root_image,
        }

    def test_empty_slide(self):
        slide = self._make_slide([])
        boxes = resolve_layout({}, slide)
        assert boxes == []

    def test_bg_color_creates_shape(self):
        slide = self._make_slide([], bg_color="#FF0000")
        boxes = resolve_layout({}, slide)
        assert len(boxes) == 1
        assert boxes[0].node_type == "shape"
        assert boxes[0].content["fill"] == "#FF0000"
        assert boxes[0].w == 10.0  # Full page width

    def test_root_image_creates_image_box(self):
        slide = self._make_slide(
            [],
            layout_type="left",
            root_image={"asset_id": "abc-123", "query": "cat"},
        )
        boxes = resolve_layout({}, slide)
        assert len(boxes) == 1
        assert boxes[0].node_type == "image"

    def test_text_nodes_stacked_vertically(self):
        nodes = [
            {"type": "h1", "children": [{"text": "Title"}]},
            {"type": "p", "children": [{"text": "Paragraph content here"}]},
        ]
        slide = self._make_slide(nodes)
        boxes = resolve_layout({}, slide)
        # bg=none, rootImage=none → only text boxes
        text_boxes = [b for b in boxes if b.node_type == "text"]
        assert len(text_boxes) == 2
        # Second box is below the first
        assert text_boxes[1].y > text_boxes[0].y

    def test_complete_slide(self):
        nodes = [
            {"type": "h2", "children": [{"text": "Heading"}]},
            {"type": "p", "children": [{"text": "Some content"}]},
        ]
        slide = self._make_slide(
            nodes,
            layout_type="right",
            bg_color="#1a1a2e",
            root_image={"asset_id": "img-1"},
        )
        boxes = resolve_layout({}, slide)
        types = [b.node_type for b in boxes]
        assert "shape" in types     # bg color
        assert "image" in types     # root image
        assert "text" in types      # content

    def test_custom_page_size(self):
        nodes = [{"type": "p", "children": [{"text": "test"}]}]
        slide = self._make_slide(nodes)
        page = PageSize(width=13.333, height=7.5, margin=1.0)
        boxes = resolve_layout({}, slide, page)
        for box in boxes:
            assert box.x >= 0
            assert box.y >= 0
            assert box.x + box.w <= page.width + 0.01
            assert box.y + box.h <= page.height + 0.01


# ─── Pydantic Schema Validation ──────────────────────────────────────────────


class TestSlideContentValidation:
    def test_minimal_valid(self):
        sc = SlideContent()
        assert sc.content_json == []
        assert sc.layout_type == "vertical"

    def test_full_valid(self):
        sc = SlideContent(
            content_json=[
                SlideNode(
                    type="h1",
                    children=[TextLeaf(text="Title", bold=True)],
                ),
                SlideNode(
                    type="p",
                    children=[TextLeaf(text="Body text")],
                ),
            ],
            layout_type="left",
            root_image=RootImage(asset_id="abc", query="cat"),
            bg_color="#FFFFFF",
        )
        assert len(sc.content_json) == 2
        assert sc.content_json[0].type == "h1"

    def test_nested_bullet_group(self):
        sc = SlideContent(
            content_json=[
                SlideNode(
                    type="bullet_group",
                    children=[
                        SlideNode(
                            type="bullet_item",
                            children=[
                                SlideNode(type="p", children=[TextLeaf(text="Item 1")]),
                            ],
                        ),
                    ],
                ),
            ],
        )
        assert sc.content_json[0].type == "bullet_group"


class TestOutlineItem:
    def test_valid(self):
        item = OutlineItem(title="Introduction", bullets=["Point A", "Point B"])
        assert item.title == "Introduction"
        assert len(item.bullets) == 2

    def test_empty_bullets(self):
        item = OutlineItem(title="Conclusion")
        assert item.bullets == []


class TestThemeData:
    def test_defaults(self):
        td = ThemeData()
        assert td.colors.primary == "#6C63FF"
        assert td.fonts.heading == "Inter"
        assert td.border_radius == "12px"

    def test_custom_colors(self):
        from app.schemas.presentation import ThemeColors
        td = ThemeData(
            colors=ThemeColors(primary="#000000", text="#FFFFFF"),
        )
        assert td.colors.primary == "#000000"
        assert td.colors.text == "#FFFFFF"
        assert td.colors.secondary == "#2D2B55"  # Default preserved


class TestCropSettings:
    def test_defaults(self):
        cs = CropSettings()
        assert cs.object_fit == "cover"
        assert cs.object_position == {"x": 50, "y": 50}

    def test_custom(self):
        cs = CropSettings(object_fit="contain", zoom=1.5)
        assert cs.zoom == 1.5
