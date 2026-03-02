"""XML-to-SlideNode parser for presentation generation.

Converts LLM-generated XML (presentation-ai format) into ancre-ai's
SlideNode dict format. Deterministic conversion — no LLM involved.

The XML format uses <SECTION layout="..."> tags for slides, with nested
component tags (BOXES, STATS, TIMELINE, etc.) that map to SlideNode types.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Valid layout types ──

VALID_LAYOUTS = frozenset(
    ["left", "right", "vertical", "left-fit", "right-fit", "accent-top", "background"]
)


# ── XML Node ──


@dataclass
class XMLNode:
    """Parsed XML element."""

    tag: str
    attributes: dict[str, str] = field(default_factory=dict)
    content: str = ""
    children: list[XMLNode] = field(default_factory=list)
    original_tag: str = ""  # raw tag string for query validation


# ── Helpers ──


def _get_text_content(node: XMLNode, trim: bool = True) -> str:
    """Recursively extract all text content from an XMLNode."""
    text = node.content.strip() if trim else node.content
    for child in node.children:
        text += _get_text_content(child, trim=False)
    return _unescape_xml_entities(text)


def _get_text_descendants(node: XMLNode) -> list[dict]:
    """Extract text descendants with inline formatting (bold/italic/underline)."""
    descendants: list[dict] = []

    if node.content:
        descendants.append({"text": _unescape_xml_entities(node.content)})

    for child in node.children:
        tag = child.tag.upper()
        if tag in ("B", "STRONG"):
            content = _get_text_content(child, trim=False)
            if content:
                descendants.append({"text": _unescape_xml_entities(content), "bold": True})
        elif tag in ("I", "EM"):
            content = _get_text_content(child, trim=False)
            if content:
                descendants.append({"text": _unescape_xml_entities(content), "italic": True})
        elif tag in ("U",):
            content = _get_text_content(child, trim=False)
            if content:
                descendants.append({"text": _unescape_xml_entities(content), "underline": True})
        elif tag in ("S", "STRIKE"):
            content = _get_text_content(child, trim=False)
            if content:
                descendants.append({"text": _unescape_xml_entities(content)})
        else:
            # Recurse for nested elements (H3 inside P, etc.)
            processed = _process_node(child)
            if processed:
                descendants.append(processed)

    # Clean empty text nodes
    cleaned = [d for d in descendants if not (isinstance(d.get("text"), str) and d["text"] == "")]

    return cleaned if cleaned else [{"text": ""}]


# ── Node processors ──


def _make_heading(tag: str, node: XMLNode) -> dict:
    return {"type": tag.lower(), "children": _get_text_descendants(node)}


def _make_paragraph(node: XMLNode) -> dict:
    return {"type": "p", "children": _get_text_descendants(node)}


def _make_image(node: XMLNode) -> dict | None:
    """Create img node from <IMG query="..."> — returns None if query incomplete."""
    query = node.attributes.get("query", "").strip()
    if not query or len(query) < 3:
        return None
    url = node.attributes.get("url") or node.attributes.get("src") or ""
    result: dict[str, Any] = {"type": "img", "query": query, "children": [{"text": ""}]}
    if url:
        result["url"] = url
    return result


def _make_icon(node: XMLNode) -> dict | None:
    """Create icon node from <ICON query="...">."""
    query = node.attributes.get("query", "").strip()
    if not query or len(query) < 2:
        return None
    return {"type": "icon", "query": query, "icon_role": "card", "children": [{"text": ""}]}


def _process_div_children(node: XMLNode) -> list[dict]:
    """Process children of a DIV into a list of SlideNode dicts."""
    results: list[dict] = []
    for child in node.children:
        processed = _process_node(child)
        if processed:
            results.append(processed)
    # If no children but has text content, create a paragraph
    if not results and node.content.strip():
        results.append({"type": "p", "children": [{"text": node.content.strip()}]})
    return results


def _make_group(
    node: XMLNode,
    group_type: str,
    item_type: str,
    *,
    use_variant: bool = False,
    default_variant: str = "",
) -> dict:
    """Generic group builder: processes DIV children as items."""
    items: list[dict] = []
    for child in node.children:
        if child.tag.upper() == "DIV":
            item_children = _process_div_children(child)
            item: dict[str, Any] = {"type": item_type, "children": item_children or [{"text": ""}]}
            # For stats_item, extract value attribute
            if item_type == "stats_item" and "value" in child.attributes:
                item["value"] = child.attributes["value"]
            items.append(item)

    result: dict[str, Any] = {"type": group_type, "children": items or [{"text": ""}]}
    if use_variant:
        result["variant"] = node.attributes.get("variant", default_variant)
    return result


def _make_boxes(node: XMLNode) -> dict:
    return _make_group(node, "box_group", "box_item", use_variant=True, default_variant="solid")


def _make_bullets(node: XMLNode) -> dict:
    return _make_group(
        node, "bullet_group", "bullet_item", use_variant=True, default_variant="numbered"
    )


def _make_icons(node: XMLNode) -> dict:
    """ICONS → icon_list with icon_list_item containing icon + h3 + p."""
    items: list[dict] = []
    for child in node.children:
        if child.tag.upper() == "DIV":
            item_children: list[dict] = []
            for sub in child.children:
                tag = sub.tag.upper()
                if tag == "ICON":
                    icon = _make_icon(sub)
                    if icon:
                        item_children.append(icon)
                else:
                    processed = _process_node(sub)
                    if processed:
                        item_children.append(processed)
            if not item_children and child.content.strip():
                item_children.append({"type": "p", "children": [{"text": child.content.strip()}]})
            items.append({"type": "icon_list_item", "children": item_children or [{"text": ""}]})

    return {"type": "icon_list", "children": items or [{"text": ""}]}


def _make_timeline(node: XMLNode) -> dict:
    return _make_group(
        node, "timeline_group", "timeline_item", use_variant=True, default_variant="default"
    )


def _make_cycle(node: XMLNode) -> dict:
    return _make_group(node, "cycle_group", "cycle_item")


def _make_staircase(node: XMLNode) -> dict:
    return _make_group(node, "staircase_group", "stair_item")


def _make_pyramid(node: XMLNode) -> dict:
    return _make_group(
        node, "pyramid_group", "pyramid_item", use_variant=True, default_variant="pyramid"
    )


def _make_arrows(node: XMLNode) -> dict:
    return _make_group(node, "arrow_list", "arrow_list_item")


def _make_arrow_vertical(node: XMLNode) -> dict:
    """ARROW-VERTICAL → staircase_group (closest visual equivalent)."""
    return _make_group(node, "staircase_group", "stair_item")


def _make_compare(node: XMLNode) -> dict:
    """COMPARE → compare_group with 2 compare_side."""
    sides: list[dict] = []
    for child in node.children:
        if child.tag.upper() == "DIV":
            side_children = _process_div_children(child)
            sides.append({"type": "compare_side", "children": side_children or [{"text": ""}]})
    return {"type": "compare_group", "children": sides or [{"text": ""}]}


def _make_before_after(node: XMLNode) -> dict:
    sides: list[dict] = []
    for child in node.children:
        if child.tag.upper() == "DIV":
            side_children = _process_div_children(child)
            sides.append(
                {"type": "before_after_side", "children": side_children or [{"text": ""}]}
            )
    return {"type": "before_after_group", "children": sides or [{"text": ""}]}


def _make_pros_cons(node: XMLNode) -> dict:
    children: list[dict] = []
    for child in node.children:
        tag = child.tag.upper()
        if tag == "PROS":
            inner = _process_div_children(child)
            children.append({"type": "pros_item", "children": inner or [{"text": ""}]})
        elif tag == "CONS":
            inner = _process_div_children(child)
            children.append({"type": "cons_item", "children": inner or [{"text": ""}]})
        elif tag == "DIV":
            # Alternating fallback
            item_type = "pros_item" if len(children) % 2 == 0 else "cons_item"
            inner = _process_div_children(child)
            children.append({"type": item_type, "children": inner or [{"text": ""}]})
    return {"type": "pros_cons_group", "children": children or [{"text": ""}]}


def _make_quote(node: XMLNode) -> dict:
    variant = node.attributes.get("variant", "large")
    children: list[dict] = []
    for child in node.children:
        processed = _process_node(child)
        if processed:
            children.append(processed)
    if not children and node.content.strip():
        children = [{"type": "p", "children": [{"text": node.content.strip()}]}]
    return {
        "type": "quote",
        "variant": variant,
        "children": children or [{"type": "p", "children": [{"text": ""}]}],
    }


def _make_stats(node: XMLNode) -> dict:
    variant = node.attributes.get("variant", "default")
    items: list[dict] = []
    for child in node.children:
        if child.tag.upper() == "DIV":
            value = child.attributes.get("value", "")
            item_children = _process_div_children(child)
            items.append({
                "type": "stats_item",
                "value": value,
                "variant": variant,
                "children": item_children or [{"type": "p", "children": [{"text": ""}]}],
            })
    return {
        "type": "stats_group",
        "variant": variant,
        "children": items or [{"text": ""}],
    }


def _make_chart(node: XMLNode) -> dict:
    """CHART → chart-{type} with data array."""
    chart_type = (node.attributes.get("charttype") or "bar").lower()
    data_nodes = [c for c in node.children if c.tag.upper() == "DATA"]

    data: list[dict] = []
    if chart_type in ("scatter", "heatmap"):
        for d in data_nodes:
            x_node = next((c for c in d.children if c.tag.upper() == "X"), None)
            y_node = next((c for c in d.children if c.tag.upper() == "Y"), None)
            x_val = _safe_float(x_node.content.strip() if x_node else d.attributes.get("x", "0"))
            y_val = _safe_float(y_node.content.strip() if y_node else d.attributes.get("y", "0"))
            data.append({"x": x_val, "y": y_val})
    else:
        for d in data_nodes:
            label_node = next((c for c in d.children if c.tag.upper() == "LABEL"), None)
            value_node = next((c for c in d.children if c.tag.upper() == "VALUE"), None)
            label = (
                label_node.content.strip()
                if label_node
                else d.attributes.get("label", d.attributes.get("name", ""))
            )
            value = _safe_float(
                value_node.content.strip()
                if value_node
                else d.attributes.get("value", "0")
            )
            data.append({"label": label, "value": value})

    element_type = f"chart-{chart_type}"
    return {"type": element_type, "data": data, "children": [{"text": ""}]}


def _make_table(node: XMLNode) -> dict:
    """TABLE → table with table_row and table_cell."""
    rows: list[dict] = []

    def parse_row(row_node: XMLNode) -> None:
        cells: list[dict] = []
        for cell_node in row_node.children:
            tag = cell_node.tag.upper()
            if tag in ("TD", "TH"):
                cell_children = _process_div_children(cell_node)
                if not cell_children:
                    cell_children = [{"type": "p", "children": [{"text": cell_node.content.strip()}]}]
                cells.append({"type": tag.lower(), "children": cell_children})
        if cells:
            rows.append({"type": "tr", "children": cells})

    # Handle THEAD
    for child in node.children:
        if child.tag.upper() == "THEAD":
            for row in child.children:
                if row.tag.upper() in ("TR", "ROW"):
                    parse_row(row)

    # Handle direct TR and TBODY
    for child in node.children:
        tag = child.tag.upper()
        if tag == "TBODY":
            for row in child.children:
                if row.tag.upper() in ("TR", "ROW"):
                    parse_row(row)
        elif tag in ("TR", "ROW"):
            parse_row(child)

    return {"type": "table", "children": rows or [{"text": ""}]}


def _make_image_gallery(node: XMLNode) -> dict:
    variant = node.attributes.get("variant", "3-col")
    items: list[dict] = []
    for child in node.children:
        if child.tag.upper() == "DIV":
            img_child = next((c for c in child.children if c.tag.upper() == "IMG"), None)
            query = img_child.attributes.get("query", "") if img_child else ""
            # Process non-IMG children as captions
            caption_children: list[dict] = []
            for sub in child.children:
                if sub.tag.upper() != "IMG":
                    processed = _process_node(sub)
                    if processed:
                        caption_children.append(processed)
            item: dict[str, Any] = {
                "type": "image_gallery_item",
                "query": query,
                "variant": variant,
                "children": caption_children or [{"type": "p", "children": [{"text": ""}]}],
            }
            items.append(item)

    return {
        "type": "image_gallery_group",
        "variant": variant,
        "children": items or [{"text": ""}],
    }


def _make_columns(node: XMLNode) -> list[dict]:
    """COLUMNS → flatten DIV children as top-level nodes (no column plugin in ancre-ai)."""
    results: list[dict] = []
    for child in node.children:
        if child.tag.upper() == "DIV":
            results.extend(_process_div_children(child))
    return results


# ── Badge ──


def _make_badge(node: XMLNode) -> dict:
    color = node.attributes.get("color", "primary")
    text = _get_text_content(node)
    return {
        "type": "badge",
        "color": color,
        "children": [{"text": text}],
    }


# ── LI handling ──


def _make_list_items(nodes: list[XMLNode]) -> list[dict]:
    """Convert consecutive <LI> elements into bullet_item dicts."""
    items: list[dict] = []
    for node in nodes:
        text = _get_text_content(node)
        items.append({
            "type": "bullet_item",
            "children": [{"type": "p", "children": [{"text": text}]}],
        })
    return items


# ── Node dispatch ──

_TOP_LEVEL_DISPATCH: dict[str, Any] = {}  # populated below


def _process_node(node: XMLNode) -> dict | None:
    """Process a single XMLNode into a SlideNode dict."""
    tag = node.tag.upper()

    if tag in ("H1", "H2", "H3", "H4", "H5", "H6"):
        return _make_heading(tag, node)
    if tag == "P":
        return _make_paragraph(node)
    if tag == "IMG":
        return _make_image(node)
    if tag == "ICON":
        return _make_icon(node)
    if tag == "LI":
        text = _get_text_content(node)
        return {"type": "p", "children": [{"text": text}]}

    # Group components
    handler = _TOP_LEVEL_DISPATCH.get(tag)
    if handler:
        return handler(node)

    logger.debug("Unknown XML tag: %s", tag)
    return None


def _process_top_level_node(node: XMLNode) -> list[dict]:
    """Process a top-level node inside a SECTION. Returns a list (COLUMNS expands to multiple)."""
    tag = node.tag.upper()

    if tag == "COLUMNS":
        return _make_columns(node)

    if tag == "DIV":
        return _process_div_children(node)

    result = _process_node(node)
    return [result] if result else []


# Populate dispatch table
_TOP_LEVEL_DISPATCH.update({
    "BOXES": _make_boxes,
    "BULLETS": _make_bullets,
    "ICONS": _make_icons,
    "TIMELINE": _make_timeline,
    "CYCLE": _make_cycle,
    "STAIRCASE": _make_staircase,
    "PYRAMID": _make_pyramid,
    "ARROWS": _make_arrows,
    "ARROW-VERTICAL": _make_arrow_vertical,
    "ARROWVERTICAL": _make_arrow_vertical,
    "ARROW_VERTICAL": _make_arrow_vertical,
    "VERTICAL-ARROWS": _make_arrow_vertical,
    "COMPARE": _make_compare,
    "BEFORE-AFTER": _make_before_after,
    "BEFOREAFTER": _make_before_after,
    "PROS-CONS": _make_pros_cons,
    "PROSCONS": _make_pros_cons,
    "QUOTE": _make_quote,
    "STATS": _make_stats,
    "CHART": _make_chart,
    "TABLE": _make_table,
    "IMAGE-GALLERY": _make_image_gallery,
    "IMAGEGALLERY": _make_image_gallery,
    "BADGE": _make_badge,
})


# ── XML Parser ──


def _safe_float(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _sanitize_xml_text(text: str) -> str:
    """Escape stray '<' characters that aren't part of valid XML tags.

    LLMs sometimes produce text like "< 2h" or "x < y" which breaks XML parsing.
    We keep valid tags (starting with a letter, '/', '!' or '?') and escape the rest.
    """
    # Valid XML tags start with: letter, /, !, ?
    # Replace '<' NOT followed by those with &lt;
    return re.sub(r"<(?![A-Za-z/!?])", "&lt;", text)


def _unescape_xml_entities(text: str) -> str:
    """Unescape common XML entities in text content."""
    return (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )


def _parse_xml(xml_string: str) -> XMLNode:
    """Hand-rolled XML parser that handles malformed LLM output gracefully."""
    root = XMLNode(tag="ROOT")
    # Strip PRESENTATION wrapper
    text = xml_string
    # Remove opening <PRESENTATION...>
    m = re.search(r"<PRESENTATION[^>]*>", text, re.IGNORECASE)
    if m:
        text = text[: m.start()] + text[m.end() :]
    text = re.sub(r"</PRESENTATION\s*>", "", text, flags=re.IGNORECASE)

    # Sanitize stray '<' characters that aren't tags
    text = _sanitize_xml_text(text)

    _parse_element(text, root)
    return root


def _parse_element(xml: str, parent: XMLNode) -> None:
    """Recursively parse XML string into parent node's children."""
    idx = 0
    length = len(xml)

    while idx < length:
        # Find next tag
        tag_start = xml.find("<", idx)
        if tag_start == -1:
            parent.content += xml[idx:]
            break

        # Text before tag
        if tag_start > idx:
            parent.content += xml[idx:tag_start]

        # Find tag end
        tag_end = xml.find(">", tag_start)
        if tag_end == -1:
            parent.content += xml[tag_start:]
            break

        tag_content = xml[tag_start + 1 : tag_end]

        # Closing tag
        if tag_content.startswith("/"):
            closing_tag = tag_content[1:].strip()
            if closing_tag.upper() == parent.tag.upper():
                idx = tag_end + 1
                break
            else:
                idx = tag_end + 1
                continue

        # Comment
        if tag_content.startswith("!--"):
            comment_end = xml.find("-->", tag_start)
            idx = comment_end + 3 if comment_end != -1 else length
            continue

        # Skip processing instructions
        if tag_content.startswith("!") or tag_content.startswith("?"):
            idx = tag_end + 1
            continue

        # Parse tag name and attributes
        is_self_closing = tag_content.endswith("/")
        if is_self_closing:
            tag_content = tag_content[:-1].rstrip()

        space_idx = tag_content.find(" ")
        if space_idx == -1:
            tag_name = tag_content
            attr_string = ""
        else:
            tag_name = tag_content[:space_idx]
            attr_string = tag_content[space_idx + 1 :]

        tag_name = tag_name.strip()
        if not tag_name:
            idx = tag_end + 1
            continue

        # Parse attributes
        attributes = _parse_attributes(attr_string)

        new_node = XMLNode(
            tag=tag_name,
            attributes=attributes,
            original_tag=xml[tag_start : tag_end + 1],
        )
        parent.children.append(new_node)
        idx = tag_end + 1

        if not is_self_closing:
            # Recursively parse children
            _parse_element(xml[idx:], new_node)
            # Find closing tag to advance past it
            closing = f"</{tag_name}>"
            closing_upper = closing.upper()
            # Case-insensitive search
            search_from = idx
            close_idx = -1
            while search_from < length:
                candidate = xml.find("</", search_from)
                if candidate == -1:
                    break
                end_of_close = xml.find(">", candidate)
                if end_of_close == -1:
                    break
                candidate_tag = xml[candidate + 2 : end_of_close].strip()
                if candidate_tag.upper() == tag_name.upper():
                    close_idx = end_of_close + 1
                    break
                search_from = end_of_close + 1

            if close_idx != -1:
                idx = close_idx
            else:
                # No closing tag — continue from where we are
                break


def _parse_attributes(attr_string: str) -> dict[str, str]:
    """Parse attribute string into dict, handling malformed quotes."""
    attributes: dict[str, str] = {}
    remaining = attr_string.strip()

    while remaining:
        eq_idx = remaining.find("=")
        if eq_idx == -1:
            break

        attr_name = remaining[:eq_idx].strip()
        remaining = remaining[eq_idx + 1 :].strip()

        if not remaining:
            break

        quote_char = remaining[0]
        if quote_char in ('"', "'"):
            end_quote = remaining.find(quote_char, 1)
            if end_quote != -1:
                attr_value = remaining[1:end_quote]
                remaining = remaining[end_quote + 1 :].strip()
            else:
                attr_value = remaining[1:]
                remaining = ""
        else:
            space_idx = remaining.find(" ")
            if space_idx != -1:
                attr_value = remaining[:space_idx]
                remaining = remaining[space_idx + 1 :].strip()
            else:
                attr_value = remaining
                remaining = ""

        if attr_name:
            attributes[attr_name] = attr_value

    return attributes


# ── Section extraction ──


def _extract_sections(xml_text: str) -> list[str]:
    """Extract complete <SECTION>...</SECTION> blocks from XML text."""
    sections: list[str] = []
    text = xml_text
    idx = 0

    while idx < len(text):
        # Find next <SECTION
        start = text.upper().find("<SECTION", idx)
        if start == -1:
            break

        # Find </SECTION>
        end_tag = text.upper().find("</SECTION>", start)
        next_section = text.upper().find("<SECTION", start + 1)

        if end_tag != -1 and (next_section == -1 or end_tag < next_section):
            # Complete section
            section = text[start : end_tag + len("</SECTION>")]
            sections.append(section)
            idx = end_tag + len("</SECTION>")
        elif next_section != -1:
            # Incomplete section — force close
            partial = text[start:next_section]
            if any(tag in partial.upper() for tag in ("<H1>", "<H2>", "<H3>", "<P>", "<BOXES", "<STATS")):
                sections.append(partial.rstrip() + "</SECTION>")
            idx = next_section
        else:
            # Last section, possibly incomplete — force close
            remaining = text[start:]
            if "<H" in remaining.upper() or "<P>" in remaining.upper():
                if not remaining.upper().rstrip().endswith("</SECTION>"):
                    remaining = remaining.rstrip() + "</SECTION>"
                sections.append(remaining)
            break

    return sections


# ── Section → Slide conversion ──


def _convert_section_to_slide(section_xml: str) -> dict[str, Any]:
    """Convert a single <SECTION> XML block to an ancre-ai slide dict."""
    root = _parse_xml(section_xml)
    section_node = next(
        (c for c in root.children if c.tag.upper() == "SECTION"),
        None,
    )
    if not section_node:
        return {
            "layout_type": "vertical",
            "content_json": [],
            "root_image": None,
            "bg_color": None,
            "sizing": _default_sizing(),
        }

    # Extract layout
    layout_attr = section_node.attributes.get("layout", "vertical").lower()
    layout_type = layout_attr if layout_attr in VALID_LAYOUTS else "vertical"

    # Process children
    content_json: list[dict] = []
    root_image: dict[str, Any] | None = None

    for child in section_node.children:
        tag = child.tag.upper()

        # Root-level IMG → root_image (not inline img)
        if tag == "IMG":
            query = child.attributes.get("query", "").strip()
            if query and len(query) >= 3 and root_image is None:
                root_image = {"query": query, "layout_type": layout_type}
            continue

        # Process as content
        nodes = _process_top_level_node(child)
        content_json.extend(nodes)

    # Infer sizing from content density
    sizing = _infer_sizing(content_json, layout_type)

    return {
        "layout_type": layout_type,
        "content_json": content_json,
        "root_image": root_image,
        "bg_color": None,
        "sizing": sizing,
    }


def _infer_sizing(content_json: list[dict], layout_type: str) -> dict:
    """Infer SlideSizing from content density."""
    total_items = 0
    total_chars = 0

    def _count(nodes: list) -> None:
        nonlocal total_items, total_chars
        for node in nodes:
            if isinstance(node, dict):
                ntype = node.get("type", "")
                if ntype.endswith("_item") or ntype in ("compare_side", "before_after_side", "pros_item", "cons_item"):
                    total_items += 1
                if "text" in node:
                    total_chars += len(node["text"])
                children = node.get("children")
                if isinstance(children, list):
                    _count(children)

    _count(content_json)

    if total_items >= 5 or total_chars > 1000:
        return {"font_scale": "S", "block_spacing": "tight", "card_width": "L"}
    elif total_items <= 2 and total_chars < 300:
        return {"font_scale": "L", "block_spacing": "loose", "card_width": "M"}
    else:
        return {"font_scale": "M", "block_spacing": "normal", "card_width": "M"}


def _default_sizing() -> dict:
    return {"font_scale": "M", "block_spacing": "normal", "card_width": "M"}


# ── Public API ──


class XMLSlideParser:
    """Parse LLM-generated XML presentations into ancre-ai slide dicts."""

    def parse_presentation(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse a full <PRESENTATION>...</PRESENTATION> XML into a list of slide dicts.

        Each slide dict contains:
          - layout_type: str
          - content_json: list[dict]  (SlideNode format)
          - root_image: dict | None
          - bg_color: str | None
          - sizing: dict
        """
        sections = _extract_sections(xml_text)
        if not sections:
            logger.warning("No <SECTION> blocks found in XML output")
            return []

        slides: list[dict[str, Any]] = []
        for i, section_xml in enumerate(sections):
            try:
                slide = _convert_section_to_slide(section_xml)
                slides.append(slide)
            except Exception:
                logger.exception("Failed to parse section %d", i)
                continue

        logger.info("Parsed %d slides from XML (%d sections found)", len(slides), len(sections))
        return slides

    def parse_single_section(self, xml_text: str) -> dict[str, Any]:
        """Parse a single <SECTION>...</SECTION> XML block.

        Used for single-slide regeneration.
        """
        # Wrap in SECTION if not present
        if "<SECTION" not in xml_text.upper():
            xml_text = f'<SECTION layout="vertical">{xml_text}</SECTION>'

        sections = _extract_sections(xml_text)
        if sections:
            return _convert_section_to_slide(sections[0])

        return _convert_section_to_slide(xml_text)
