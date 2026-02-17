"""Mail integration endpoints.

Manages mail accounts (connect via Nango), threads, messages,
and reliable email sending via the outbox pattern.

All queries enforce multi-tenant isolation via ``user.tenant_id``.
"""

import logging
from uuid import UUID, uuid4

from arq import create_pool
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func as sa_func, case, literal_column
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession
from app.integrations.nango.client import nango_client
from app.integrations.nango.models import NangoConnection, assistant_integrations
from app.models.mail import MailAccount, MailMessage, MailSendRequest, MailSyncState
from app.schemas.mail import (
    MailAccountConnectResponse,
    MailAccountRead,
    MailMessageRead,
    MailSendRequestCreate,
    MailSendResponse,
    MailSendStatusRead,
    MailThreadRead,
    MailThreadSummary,
)
from app.workers.settings import redis_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_account_for_tenant(
    db, account_id: UUID, tenant_id: UUID
) -> MailAccount:
    """Load a MailAccount, verifying tenant ownership."""
    result = await db.execute(
        select(MailAccount)
        .where(MailAccount.id == account_id, MailAccount.tenant_id == tenant_id)
        .options(selectinload(MailAccount.nango_connection))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mail account not found",
        )
    return account


async def _get_arq():
    pool = await create_pool(redis_settings)
    return pool


# ── Accounts ─────────────────────────────────────────────────────────


@router.get("/accounts", response_model=list[MailAccountRead])
async def list_mail_accounts(user: CurrentUser, db: DbSession):
    """List all mail accounts for the current tenant."""
    result = await db.execute(
        select(MailAccount)
        .where(MailAccount.tenant_id == user.tenant_id)
        .order_by(MailAccount.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/accounts/connect/{provider}",
    response_model=MailAccountConnectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_mail_account(
    provider: str,
    user: CurrentUser,
    db: DbSession,
):
    """Initiate OAuth connection for a mail account.

    Creates a pending MailAccount and returns the Nango OAuth URL.
    The frontend should open this URL, then call ``/finalize`` after
    the popup closes.
    """
    if provider not in ("gmail", "microsoft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider must be 'gmail' or 'microsoft'",
        )

    tenant_id = user.tenant_id
    connection_id = f"{tenant_id}:{provider}"

    # Create or update NangoConnection (reuse existing flow)
    result = await db.execute(
        select(NangoConnection).where(
            NangoConnection.tenant_id == tenant_id,
            NangoConnection.provider == provider,
        )
    )
    nango_conn = result.scalar_one_or_none()

    if nango_conn:
        nango_conn.status = "pending"
    else:
        nango_conn = NangoConnection(
            id=uuid4(),
            tenant_id=tenant_id,
            provider=provider,
            nango_connection_id=connection_id,
            status="pending",
        )
        db.add(nango_conn)

    await db.flush()

    # Check if a MailAccount already exists for this tenant+provider
    result = await db.execute(
        select(MailAccount).where(
            MailAccount.tenant_id == tenant_id,
            MailAccount.provider == provider,
        )
    )
    mail_account = result.scalar_one_or_none()

    if mail_account:
        mail_account.status = "pending"
        mail_account.nango_conn_id = nango_conn.id
    else:
        mail_account = MailAccount(
            tenant_id=tenant_id,
            user_id=user.id,
            provider=provider,
            nango_conn_id=nango_conn.id,
            status="pending",
        )
        db.add(mail_account)

    await db.flush()

    # Create sync state if needed
    result = await db.execute(
        select(MailSyncState).where(
            MailSyncState.mail_account_id == mail_account.id
        )
    )
    if not result.scalar_one_or_none():
        db.add(MailSyncState(mail_account_id=mail_account.id))

    await db.flush()

    connect_url = nango_client.get_oauth_connect_url(
        provider_config_key=provider,
        connection_id=connection_id,
    )

    return MailAccountConnectResponse(
        account_id=mail_account.id,
        connect_url=connect_url,
        provider=provider,
    )


@router.get("/accounts/{account_id}/finalize", response_model=MailAccountRead)
async def finalize_mail_account(
    account_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Finalize a mail account after OAuth popup closes.

    Verifies the Nango connection is active, fetches the email profile,
    and enqueues initial sync.
    """
    account = await _get_account_for_tenant(db, account_id, user.tenant_id)

    if not account.nango_conn_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Nango connection linked",
        )

    nango_conn = account.nango_connection
    if not nango_conn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nango connection not found",
        )

    # Verify with Nango that the connection is ready
    try:
        await nango_client.get_connection(
            provider_config_key=account.provider,
            connection_id=nango_conn.nango_connection_id,
        )
    except Exception as e:
        logger.warning("Nango connection not ready: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth connection not completed yet. Please try again.",
        )

    # Update Nango connection status
    nango_conn.status = "connected"

    # Fetch profile (email address)
    try:
        from app.services.mail.factory import get_mail_provider

        proxy = nango_client.proxy(
            connection_id=nango_conn.nango_connection_id,
            provider_config_key=account.provider,
        )
        provider = get_mail_provider(account.provider, proxy)
        profile = await provider.get_profile()
        account.email_address = profile.get("email_address", "")
    except Exception as e:
        logger.warning("Failed to fetch mail profile: %s", e)
        # Continue anyway — email_address will be filled on sync

    account.status = "connected"
    await db.flush()

    # Enqueue initial sync
    try:
        pool = await _get_arq()
        await pool.enqueue_job("sync_mail_account", str(account.id))
        await pool.close()
    except Exception as e:
        logger.warning("Failed to enqueue initial sync: %s", e)

    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_200_OK)
async def delete_mail_account(
    account_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Delete a mail account and all associated data.

    Only deletes the NangoConnection if no other entity references it.
    """
    account = await _get_account_for_tenant(db, account_id, user.tenant_id)
    nango_conn = account.nango_connection

    # Delete the mail account (cascades to messages, sync_state, send_requests)
    await db.delete(account)
    await db.flush()

    # Check if the NangoConnection is still referenced
    if nango_conn:
        # Check other mail accounts
        result = await db.execute(
            select(sa_func.count())
            .select_from(MailAccount)
            .where(MailAccount.nango_conn_id == nango_conn.id)
        )
        other_mail_count = result.scalar_one()

        # Check assistant integrations
        result = await db.execute(
            select(sa_func.count())
            .select_from(assistant_integrations)
            .where(
                assistant_integrations.c.nango_connection_id == nango_conn.id
            )
        )
        other_assistant_count = result.scalar_one()

        if other_mail_count == 0 and other_assistant_count == 0:
            try:
                await nango_client.delete_connection(
                    provider_config_key=nango_conn.provider,
                    connection_id=nango_conn.nango_connection_id,
                )
            except Exception as e:
                logger.warning("Failed to delete Nango connection: %s", e)
            await db.delete(nango_conn)

    return {"status": "deleted"}


# ── Send ─────────────────────────────────────────────────────────────


@router.post("/send", response_model=MailSendResponse)
async def send_email(
    data: MailSendRequestCreate,
    user: CurrentUser,
    db: DbSession,
):
    """Queue an email for sending.

    Uses ``client_send_id`` for idempotency: if the same ID is submitted
    twice, the existing request is returned instead of creating a duplicate.
    """
    tenant_id = user.tenant_id

    # Verify account belongs to tenant
    await _get_account_for_tenant(db, data.mail_account_id, tenant_id)

    # Check idempotency
    result = await db.execute(
        select(MailSendRequest).where(
            MailSendRequest.tenant_id == tenant_id,
            MailSendRequest.client_send_id == data.client_send_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return MailSendResponse(
            id=existing.id,
            client_send_id=existing.client_send_id,
            status=existing.status,
        )

    # Create send request
    req = MailSendRequest(
        tenant_id=tenant_id,
        mail_account_id=data.mail_account_id,
        client_send_id=data.client_send_id,
        mode=data.mode,
        to_recipients=data.to_recipients,
        cc_recipients=data.cc_recipients,
        bcc_recipients=data.bcc_recipients,
        subject=data.subject,
        body_text=data.body_text,
        body_html=data.body_html,
        in_reply_to_message_id=data.in_reply_to_message_id,
        provider_thread_id=data.provider_thread_id,
        status="queued",
    )
    db.add(req)
    await db.flush()

    # Enqueue worker job
    try:
        pool = await _get_arq()
        await pool.enqueue_job("send_email", str(req.id))
        await pool.close()
    except Exception as e:
        logger.error("Failed to enqueue send_email: %s", e)
        req.status = "failed"
        req.error_message = f"Failed to queue: {e}"
        await db.flush()

    return MailSendResponse(
        id=req.id,
        client_send_id=req.client_send_id,
        status=req.status,
    )


@router.get("/send-status/{client_send_id}", response_model=MailSendStatusRead)
async def get_send_status(
    client_send_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Poll the status of a send request."""
    result = await db.execute(
        select(MailSendRequest).where(
            MailSendRequest.tenant_id == user.tenant_id,
            MailSendRequest.client_send_id == client_send_id,
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Send request not found",
        )
    return req


# ── Threads & Messages ──────────────────────────────────────────────


@router.get("/threads", response_model=list[MailThreadSummary])
async def list_threads(
    user: CurrentUser,
    db: DbSession,
    account_id: UUID = Query(...),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """List email threads for a mail account."""
    tenant_id = user.tenant_id

    # Verify account ownership
    await _get_account_for_tenant(db, account_id, tenant_id)

    # Build thread_key = COALESCE(provider_thread_id, provider_message_id)
    thread_key = sa_func.coalesce(
        MailMessage.provider_thread_id, MailMessage.provider_message_id
    ).label("thread_key")

    stmt = (
        select(
            thread_key,
            sa_func.max(MailMessage.subject).label("subject"),
            sa_func.max(MailMessage.date).label("last_date"),
            sa_func.max(MailMessage.snippet).label("snippet"),
            sa_func.count(MailMessage.id).label("message_count"),
        )
        .where(
            MailMessage.mail_account_id == account_id,
            MailMessage.tenant_id == tenant_id,
        )
        .group_by(thread_key)
        .order_by(sa_func.max(MailMessage.date).desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    rows = result.all()

    threads = []
    for row in rows:
        # Fetch participants for this thread
        participants_stmt = (
            select(MailMessage.sender)
            .where(
                MailMessage.mail_account_id == account_id,
                MailMessage.tenant_id == tenant_id,
                sa_func.coalesce(
                    MailMessage.provider_thread_id,
                    MailMessage.provider_message_id,
                )
                == row.thread_key,
            )
            .distinct()
        )
        participants_result = await db.execute(participants_stmt)
        participants = [p[0] for p in participants_result.all()]

        threads.append(
            MailThreadSummary(
                thread_key=row.thread_key,
                subject=row.subject,
                last_date=row.last_date,
                snippet=row.snippet,
                message_count=row.message_count,
                participants=participants,
            )
        )

    return threads


@router.get("/threads/{thread_key}", response_model=MailThreadRead)
async def get_thread(
    thread_key: str,
    user: CurrentUser,
    db: DbSession,
    account_id: UUID = Query(...),
):
    """Get all messages in a thread."""
    tenant_id = user.tenant_id
    await _get_account_for_tenant(db, account_id, tenant_id)

    result = await db.execute(
        select(MailMessage)
        .where(
            MailMessage.mail_account_id == account_id,
            MailMessage.tenant_id == tenant_id,
            (
                (MailMessage.provider_thread_id == thread_key)
                | (MailMessage.provider_message_id == thread_key)
            ),
        )
        .order_by(MailMessage.date.asc())
    )
    messages = list(result.scalars().all())

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    return MailThreadRead(
        thread_key=thread_key,
        subject=messages[0].subject,
        messages=messages,
    )


@router.get("/messages/{message_id}", response_model=MailMessageRead)
async def get_message(
    message_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Get a single message by ID."""
    result = await db.execute(
        select(MailMessage).where(
            MailMessage.id == message_id,
            MailMessage.tenant_id == user.tenant_id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    return message


# ── Sync (admin/debug) ──────────────────────────────────────────────


@router.post("/sync/{account_id}")
async def trigger_sync(
    account_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Manually trigger a sync for a mail account."""
    await _get_account_for_tenant(db, account_id, user.tenant_id)

    pool = await _get_arq()
    await pool.enqueue_job("sync_mail_account", str(account_id))
    await pool.close()

    return {"status": "sync_queued"}
