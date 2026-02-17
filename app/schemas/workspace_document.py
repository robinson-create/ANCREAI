"""Workspace document schemas — DocModel, block types, CRUD, AI actions."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Block content types ──


class LineItem(BaseModel):
    """A single line item in a line_items block."""

    id: str
    description: str = ""
    quantity: float = 0
    unit: str = ""
    unit_price: float = 0
    tax_rate: float = 0
    total: float = 0
    meta: dict[str, Any] | None = None


class RichTextBlock(BaseModel):
    type: Literal["rich_text"] = "rich_text"
    id: str
    label: str | None = None
    content: dict = Field(default_factory=dict)  # ProseMirror JSON
    locked: bool = False


class LineItemsBlock(BaseModel):
    type: Literal["line_items"] = "line_items"
    id: str
    label: str | None = None
    columns: list[str] = Field(
        default_factory=lambda: [
            "description",
            "quantity",
            "unit",
            "unit_price",
            "tax_rate",
            "total",
        ]
    )
    items: list[LineItem] = Field(default_factory=list)
    currency: str = "EUR"


class ClauseBlock(BaseModel):
    type: Literal["clause"] = "clause"
    id: str
    label: str | None = None
    content: dict = Field(default_factory=dict)  # ProseMirror JSON
    clause_ref: str | None = None
    locked: bool = False


class TermsBlock(BaseModel):
    type: Literal["terms"] = "terms"
    id: str
    label: str | None = None
    content: dict = Field(default_factory=dict)  # ProseMirror JSON
    locked: bool = False


class SignatureBlock(BaseModel):
    type: Literal["signature"] = "signature"
    id: str
    label: str | None = None
    parties: list[dict[str, Any]] = Field(default_factory=list)


class AttachmentsBlock(BaseModel):
    type: Literal["attachments"] = "attachments"
    id: str
    label: str | None = None
    files: list[dict[str, Any]] = Field(default_factory=list)


class VariablesBlock(BaseModel):
    type: Literal["variables"] = "variables"
    id: str
    label: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)


# Discriminated union on "type"
DocBlock = Annotated[
    RichTextBlock
    | LineItemsBlock
    | ClauseBlock
    | TermsBlock
    | SignatureBlock
    | AttachmentsBlock
    | VariablesBlock,
    Field(discriminator="type"),
]


# ── DocModel ──


class DocSource(BaseModel):
    """Reference to a RAG source used during generation."""

    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int | None = None
    excerpt: str = ""
    score: float = 0.0


class DocMeta(BaseModel):
    """Document metadata."""

    author: str | None = None
    client: str | None = None
    project: str | None = None
    reference: str | None = None
    date: str | None = None
    tags: list[str] = Field(default_factory=list)
    custom: dict[str, Any] = Field(default_factory=dict)


class DocModel(BaseModel):
    """Structured document model stored as content_json in workspace_documents."""

    version: int = 1
    meta: DocMeta = Field(default_factory=DocMeta)
    blocks: list[DocBlock] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    sources: list[DocSource] = Field(default_factory=list)


# ── CRUD schemas ──


class WorkspaceDocumentCreate(BaseModel):
    title: str = "Sans titre"
    doc_type: str = "generic"
    assistant_id: UUID | None = None
    status: str = "draft"
    content_json: DocModel = Field(default_factory=DocModel)
    template_id: UUID | None = None


class WorkspaceDocumentUpdate(BaseModel):
    title: str | None = None
    doc_type: str | None = None
    assistant_id: UUID | None = None
    status: str | None = None
    content_json: DocModel | None = None


class WorkspaceDocumentPatch(BaseModel):
    """Partial update for autosave — only content_json."""

    content_json: DocModel


class WorkspaceDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    assistant_id: UUID | None = None
    title: str
    doc_type: str
    status: str
    content_json: dict  # raw JSONB
    version: int
    last_exported_url: str | None = None
    created_at: datetime
    updated_at: datetime


class WorkspaceDocumentListItem(BaseModel):
    """Lightweight item for list view (no content_json)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    title: str
    doc_type: str
    status: str
    assistant_id: UUID | None = None
    version: int
    created_at: datetime
    updated_at: datetime


# ── AI action schemas ──


class GenerateRequest(BaseModel):
    """Generate document content using RAG."""

    prompt: str
    collection_ids: list[UUID] = Field(default_factory=list)
    doc_type: str = "generic"
    target_block_ids: list[str] | None = None


class RewriteBlockRequest(BaseModel):
    """Rewrite a specific block."""

    block_id: str
    instruction: str
    collection_ids: list[UUID] = Field(default_factory=list)


class CheckDocumentRequest(BaseModel):
    """Check document for consistency / compliance."""

    collection_ids: list[UUID] = Field(default_factory=list)
    check_type: str = "general"  # general | legal | financial


class AddLineItemRequest(BaseModel):
    """Add a line item to a line_items block."""

    block_id: str
    description: str
    collection_ids: list[UUID] = Field(default_factory=list)


class DocPatch(BaseModel):
    """A single patch operation on a DocModel."""

    op: str  # "add_block" | "replace_block" | "update_variables" | "add_source" | "add_line_item"
    block_id: str | None = None
    value: dict[str, Any] = Field(default_factory=dict)


class AiActionResponse(BaseModel):
    """Response from AI actions — returns DocModel patches."""

    patches: list[DocPatch] = Field(default_factory=list)
    sources: list[DocSource] = Field(default_factory=list)
    message: str = ""
