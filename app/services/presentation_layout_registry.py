"""
Registry of the 12 slide layout templates (general group).

Each layout has:
- id: unique identifier used in PresentationSlide.layout_type
- name: display name
- description: used by the LLM to choose the right layout
- json_schema: JSON Schema sent to the LLM as response_format for structured output.
  Fields __image_url__ and __icon_url__ are EXCLUDED (resolved post-generation).
  Fields __image_prompt__ and __icon_query__ are INCLUDED (LLM generates these).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Image / Icon sub-schemas (reused across templates)
# ---------------------------------------------------------------------------
_IMAGE_PROMPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "__image_prompt__": {
            "type": "string",
            "minLength": 10,
            "maxLength": 50,
            "description": "Short prompt to generate/search a relevant image",
        },
    },
    "required": ["__image_prompt__"],
}

_ICON_QUERY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "__icon_query__": {
            "type": "string",
            "minLength": 5,
            "maxLength": 20,
            "description": "Short query to search for a relevant icon",
        },
    },
    "required": ["__icon_query__"],
}

# ---------------------------------------------------------------------------
# Speaker note field – injected into every schema at generation time
# ---------------------------------------------------------------------------
SPEAKER_NOTE_FIELD: dict[str, Any] = {
    "__speaker_note__": {
        "type": "string",
        "minLength": 100,
        "maxLength": 250,
        "description": "Speaker note for the slide",
    },
}

# ---------------------------------------------------------------------------
# The 12 layouts
# ---------------------------------------------------------------------------

LAYOUT_REGISTRY: list[dict[str, Any]] = [
    # 1 ─ Intro slide
    {
        "id": "general-intro-slide",
        "name": "Intro Slide",
        "description": "A clean title slide with title, description, presenter name, date, and a supporting image. Use for the first slide.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 40, "description": "Main title of the slide"},
                "description": {"type": "string", "minLength": 10, "maxLength": 150, "description": "Main description text content"},
                "presenterName": {"type": "string", "minLength": 2, "maxLength": 50, "description": "Name of the presenter"},
                "presentationDate": {"type": "string", "minLength": 2, "maxLength": 50, "description": "Date of the presentation (use today's date)"},
                "image": _IMAGE_PROMPT_SCHEMA,
            },
            "required": ["title", "description", "presenterName", "presentationDate", "image"],
        },
    },
    # 2 ─ Basic info
    {
        "id": "basic-info-slide",
        "name": "Basic Info",
        "description": "A clean slide with title, description text, and a supporting image. Good for general content.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 40, "description": "Main title of the slide"},
                "description": {"type": "string", "minLength": 10, "maxLength": 150, "description": "Main description text content"},
                "image": _IMAGE_PROMPT_SCHEMA,
            },
            "required": ["title", "description", "image"],
        },
    },
    # 3 ─ Bullet icons only
    {
        "id": "bullet-icons-only-slide",
        "name": "Bullet Icons Only",
        "description": "A slide with title, grid of bullet points (title + subtitle) with icons, and a supporting image. Good for features or solutions.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 40, "description": "Main title"},
                "image": _IMAGE_PROMPT_SCHEMA,
                "bulletPoints": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "minLength": 2, "maxLength": 80, "description": "Bullet point title"},
                            "subtitle": {"type": "string", "minLength": 5, "maxLength": 150, "description": "Optional short subtitle"},
                            "icon": _ICON_QUERY_SCHEMA,
                        },
                        "required": ["title", "icon"],
                    },
                },
            },
            "required": ["title", "image", "bulletPoints"],
        },
    },
    # 4 ─ Bullet with icons
    {
        "id": "bullet-with-icons-slide",
        "name": "Bullet with Icons",
        "description": "A slide with title, description, image, and bullet points with icons and descriptions. Good for problems or detailed lists.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 40, "description": "Main title"},
                "description": {"type": "string", "maxLength": 150, "description": "Main description text"},
                "image": _IMAGE_PROMPT_SCHEMA,
                "bulletPoints": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "minLength": 2, "maxLength": 60, "description": "Bullet point title"},
                            "description": {"type": "string", "minLength": 10, "maxLength": 100, "description": "Bullet point description"},
                            "icon": _ICON_QUERY_SCHEMA,
                        },
                        "required": ["title", "description", "icon"],
                    },
                },
            },
            "required": ["title", "description", "image", "bulletPoints"],
        },
    },
    # 5 ─ Chart with bullets
    {
        "id": "chart-with-bullets-slide",
        "name": "Chart with Bullet Boxes",
        "description": "A slide with title, description, chart on the left and colored bullet boxes with icons on the right. Only use when data is available.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 40, "description": "Main title"},
                "description": {"type": "string", "minLength": 10, "maxLength": 150, "description": "Description text below the title"},
                "chartData": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["bar", "pie", "line", "area", "scatter"], "description": "Chart type"},
                        "data": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 5,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Data point name"},
                                    "value": {"type": "number", "description": "Data point value"},
                                },
                                "required": ["name", "value"],
                            },
                        },
                    },
                    "required": ["type", "data"],
                },
                "showLegend": {"type": "boolean", "description": "Whether to show chart legend"},
                "showTooltip": {"type": "boolean", "description": "Whether to show chart tooltip"},
                "bulletPoints": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "minLength": 2, "maxLength": 80, "description": "Bullet point title"},
                            "description": {"type": "string", "minLength": 10, "maxLength": 150, "description": "Bullet point description"},
                            "icon": _ICON_QUERY_SCHEMA,
                        },
                        "required": ["title", "description", "icon"],
                    },
                },
            },
            "required": ["title", "description", "chartData", "bulletPoints"],
        },
    },
    # 6 ─ Metrics
    {
        "id": "metrics-slide",
        "name": "Metrics",
        "description": "A slide for showcasing key business metrics with large numbers. Supports 2-8 metrics — auto-compacts to fit. Use when many numbers or KPIs must appear on one slide.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 100, "description": "Main title"},
                "metrics": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "minLength": 2, "maxLength": 50, "description": "Metric label/title"},
                            "value": {"type": "string", "minLength": 1, "maxLength": 10, "description": "Metric value (e.g., 150+, 95%, $2M). Keep very short."},
                            "description": {"type": "string", "maxLength": 80, "description": "Optional short description"},
                        },
                        "required": ["label", "value"],
                    },
                },
            },
            "required": ["title", "metrics"],
        },
    },
    # 7 ─ Metrics with image
    {
        "id": "metrics-with-image-slide",
        "name": "Metrics with Image",
        "description": "A slide with supporting image on the left and title, description, and metrics grid on the right. Supports 2-6 metrics.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 40, "description": "Main title"},
                "description": {"type": "string", "minLength": 10, "maxLength": 150, "description": "Description text below the title"},
                "image": _IMAGE_PROMPT_SCHEMA,
                "metrics": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 6,
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "minLength": 2, "maxLength": 100, "description": "Metric label/title"},
                            "value": {"type": "string", "minLength": 1, "maxLength": 20, "description": "Metric value (e.g., 200+, 95%, 50%)"},
                        },
                        "required": ["label", "value"],
                    },
                },
            },
            "required": ["title", "description", "image", "metrics"],
        },
    },
    # 8 ─ Numbered bullets
    {
        "id": "numbered-bullets-slide",
        "name": "Numbered Bullets",
        "description": "A slide with large title, supporting image, and numbered bullet points with descriptions. Good for processes or steps.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 40, "description": "Main title"},
                "image": _IMAGE_PROMPT_SCHEMA,
                "bulletPoints": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "minLength": 2, "maxLength": 80, "description": "Bullet point title"},
                            "description": {"type": "string", "minLength": 10, "maxLength": 150, "description": "Bullet point description"},
                        },
                        "required": ["title", "description"],
                    },
                },
            },
            "required": ["title", "image", "bulletPoints"],
        },
    },
    # 9 ─ Quote
    {
        "id": "quote-slide",
        "name": "Quote",
        "description": "A slide with a heading, inspirational quote, author, and background image with overlay. Use for impactful quotations.",
        "json_schema": {
            "type": "object",
            "properties": {
                "heading": {"type": "string", "minLength": 3, "maxLength": 60, "description": "Main heading of the slide"},
                "quote": {"type": "string", "minLength": 10, "maxLength": 200, "description": "The main quote text content"},
                "author": {"type": "string", "minLength": 2, "maxLength": 50, "description": "Author of the quote"},
                "backgroundImage": _IMAGE_PROMPT_SCHEMA,
            },
            "required": ["heading", "quote", "author", "backgroundImage"],
        },
    },
    # 10 ─ Table info
    {
        "id": "table-info-slide",
        "name": "Table with Info",
        "description": "A slide with a title, structured table, and descriptive text. Use for data comparisons or structured information.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 40, "description": "Main title"},
                "tableData": {
                    "type": "object",
                    "properties": {
                        "headers": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 5,
                            "items": {"type": "string", "minLength": 1, "maxLength": 30},
                            "description": "Table column headers",
                        },
                        "rows": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 6,
                            "items": {
                                "type": "array",
                                "items": {"type": "string", "minLength": 1, "maxLength": 50},
                            },
                            "description": "Table rows data – each row should match the number of headers",
                        },
                    },
                    "required": ["headers", "rows"],
                },
                "description": {"type": "string", "minLength": 10, "maxLength": 200, "description": "Descriptive text below the table"},
            },
            "required": ["title", "tableData", "description"],
        },
    },
    # 11 ─ Table of contents
    {
        "id": "table-of-contents-slide",
        "name": "Table of Contents",
        "description": "A professional table of contents with numbered sections and page references. Place right after intro slide if used.",
        "json_schema": {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 12,
                    "items": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "integer", "minimum": 1, "description": "Section number"},
                            "title": {"type": "string", "minLength": 1, "maxLength": 80, "description": "Section title"},
                            "pageNumber": {"type": "string", "minLength": 1, "maxLength": 10, "description": "Page number for this section"},
                        },
                        "required": ["number", "title", "pageNumber"],
                    },
                },
            },
            "required": ["sections"],
        },
    },
    # 12 ─ Team
    {
        "id": "team-slide",
        "name": "Team Slide",
        "description": "A slide showcasing team members with photos, names, positions, and descriptions alongside company information.",
        "json_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 3, "maxLength": 40, "description": "Main title"},
                "companyDescription": {"type": "string", "minLength": 10, "maxLength": 150, "description": "Company description or team introduction text"},
                "teamMembers": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "minLength": 2, "maxLength": 50, "description": "Team member's full name"},
                            "position": {"type": "string", "minLength": 2, "maxLength": 50, "description": "Job title or position"},
                            "description": {"type": "string", "maxLength": 150, "description": "Brief description of the team member"},
                            "image": _IMAGE_PROMPT_SCHEMA,
                        },
                        "required": ["name", "position", "description", "image"],
                    },
                },
            },
            "required": ["title", "companyDescription", "teamMembers"],
        },
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REGISTRY_BY_ID: dict[str, dict[str, Any]] = {l["id"]: l for l in LAYOUT_REGISTRY}


def get_layout_by_id(layout_id: str) -> dict[str, Any] | None:
    """Return a layout dict by its id, or None."""
    return _REGISTRY_BY_ID.get(layout_id)


def get_layout_by_index(index: int) -> dict[str, Any] | None:
    """Return a layout dict by its position in the registry."""
    if 0 <= index < len(LAYOUT_REGISTRY):
        return LAYOUT_REGISTRY[index]
    return None


def get_all_layout_ids() -> list[str]:
    """Return list of all layout ids."""
    return [l["id"] for l in LAYOUT_REGISTRY]


def build_layout_description_for_llm() -> str:
    """Build a human-readable string listing all layouts for the structure selection prompt."""
    lines: list[str] = []
    for i, layout in enumerate(LAYOUT_REGISTRY):
        lines.append(f"{i}. **{layout['name']}** – {layout['description']}")
    return "\n".join(lines)


def get_schema_for_llm(layout_id: str) -> dict[str, Any] | None:
    """Return the JSON schema for a layout with __speaker_note__ injected and __image_url__/__icon_url__ removed."""
    layout = get_layout_by_id(layout_id)
    if not layout:
        return None

    import copy
    schema = copy.deepcopy(layout["json_schema"])

    # Inject speaker note
    schema["properties"]["__speaker_note__"] = SPEAKER_NOTE_FIELD["__speaker_note__"]
    if "required" in schema:
        schema["required"].append("__speaker_note__")

    return schema
