"""Arq task definitions for document processing and mail integration."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from arq import ArqRedis, cron
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.core.chunking import chunk_document
from app.core.parsing import parse_document_with_ocr
from app.core.vector_store import vector_store
from app.models.chunk import Chunk
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.mail import MailAccount, MailMessage, MailSendRequest, MailSyncState, ScheduledEmail
from app.services.embedding import embedding_service
from app.services.mail.base import SendPayload
from app.services.mail.factory import get_mail_provider
from app.services.mail.parse import parse_gmail_message, parse_graph_message
from app.integrations.nango.client import nango_client
from app.services.storage import storage_service
from app.services.web_crawler import crawl_url
from app.models.web_source import WebSource
from app.workers.settings import redis_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# Create engine for worker (separate from web app)
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Get database session for worker."""
    return async_session_maker()


async def process_document(ctx: dict, document_id: str) -> dict:
    """
    Process a document: download, parse (with OCR), chunk, embed, index.

    Args:
        ctx: Arq context
        document_id: UUID of the document to process

    Returns:
        Dict with processing results
    """
    doc_uuid = UUID(document_id)
    db = await get_db()

    try:
        # Get document
        result = await db.execute(
            select(Document).where(Document.id == doc_uuid)
        )
        document = result.scalar_one_or_none()

        if not document:
            logger.error(f"Document {document_id} not found")
            return {"error": "Document not found"}

        # Update status to processing
        document.status = DocumentStatus.PROCESSING.value
        await db.commit()

        # Get collection for tenant_id
        result = await db.execute(
            select(Collection).where(Collection.id == document.collection_id)
        )
        collection = result.scalar_one()
        tenant_id = collection.tenant_id

        logger.info(f"Processing document {document_id}: {document.filename}")

        # 1. Download from S3
        content = await storage_service.download_file(document.s3_key)

        # 2. Parse document (with OCR fallback for scanned PDFs)
        parsed = await parse_document_with_ocr(content, document.filename, document.content_type)
        document.page_count = parsed.total_pages
        logger.info(
            f"Parsed with {parsed.parser_used}: {parsed.total_pages} pages"
        )

        # 2b. Store document pages (for citations)
        for page in parsed.pages:
            doc_page = DocumentPage(
                document_id=doc_uuid,
                tenant_id=tenant_id,
                page_number=page.page_number,
                text=page.content,
                meta=page.metadata or None,
            )
            db.add(doc_page)

        # 3. Chunk document
        chunks = chunk_document(parsed)
        document.chunk_count = len(chunks)

        if not chunks:
            document.status = DocumentStatus.READY.value
            document.processed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"message": "No content to index", "chunks": 0}

        # 4. Generate embeddings
        chunk_texts = [c.content for c in chunks]
        embeddings, tokens_used = await embedding_service.embed_texts(chunk_texts)
        document.tokens_used = tokens_used

        # 5. Prepare chunks for DB and vector store
        db_chunks = []
        vector_chunks = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Create DB chunk with denormalized tenant/collection + FTS vector
            db_chunk = Chunk(
                document_id=doc_uuid,
                tenant_id=tenant_id,
                collection_id=document.collection_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                content_hash=chunk.content_hash,
                token_count=chunk.token_count,
                content_tsv=sa_func.to_tsvector(settings.postgres_fts_config, chunk.content),
                page_number=chunk.page_number,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                section_title=chunk.section_title,
            )
            db.add(db_chunk)
            db_chunks.append(db_chunk)

            # Prepare vector store entry
            vector_chunks.append({
                "id": str(db_chunk.id),
                "vector": embedding,
                "payload": {
                    "tenant_id": str(tenant_id),
                    "collection_id": str(document.collection_id),
                    "document_id": str(doc_uuid),
                    "document_filename": document.filename,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "section_title": chunk.section_title,
                },
            })

        # Save chunks to DB
        await db.flush()

        # Update qdrant_id after flush (to get generated UUIDs)
        for db_chunk, vec_chunk in zip(db_chunks, vector_chunks):
            db_chunk.qdrant_id = vec_chunk["id"]
            vec_chunk["id"] = str(db_chunk.id)

        # 6. Ensure collection exists and index vectors
        await vector_store.ensure_collection()
        await vector_store.upsert_chunks(vector_chunks)

        # 7. Update document status
        document.status = DocumentStatus.READY.value
        document.processed_at = datetime.now(timezone.utc)
        document.error_message = None
        await db.commit()

        logger.info(
            f"Document {document_id} processed: "
            f"{document.page_count} pages, {len(chunks)} chunks, "
            f"{tokens_used} tokens, parser={parsed.parser_used}"
        )

        return {
            "document_id": document_id,
            "pages": document.page_count,
            "chunks": len(chunks),
            "tokens_used": tokens_used,
            "parser_used": parsed.parser_used,
        }

    except Exception as e:
        logger.exception(f"Error processing document {document_id}")

        # Update document with error
        document.status = DocumentStatus.FAILED.value
        document.error_message = str(e)[:2000]
        await db.commit()

        return {"error": str(e)}

    finally:
        await db.close()



# ── Web crawl tasks ────────────────────────────────────────────────


async def crawl_website(ctx: dict, web_source_id: str) -> dict:
    """Crawl a web page, chunk, embed and index its content.

    Creates a Document to hold the crawled content, then uses the same
    chunking/embedding/indexing pipeline as uploaded files.

    Args:
        ctx: Arq context
        web_source_id: UUID of the WebSource to process

    Returns:
        Dict with processing results
    """
    import hashlib
    from uuid import uuid4

    ws_uuid = UUID(web_source_id)
    db = await get_db()

    try:
        result = await db.execute(
            select(WebSource).where(WebSource.id == ws_uuid)
        )
        ws = result.scalar_one_or_none()
        if not ws:
            logger.error(f"WebSource {web_source_id} not found")
            return {"error": "WebSource not found"}

        ws.status = "crawling"
        await db.commit()

        logger.info(f"Crawling web source {web_source_id}: {ws.url}")

        # 1. Fetch and parse the web page
        crawl_result = await crawl_url(ws.url)
        ws.title = crawl_result.title

        # 2. Create a Document entry for the crawled content
        content_bytes = crawl_result.text.encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        document = Document(
            id=uuid4(),
            collection_id=ws.collection_id,
            filename=crawl_result.title or ws.url,
            content_type="text/html",
            s3_key=f"web_sources/{ws.tenant_id}/{ws.id}",
            content_hash=content_hash,
            file_size=len(content_bytes),
            status=DocumentStatus.PROCESSING.value,
            page_count=1,
            doc_metadata={"source_url": ws.url, "web_source_id": str(ws.id)},
        )
        db.add(document)
        await db.flush()

        # 3. Create ParsedDocument and chunk
        from app.core.parsing import ParsedDocument, ParsedPage

        parsed = ParsedDocument(
            pages=[ParsedPage(page_number=1, content=crawl_result.text)],
            total_pages=1,
            metadata={"title": crawl_result.title, "url": ws.url},
            parser_used="web_crawler",
        )

        chunks = chunk_document(parsed)
        document.chunk_count = len(chunks)

        if not chunks:
            document.status = DocumentStatus.READY.value
            document.processed_at = datetime.now(timezone.utc)
            ws.status = "ready"
            ws.last_crawled_at = datetime.now(timezone.utc)
            await db.commit()
            return {"message": "No content to index", "chunks": 0}

        # 4. Embed
        chunk_texts = [c.content for c in chunks]
        embeddings, tokens_used = await embedding_service.embed_texts(chunk_texts)
        document.tokens_used = tokens_used

        # 5. Index in PG + Qdrant
        db_chunks = []
        vector_chunks = []

        for chunk, embedding in zip(chunks, embeddings):
            db_chunk = Chunk(
                document_id=document.id,
                tenant_id=ws.tenant_id,
                collection_id=ws.collection_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                content_hash=chunk.content_hash,
                token_count=chunk.token_count,
                content_tsv=sa_func.to_tsvector(settings.postgres_fts_config, chunk.content),
                page_number=1,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                section_title=crawl_result.title,
            )
            db.add(db_chunk)
            db_chunks.append(db_chunk)

            vector_chunks.append({
                "id": str(db_chunk.id),
                "vector": embedding,
                "payload": {
                    "tenant_id": str(ws.tenant_id),
                    "collection_id": str(ws.collection_id),
                    "document_id": str(document.id),
                    "document_filename": crawl_result.title or ws.url,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "page_number": 1,
                    "section_title": crawl_result.title,
                    "source_url": ws.url,
                },
            })

        await db.flush()

        for db_chunk, vec_chunk in zip(db_chunks, vector_chunks):
            db_chunk.qdrant_id = vec_chunk["id"]
            vec_chunk["id"] = str(db_chunk.id)

        await vector_store.ensure_collection()
        await vector_store.upsert_chunks(vector_chunks)

        # 6. Update statuses
        document.status = DocumentStatus.READY.value
        document.processed_at = datetime.now(timezone.utc)
        ws.status = "ready"
        ws.last_crawled_at = datetime.now(timezone.utc)
        ws.error_message = None
        await db.commit()

        logger.info(
            f"WebSource {web_source_id} crawled: {len(chunks)} chunks, "
            f"{tokens_used} tokens"
        )
        return {
            "web_source_id": web_source_id,
            "url": ws.url,
            "chunks": len(chunks),
            "tokens_used": tokens_used,
        }

    except Exception as e:
        logger.exception(f"Error crawling web source {web_source_id}")
        try:
            ws.status = "failed"
            ws.error_message = str(e)[:2000]
            await db.commit()
        except Exception:
            pass
        return {"error": str(e)}

    finally:
        await db.close()


# ── Mail tasks ──────────────────────────────────────────────────────


def _get_proxy(account: MailAccount):
    """Build a NangoProxy for a mail account."""
    from app.integrations.nango.models import NangoConnection

    return nango_client.proxy(
        connection_id=account.nango_connection.nango_connection_id,
        provider_config_key=account.provider,
    )


def _parse_message(provider: str, raw_payload: dict):
    """Parse a raw message payload for the given provider."""
    if provider == "gmail":
        return parse_gmail_message(raw_payload)
    return parse_graph_message(raw_payload)


async def _upsert_message(db: AsyncSession, account: MailAccount, parsed) -> None:
    """Insert or update a mail message in the database."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(MailMessage).values(
        tenant_id=account.tenant_id,
        mail_account_id=account.id,
        provider_message_id=parsed.provider_message_id,
        provider_thread_id=parsed.provider_thread_id,
        internet_message_id=parsed.internet_message_id,
        sender=parsed.sender,
        to_recipients=parsed.to_recipients,
        cc_recipients=parsed.cc_recipients,
        bcc_recipients=parsed.bcc_recipients,
        subject=parsed.subject,
        date=parsed.date,
        snippet=parsed.snippet,
        body_text=parsed.body_text,
        body_html=parsed.body_html,
        is_read=parsed.is_read,
        is_sent=parsed.is_sent,
        is_draft=parsed.is_draft,
        has_attachments=parsed.has_attachments,
        raw_headers=parsed.raw_headers,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_mail_msg_account_provider",
        set_={
            "provider_thread_id": stmt.excluded.provider_thread_id,
            "snippet": stmt.excluded.snippet,
            "body_text": stmt.excluded.body_text,
            "body_html": stmt.excluded.body_html,
            "is_read": stmt.excluded.is_read,
            "is_sent": stmt.excluded.is_sent,
            "is_draft": stmt.excluded.is_draft,
            "has_attachments": stmt.excluded.has_attachments,
            "raw_headers": stmt.excluded.raw_headers,
            "updated_at": sa_func.now(),
        },
    )
    await db.execute(stmt)


async def send_email(ctx: dict, send_request_id: str) -> dict:
    """Send an email via the appropriate provider.

    Idempotent: if the request is already sent, returns early.
    On success, enqueues sync_thread to refresh the thread view.
    """
    req_uuid = UUID(send_request_id)
    db = await get_db()

    try:
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(MailSendRequest)
            .where(MailSendRequest.id == req_uuid)
            .options(
                selectinload(MailSendRequest.mail_account).selectinload(
                    MailAccount.nango_connection
                ),
                selectinload(MailSendRequest.in_reply_to),
            )
        )
        req = result.scalar_one_or_none()
        if not req:
            logger.error("Send request %s not found", send_request_id)
            return {"error": "Send request not found"}

        # Idempotency
        if req.status == "sent":
            logger.info("Send request %s already sent", send_request_id)
            return {"status": "sent", "provider_message_id": req.provider_message_id}

        account = req.mail_account
        if not account:
            req.status = "failed"
            req.error_message = "Mail account missing"
            await db.commit()
            return {"error": req.error_message}

        # SMTP uses smtp_config; OAuth uses nango_connection
        if account.provider == "smtp":
            if not account.smtp_config:
                req.status = "failed"
                req.error_message = "SMTP account has no configuration"
                await db.commit()
                return {"error": req.error_message}
        else:
            if not account.nango_connection:
                req.status = "failed"
                req.error_message = "Mail account or Nango connection missing"
                await db.commit()
                return {"error": req.error_message}

        # Mark as sending
        req.status = "sending"
        await db.commit()

        if account.provider == "smtp":
            provider = get_mail_provider(account.provider, smtp_config=account.smtp_config)
        else:
            proxy = _get_proxy(account)
            provider = get_mail_provider(account.provider, proxy)

        payload = SendPayload(
            to=req.to_recipients,
            cc=req.cc_recipients,
            bcc=req.bcc_recipients,
            subject=req.subject,
            body_text=req.body_text,
            body_html=req.body_html,
        )

        if req.mode == "reply" and req.provider_thread_id:
            # Get In-Reply-To and References from the original message
            in_reply_to_header = ""
            references_list: list[str] = []
            if req.in_reply_to:
                in_reply_to_header = req.in_reply_to.internet_message_id or ""
                if req.in_reply_to.raw_headers:
                    refs = req.in_reply_to.raw_headers.get("References", "")
                    if refs:
                        references_list = refs.split()
                if in_reply_to_header and in_reply_to_header not in references_list:
                    references_list.append(in_reply_to_header)

            send_result = await provider.send_reply(
                payload,
                thread_id=req.provider_thread_id,
                in_reply_to=in_reply_to_header,
                references=references_list,
            )
        else:
            send_result = await provider.send_new(payload)

        # Success
        req.status = "sent"
        req.provider_message_id = send_result.message_id or None
        req.error_code = None
        req.error_message = None
        await db.commit()

        # Post-send: refresh thread or full sync (SMTP has no inbox)
        if account.provider != "smtp":
            redis: ArqRedis = ctx.get("redis")  # type: ignore[assignment]
            if redis:
                if send_result.thread_id:
                    await redis.enqueue_job(
                        "sync_thread", str(account.id), send_result.thread_id
                    )
                else:
                    await redis.enqueue_job("sync_mail_account", str(account.id))

        logger.info(
            "Email sent via %s: request=%s message_id=%s",
            account.provider,
            send_request_id,
            send_result.message_id,
        )
        return {
            "status": "sent",
            "provider_message_id": send_result.message_id,
            "thread_id": send_result.thread_id,
        }

    except Exception as e:
        logger.exception("Failed to send email: request=%s", send_request_id)
        try:
            req.status = "failed"
            req.error_code = type(e).__name__
            req.error_message = str(e)[:2000]
            await db.commit()
        except Exception:
            pass
        return {"error": str(e)}

    finally:
        await db.close()


async def sync_mail_account(ctx: dict, account_id: str) -> dict:
    """Sync a mail account: initial or incremental depending on cursor state."""
    acct_uuid = UUID(account_id)
    db = await get_db()

    try:
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(MailAccount)
            .where(MailAccount.id == acct_uuid)
            .options(
                selectinload(MailAccount.nango_connection),
                selectinload(MailAccount.sync_state),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            logger.error("Mail account %s not found", account_id)
            return {"error": "Account not found"}

        if account.status != "connected":
            logger.info("Mail account %s not connected, skipping sync", account_id)
            return {"skipped": True}

        # SMTP has no inbox to sync
        if account.provider == "smtp":
            logger.info("Mail account %s is SMTP, no sync needed", account_id)
            return {"skipped": True, "reason": "smtp"}

        if not account.nango_connection:
            logger.error("Mail account %s has no Nango connection", account_id)
            return {"error": "No Nango connection"}

        sync_state = account.sync_state
        if not sync_state:
            sync_state = MailSyncState(mail_account_id=account.id)
            db.add(sync_state)
            await db.flush()

        if sync_state.status == "syncing":
            logger.info("Mail account %s already syncing, skipping", account_id)
            return {"skipped": True}

        # Mark syncing
        sync_state.status = "syncing"
        sync_state.error = None
        await db.commit()

        proxy = _get_proxy(account)
        provider = get_mail_provider(account.provider, proxy)

        # Determine cursor
        cursor: str | None = None
        if account.provider == "gmail":
            cursor = sync_state.gmail_history_id
        elif account.provider == "microsoft":
            cursor = sync_state.graph_delta_link

        # Sync
        if cursor:
            sync_result = await provider.incremental_sync(cursor)
        else:
            sync_result = await provider.initial_sync(since_days=30)

        # Upsert messages
        count = 0
        for raw_msg in sync_result.messages:
            try:
                parsed = _parse_message(account.provider, raw_msg.raw_payload)
                await _upsert_message(db, account, parsed)
                count += 1
            except Exception as e:
                logger.warning(
                    "Failed to upsert message %s: %s",
                    raw_msg.provider_message_id,
                    e,
                )

        # Update cursor
        if sync_result.cursor:
            if account.provider == "gmail":
                sync_state.gmail_history_id = sync_result.cursor
            elif account.provider == "microsoft":
                sync_state.graph_delta_link = sync_result.cursor

        sync_state.status = "idle"
        sync_state.last_synced_at = datetime.now(timezone.utc)
        sync_state.error = None
        await db.commit()

        # Index new emails into RAG
        indexed_chunks = 0
        try:
            from app.services.mail.indexer import (
                get_or_create_email_collection,
                index_unindexed_emails,
            )

            email_collection_id = await get_or_create_email_collection(
                db, account.tenant_id
            )
            indexed_chunks = await index_unindexed_emails(
                db, account.id, account.tenant_id, email_collection_id
            )
            if indexed_chunks:
                await db.commit()
                logger.info(
                    "Indexed %d email chunks for account %s",
                    indexed_chunks,
                    account_id,
                )
        except Exception as e:
            logger.warning(
                "Email RAG indexing failed for account %s: %s", account_id, e
            )

        logger.info(
            "Mail sync complete: account=%s provider=%s upserted=%d indexed_chunks=%d",
            account_id,
            account.provider,
            count,
            indexed_chunks,
        )
        return {"upserted": count, "cursor": sync_result.cursor, "indexed_chunks": indexed_chunks}

    except Exception as e:
        logger.exception("Mail sync failed: account=%s", account_id)
        try:
            if sync_state:
                sync_state.status = "error"
                sync_state.error = str(e)[:2000]
                await db.commit()
        except Exception:
            pass
        return {"error": str(e)}

    finally:
        await db.close()


async def sync_thread(ctx: dict, account_id: str, provider_thread_id: str) -> dict:
    """Sync a single thread (on-demand, e.g. after sending)."""
    acct_uuid = UUID(account_id)
    db = await get_db()

    try:
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(MailAccount)
            .where(MailAccount.id == acct_uuid)
            .options(selectinload(MailAccount.nango_connection))
        )
        account = result.scalar_one_or_none()
        if not account:
            return {"error": "Account not found"}
        if account.provider == "smtp":
            return {"error": "SMTP has no inbox"}
        if not account.nango_connection:
            return {"error": "No Nango connection"}

        proxy = _get_proxy(account)
        provider = get_mail_provider(account.provider, proxy)

        raw_messages = await provider.fetch_thread(provider_thread_id)

        count = 0
        for raw_msg in raw_messages:
            try:
                parsed = _parse_message(account.provider, raw_msg.raw_payload)
                await _upsert_message(db, account, parsed)
                count += 1
            except Exception as e:
                logger.warning(
                    "Failed to upsert thread message %s: %s",
                    raw_msg.provider_message_id,
                    e,
                )

        await db.commit()
        logger.info(
            "Thread sync: account=%s thread=%s upserted=%d",
            account_id,
            provider_thread_id,
            count,
        )
        return {"upserted": count}

    except Exception as e:
        logger.exception(
            "Thread sync failed: account=%s thread=%s",
            account_id,
            provider_thread_id,
        )
        return {"error": str(e)}

    finally:
        await db.close()


async def sync_all_mail_accounts(ctx: dict) -> dict:
    """Cron job: enqueue sync for all connected mail accounts."""
    db = await get_db()
    try:
        result = await db.execute(
            select(MailAccount).where(MailAccount.status == "connected")
        )
        accounts = result.scalars().all()

        redis: ArqRedis | None = ctx.get("redis")  # type: ignore[assignment]
        if not redis:
            logger.error("No Redis in ctx for cron job")
            return {"error": "No Redis"}

        enqueued = 0
        for account in accounts:
            await redis.enqueue_job("sync_mail_account", str(account.id))
            enqueued += 1

        logger.info("Cron: enqueued sync for %d mail accounts", enqueued)
        return {"enqueued": enqueued}

    finally:
        await db.close()


# ── Lifecycle ───────────────────────────────────────────────────────


async def startup(ctx: dict) -> None:
    """Worker startup hook."""
    logger.info("Worker starting up...")
    await vector_store.ensure_collection()

    # Register all agent tools once at startup
    from app.core.tool_registry import register_builtin_tools
    register_builtin_tools()
    logger.info("Tool registry initialized")


async def shutdown(ctx: dict) -> None:
    """Worker shutdown hook."""
    logger.info("Worker shutting down...")
    # Close agent stream redis if it was opened
    stream_redis = ctx.get("stream_redis")
    if stream_redis:
        await stream_redis.aclose()
    await engine.dispose()


async def send_scheduled_emails(ctx: dict) -> dict:
    """
    Cron job: Send all emails that are scheduled to be sent now or in the past.
    Runs every minute.
    """
    async with async_session_maker() as db:
        now = datetime.now(timezone.utc)

        # Find all pending scheduled emails that should be sent
        result = await db.execute(
            select(ScheduledEmail)
            .where(
                ScheduledEmail.status == "pending",
                ScheduledEmail.scheduled_at <= now,
            )
            .order_by(ScheduledEmail.scheduled_at.asc())
            .limit(100)  # Process max 100 per run
        )
        scheduled_emails = list(result.scalars().all())

        if not scheduled_emails:
            return {"sent": 0, "failed": 0}

        logger.info(f"Found {len(scheduled_emails)} scheduled emails to send")

        sent_count = 0
        failed_count = 0

        for scheduled_email in scheduled_emails:
            try:
                # Create MailSendRequest
                send_request = MailSendRequest(
                    tenant_id=scheduled_email.tenant_id,
                    mail_account_id=scheduled_email.mail_account_id,
                    client_send_id=scheduled_email.id,  # Use scheduled email ID as idempotency key
                    mode=scheduled_email.mode,
                    to_recipients=scheduled_email.to_recipients,
                    cc_recipients=scheduled_email.cc_recipients,
                    bcc_recipients=scheduled_email.bcc_recipients,
                    subject=scheduled_email.subject,
                    body_text=scheduled_email.body_text,
                    body_html=scheduled_email.body_html,
                    in_reply_to_message_id=scheduled_email.in_reply_to_message_id,
                    provider_thread_id=scheduled_email.provider_thread_id,
                    status="pending",
                )
                db.add(send_request)
                await db.flush()

                # Enqueue send_email task
                redis_pool: ArqRedis = ctx["redis"]
                await redis_pool.enqueue_job("send_email", str(send_request.id))

                # Mark as sent (actual sending happens in send_email task)
                scheduled_email.status = "sent"
                scheduled_email.sent_at = now
                sent_count += 1

                logger.info(f"Enqueued scheduled email {scheduled_email.id} for sending")

            except Exception as e:
                logger.error(f"Failed to send scheduled email {scheduled_email.id}: {e}")
                scheduled_email.status = "failed"
                scheduled_email.error = str(e)
                failed_count += 1

        await db.commit()

        logger.info(f"Scheduled emails: sent={sent_count}, failed={failed_count}")
        return {"sent": sent_count, "failed": failed_count}


class WorkerSettings:
    """Arq worker settings."""

    from app.workers.agent_tasks import run_agent, watchdog_stuck_runs
    from app.workers.presentation_tasks import (
        generate_presentation_outline,
        generate_presentation_slides,
        export_presentation,
    )

    functions = [
        process_document, crawl_website, send_email, sync_mail_account, sync_thread, run_agent,
        generate_presentation_outline, generate_presentation_slides, export_presentation,
    ]
    cron_jobs = [
        cron(
            sync_all_mail_accounts,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
        ),
        cron(
            watchdog_stuck_runs,
            minute={0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30,
                    32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58},
        ),
        cron(
            send_scheduled_emails,
            minute=None,  # Run every minute
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings
    max_jobs = 10
    job_timeout = 600  # 10 minutes max per job
    keep_result = 3600  # Keep results for 1 hour
