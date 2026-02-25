"""Presentation schemas — slide content, CRUD, AI generation, export."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Slide content types (JSON pivot) ──


class TextLeaf(BaseModel):
    """Inline text node with optional marks."""

    text: str
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    color: str | None = None
    font_size: str | None = None
    font_family: str | None = None


class SlideNode(BaseModel):
    """Recursive Plate-style node for slide content."""

    type: str  # h1|h2|h3|h4|h5|h6|p|img|bullet_group|bullet_item|box_group|box_item|...
    children: list[SlideNode | TextLeaf] = Field(default_factory=list)
    # Optional props depending on type
    url: str | None = None
    asset_id: str | None = None
    data: list[dict[str, Any]] | None = None  # chart data
    align: str | None = None
    # Variant for styled elements (boxes, bullets, timeline, pyramid, quote, stats, gallery)
    variant: str | None = None
    # Value for stats items
    value: str | None = None
    # Image query for gallery items
    query: str | None = None


class CropSettings(BaseModel):
    object_fit: str = "cover"
    object_position: dict[str, float] = Field(
        default_factory=lambda: {"x": 50, "y": 50}
    )
    zoom: float | None = None


class RootImage(BaseModel):
    """Background/layout image reference for a slide."""

    asset_id: str | None = None
    query: str = ""
    layout_type: str | None = None
    crop_settings: CropSettings | None = None


class SlideContent(BaseModel):
    """Validated slide content — used at save time."""

    content_json: list[SlideNode] = Field(default_factory=list)
    layout_type: Literal[
        "vertical", "left", "right", "left-fit", "right-fit", "accent-top", "background"
    ] = "vertical"
    root_image: RootImage | None = None
    bg_color: str | None = None


# ── Outline ──


class OutlineItem(BaseModel):
    """A single outline section with title and bullet points."""

    title: str
    bullets: list[str] = Field(default_factory=list)


# ── Theme ──


class ThemeColors(BaseModel):
    primary: str = "#6C63FF"
    secondary: str = "#2D2B55"
    accent: str = "#FF6584"
    background: str = "#FFFFFF"
    text: str = "#333333"
    heading: str = "#1a1a2e"
    muted: str = "#6b7280"


class ThemeFonts(BaseModel):
    heading: str = "Inter"
    body: str = "Inter"


class ThemeData(BaseModel):
    """Theme properties stored in presentation_themes.theme_data."""

    colors: ThemeColors = Field(default_factory=ThemeColors)
    fonts: ThemeFonts = Field(default_factory=ThemeFonts)
    border_radius: str = "12px"


class ThemeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    name: str
    is_builtin: bool
    theme_data: dict
    created_at: datetime


class ThemeCreate(BaseModel):
    name: str
    theme_data: ThemeData


# ── CRUD schemas ──


class PresentationCreate(BaseModel):
    title: str = "Sans titre"
    prompt: str | None = None
    settings: dict = Field(
        default_factory=lambda: {
            "language": "fr-FR",
            "style": "professional",
            "slide_count": 8,
        }
    )
    theme_id: UUID | None = None


class PresentationUpdate(BaseModel):
    title: str | None = None
    prompt: str | None = None
    settings: dict | None = None
    theme_id: UUID | None = None


class SlideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    layout_type: str
    content_json: list | dict
    root_image: dict | None = None
    bg_color: str | None = None
    speaker_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class PresentationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    title: str
    prompt: str | None = None
    status: str
    outline: list
    settings: dict
    slide_order: list
    version: int
    theme_id: UUID | None = None
    theme: ThemeRead | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    slides: list[SlideRead] = Field(default_factory=list)


class PresentationListItem(BaseModel):
    """Lightweight item for list view (no slides)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    title: str
    status: str
    slide_order: list
    version: int
    theme_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SlideUpdate(BaseModel):
    """Partial update for a single slide."""

    content_json: list | dict | None = None
    layout_type: str | None = None
    root_image: dict | None = None
    bg_color: str | None = None
    speaker_notes: str | None = None


class SlideReorderRequest(BaseModel):
    slide_ids: list[UUID]


# ── AI generation ──


class GenerateOutlineRequest(BaseModel):
    prompt: str
    slide_count: int = 8
    language: str = "fr-FR"
    style: str = "professional"
    collection_ids: list[UUID] = Field(default_factory=list)


class GenerateSlidesRequest(BaseModel):
    collection_ids: list[UUID] = Field(default_factory=list)


class RegenerateSlideRequest(BaseModel):
    instruction: str = ""
    collection_ids: list[UUID] = Field(default_factory=list)


class OutlineUpdate(BaseModel):
    outline: list[OutlineItem]


# ── Export ──


class ExportRequest(BaseModel):
    format: Literal["pptx", "pdf"]


class ExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    format: str
    status: str
    s3_key: str | None = None
    file_size: int | None = None
    presentation_version: int
    slide_count: int
    error_message: str | None = None
    created_at: datetime


# ── Asset ──


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    status: str
    s3_key: str | None = None
    mime: str | None = None
    width: int | None = None
    height: int | None = None
    byte_size: int | None = None
    created_at: datetime
