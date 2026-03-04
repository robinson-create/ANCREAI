"""Content indexer: chunk, embed, and index workspace documents and presentations for RAG.

Uses a shared __workspace__ collection per tenant (similar to __emails__).
Chunks carry source_type to distinguish: 'workspace_document', 'presentation'.
"""

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy import func as sa_func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.chunking import chunker
from app.core.vector_store import vector_store
from app.models.assistant import Assistant
from app.models.chunk import Chunk
from app.models.collection import Collection, assistant_collections
from app.services.embedding import embedding_service

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Shared __workspace__ collection
# ---------------------------------------------------------------------------


async def get_or_create_workspace_collection(db: AsyncSession, tenant_id: UUID) -> UUID:
    """Get or create the __workspace__ collection for generated content."""
    result = await db.execute(
        select(Collection).where(
            Collection.tenant_id == tenant_id,
            Collection.name == "__workspace__",
        )
    )
    collection = result.scalar_one_or_none()
    if collection:
        return collection.id

    collection = Collection(
        tenant_id=tenant_id,
        name="__workspace__",
        description="Collection automatique pour documents générés et présentations (RAG)",
    )
    db.add(collection)
    await db.flush()

    # Auto-link to all tenant assistants
    assistants_result = await db.execute(
        select(Assistant.id).where(Assistant.tenant_id == tenant_id)
    )
    for (assistant_id,) in assistants_result.all():
        stmt = (
            pg_insert(assistant_collections)
            .values(assistant_id=assistant_id, collection_id=collection.id)
            .on_conflict_do_nothing()
        )
        await db.execute(stmt)

    return collection.id


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def extract_prosemirror_text(node: dict) -> str:
    """Recursively extract plain text from a ProseMirror JSON document node."""
    if not isinstance(node, dict):
        return ""
    parts: list[str] = []
    if node.get("type") == "text":
        parts.append(node.get("text", ""))
    for child in node.get("content", []):
        parts.append(extract_prosemirror_text(child))
    return " ".join(parts)


def extract_workspace_document_text(title: str, content_json: dict) -> str:
    """Extract searchable text from a workspace document's content_json."""
    parts: list[str] = []
    if title:
        parts.append(title)

    # Meta
    meta = content_json.get("meta", {})
    for field in ("author", "client", "project", "reference"):
        val = meta.get(field)
        if val:
            parts.append(f"{field}: {val}")

    # Blocks
    for block in content_json.get("blocks", []):
        block_type = block.get("type", "")
        label = block.get("label")
        if label:
            parts.append(label)

        if block_type in ("rich_text", "clause", "terms"):
            pm_content = block.get("content", {})
            text = extract_prosemirror_text(pm_content).strip()
            if text:
                parts.append(text)
        elif block_type == "line_items":
            for item in block.get("items", []):
                desc = item.get("description", "")
                if desc:
                    qty = item.get("quantity", "")
                    unit = item.get("unit", "")
                    price = item.get("unit_price", "")
                    parts.append(f"{desc} ({qty} {unit} × {price})")
        elif block_type == "signature":
            for party in block.get("parties", []):
                name = party.get("name", "")
                role = party.get("role", "")
                if name:
                    parts.append(f"{name} ({role})" if role else name)

    return "\n\n".join(p for p in parts if p)


def extract_presentation_text(title: str, prompt: str | None, slides: list[dict]) -> str:
    """Extract searchable text from a presentation's slides."""
    parts: list[str] = []
    if title:
        parts.append(title)
    if prompt:
        parts.append(f"Sujet: {prompt}")

    for slide in slides:
        content = slide.get("content_json", {})
        if not content:
            continue

        # Extract all string values from content_json recursively
        _extract_json_strings(content, parts)

        notes = slide.get("speaker_notes")
        if notes:
            parts.append(notes)

    return "\n\n".join(p for p in parts if p)


def _extract_json_strings(obj, parts: list[str], depth: int = 0) -> None:
    """Recursively extract meaningful string values from a JSON structure."""
    if depth > 10:
        return
    if isinstance(obj, str):
        # Skip short strings, URLs, colors, icons
        text = obj.strip()
        if (
            len(text) > 5
            and not text.startswith("#")
            and not text.startswith("http")
            and not text.startswith("__")
        ):
            parts.append(text)
    elif isinstance(obj, dict):
        for key, val in obj.items():
            # Skip layout/style/image keys
            if key in (
                "icon_name", "icon_query", "__icon_query__",
                "__image_prompt__", "__image_url__",
                "bg_color", "color", "layout_type",
            ):
                continue
            _extract_json_strings(val, parts, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _extract_json_strings(item, parts, depth + 1)


# ---------------------------------------------------------------------------
# Indexing functions
# ---------------------------------------------------------------------------


async def _delete_existing_chunks(
    db: AsyncSession,
    tenant_id: UUID,
    source_type: str,
    source_id: UUID,
) -> None:
    """Delete existing DB chunks for a source + Qdrant vectors."""
    await db.execute(
        delete(Chunk).where(
            Chunk.tenant_id == tenant_id,
            Chunk.source_type == source_type,
            Chunk.source_id == source_id,
        )
    )
    # Qdrant: delete by document_id (which we set to source_id in payload)
    await vector_store.delete_by_document(source_id, tenant_id)


async def index_workspace_document(
    db: AsyncSession,
    tenant_id: UUID,
    doc_id: UUID,
    title: str,
    content_json: dict,
) -> int:
    """Index a workspace document into the __workspace__ collection. Returns chunk count."""
    text = extract_workspace_document_text(title, content_json)
    if not text.strip() or len(text.strip()) < 30:
        return 0

    collection_id = await get_or_create_workspace_collection(db, tenant_id)

    # Remove old chunks
    await _delete_existing_chunks(db, tenant_id, "workspace_document", doc_id)

    # Chunk
    chunks = chunker.chunk_text(text, section_title=title)
    if not chunks:
        return 0

    # Embed
    chunk_texts = [c.content for c in chunks]
    embeddings, _ = await embedding_service.embed_texts(chunk_texts)

    # Store
    db_chunks = []
    vector_chunks = []

    for chunk, embedding in zip(chunks, embeddings):
        db_chunk = Chunk(
            document_id=None,
            tenant_id=tenant_id,
            collection_id=collection_id,
            source_type="workspace_document",
            source_id=doc_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            content_hash=chunk.content_hash,
            token_count=chunk.token_count,
            content_tsv=sa_func.to_tsvector(settings.postgres_fts_config, chunk.content),
            page_number=None,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            section_title=chunk.section_title,
        )
        db.add(db_chunk)
        db_chunks.append(db_chunk)

        vector_chunks.append({
            "id": str(db_chunk.id),
            "vector": embedding,
            "payload": {
                "scope": "org",
                "tenant_id": str(tenant_id),
                "collection_id": str(collection_id),
                "document_id": str(doc_id),
                "document_filename": f"Document: {title}",
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "section_title": chunk.section_title,
                "source_type": "workspace_document",
            },
        })

    await db.flush()

    for db_chunk, vec_chunk in zip(db_chunks, vector_chunks):
        db_chunk.qdrant_id = vec_chunk["id"]
        vec_chunk["id"] = str(db_chunk.id)

    await vector_store.ensure_collection()
    await vector_store.upsert_chunks(vector_chunks)

    logger.info(
        "Indexed workspace document %s: %d chunks",
        doc_id, len(db_chunks),
    )
    return len(db_chunks)


async def index_presentation(
    db: AsyncSession,
    tenant_id: UUID,
    presentation_id: UUID,
    title: str,
    prompt: str | None,
    slides: list[dict],
) -> int:
    """Index a presentation into the __workspace__ collection. Returns chunk count."""
    text = extract_presentation_text(title, prompt, slides)
    if not text.strip() or len(text.strip()) < 30:
        return 0

    collection_id = await get_or_create_workspace_collection(db, tenant_id)

    # Remove old chunks
    await _delete_existing_chunks(db, tenant_id, "presentation", presentation_id)

    # Chunk
    chunks = chunker.chunk_text(text, section_title=title)
    if not chunks:
        return 0

    # Embed
    chunk_texts = [c.content for c in chunks]
    embeddings, _ = await embedding_service.embed_texts(chunk_texts)

    # Store
    db_chunks = []
    vector_chunks = []

    for chunk, embedding in zip(chunks, embeddings):
        db_chunk = Chunk(
            document_id=None,
            tenant_id=tenant_id,
            collection_id=collection_id,
            source_type="presentation",
            source_id=presentation_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            content_hash=chunk.content_hash,
            token_count=chunk.token_count,
            content_tsv=sa_func.to_tsvector(settings.postgres_fts_config, chunk.content),
            page_number=None,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            section_title=chunk.section_title,
        )
        db.add(db_chunk)
        db_chunks.append(db_chunk)

        vector_chunks.append({
            "id": str(db_chunk.id),
            "vector": embedding,
            "payload": {
                "scope": "org",
                "tenant_id": str(tenant_id),
                "collection_id": str(collection_id),
                "document_id": str(presentation_id),
                "document_filename": f"Présentation: {title}",
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "section_title": chunk.section_title,
                "source_type": "presentation",
            },
        })

    await db.flush()

    for db_chunk, vec_chunk in zip(db_chunks, vector_chunks):
        db_chunk.qdrant_id = vec_chunk["id"]
        vec_chunk["id"] = str(db_chunk.id)

    await vector_store.ensure_collection()
    await vector_store.upsert_chunks(vector_chunks)

    logger.info(
        "Indexed presentation %s: %d chunks",
        presentation_id, len(db_chunks),
    )
    return len(db_chunks)
