"""Email RAG indexer: chunk, embed, and index email messages."""

import logging
import re
from uuid import UUID

from sqlalchemy import select, func as sa_func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.chunking import chunker
from app.core.vector_store import vector_store
from app.models.chunk import Chunk
from app.models.collection import Collection, assistant_collections
from app.models.assistant import Assistant
from app.models.mail import MailMessage
from app.services.embedding import embedding_service

logger = logging.getLogger(__name__)
settings = get_settings()


def _prepare_email_text(msg: MailMessage) -> str:
    """Build a searchable text representation of an email message."""
    parts = []

    sender = msg.sender or {}
    sender_str = sender.get("name", "") or sender.get("email", "")
    if sender_str:
        parts.append(f"De: {sender_str}")

    to_list = msg.to_recipients or []
    to_str = ", ".join(r.get("name", "") or r.get("email", "") for r in to_list)
    if to_str:
        parts.append(f"À: {to_str}")

    if msg.subject:
        parts.append(f"Objet: {msg.subject}")

    if msg.date:
        parts.append(f"Date: {msg.date.strftime('%d/%m/%Y')}")

    parts.append("")  # blank line separator

    body = msg.body_text or ""
    if not body and msg.body_html:
        body = re.sub(r"<[^>]+>", " ", msg.body_html)
        body = re.sub(r"\s+", " ", body).strip()

    parts.append(body)
    return "\n".join(parts)


async def get_or_create_email_collection(db: AsyncSession, tenant_id: UUID) -> UUID:
    """Get or create the special __emails__ collection for a tenant."""
    result = await db.execute(
        select(Collection).where(
            Collection.tenant_id == tenant_id,
            Collection.name == "__emails__",
        )
    )
    collection = result.scalar_one_or_none()

    if collection:
        return collection.id

    collection = Collection(
        tenant_id=tenant_id,
        name="__emails__",
        description="Collection automatique pour les emails indexés (RAG)",
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


async def index_email_message(
    db: AsyncSession,
    msg: MailMessage,
    tenant_id: UUID,
    collection_id: UUID,
) -> int:
    """Index a single email message into RAG. Returns chunk count."""
    text = _prepare_email_text(msg)
    if not text.strip() or len(text.strip()) < 20:
        msg.is_indexed = True
        return 0

    chunks = chunker.chunk_text(
        text,
        section_title=msg.subject or "(email sans objet)",
    )

    if not chunks:
        msg.is_indexed = True
        return 0

    chunk_texts = [c.content for c in chunks]
    embeddings, _ = await embedding_service.embed_texts(chunk_texts)

    db_chunks = []
    vector_chunks = []

    sender = msg.sender or {}
    for chunk, embedding in zip(chunks, embeddings):
        db_chunk = Chunk(
            document_id=None,
            tenant_id=tenant_id,
            collection_id=collection_id,
            source_type="email",
            source_id=msg.id,
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
                "tenant_id": str(tenant_id),
                "collection_id": str(collection_id),
                "document_id": str(msg.id),
                "document_filename": f"Email: {msg.subject or '(sans objet)'}",
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "page_number": None,
                "section_title": chunk.section_title,
                "source_type": "email",
                "email_sender": sender.get("email", ""),
                "email_date": msg.date.isoformat() if msg.date else None,
            },
        })

    await db.flush()

    for db_chunk, vec_chunk in zip(db_chunks, vector_chunks):
        db_chunk.qdrant_id = vec_chunk["id"]
        vec_chunk["id"] = str(db_chunk.id)

    await vector_store.ensure_collection()
    await vector_store.upsert_chunks(vector_chunks)

    msg.is_indexed = True
    return len(db_chunks)


async def index_unindexed_emails(
    db: AsyncSession,
    account_id: UUID,
    tenant_id: UUID,
    collection_id: UUID,
    batch_size: int = 50,
) -> int:
    """Index all unindexed emails for an account. Returns total chunks created."""
    result = await db.execute(
        select(MailMessage)
        .where(
            MailMessage.mail_account_id == account_id,
            MailMessage.tenant_id == tenant_id,
            MailMessage.is_indexed == False,  # noqa: E712
            MailMessage.is_draft == False,  # noqa: E712
        )
        .order_by(MailMessage.date.desc())
        .limit(batch_size)
    )
    messages = list(result.scalars().all())

    total_chunks = 0
    for msg in messages:
        try:
            count = await index_email_message(db, msg, tenant_id, collection_id)
            total_chunks += count
        except Exception as e:
            logger.warning("Failed to index email %s: %s", msg.id, e)

    return total_chunks
