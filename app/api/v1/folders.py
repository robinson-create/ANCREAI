"""Folder endpoints — CRUD for folders and folder items."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession
from app.models.assistant import Assistant
from app.models.folder import Folder, FolderItem
from app.models.mail import MailAccount, MailMessage
from app.models.message import Message
from app.models.workspace_document import WorkspaceDocument
from app.schemas.folder import (
    FolderCreate,
    FolderItemAdd,
    FolderItemRead,
    FolderRead,
    FolderUpdate,
)

router = APIRouter()


def _item_counts(items: list[FolderItem]) -> dict[str, int]:
    """Count items by type."""
    counts = {"conversation": 0, "document": 0, "email_thread": 0}
    for item in items:
        if item.item_type in counts:
            counts[item.item_type] += 1
    return counts


@router.get("", response_model=list[FolderRead])
async def list_folders(
    user: CurrentUser,
    db: DbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[FolderRead]:
    """List folders for the tenant with item counts."""
    result = await db.execute(
        select(Folder)
        .where(Folder.tenant_id == user.tenant_id)
        .options(selectinload(Folder.items))
        .order_by(Folder.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    folders = list(result.scalars().unique().all())
    return [
        FolderRead(
            id=f.id,
            name=f.name,
            description=f.description,
            color=f.color,
            item_counts=_item_counts(f.items),
            created_at=f.created_at,
            updated_at=f.updated_at,
        )
        for f in folders
    ]


@router.post("", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
async def create_folder(
    data: FolderCreate,
    user: CurrentUser,
    db: DbSession,
) -> FolderRead:
    """Create a new folder."""
    folder = Folder(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        color=data.color,
    )
    db.add(folder)
    await db.flush()
    await db.refresh(folder)
    return FolderRead(
        id=folder.id,
        name=folder.name,
        description=folder.description,
        color=folder.color,
        item_counts={"conversation": 0, "document": 0, "email_thread": 0},
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.get("/{folder_id}", response_model=FolderRead)
async def get_folder(
    folder_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> FolderRead:
    """Get a folder by ID."""
    result = await db.execute(
        select(Folder)
        .where(Folder.id == folder_id, Folder.tenant_id == user.tenant_id)
        .options(selectinload(Folder.items))
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dossier introuvable.",
        )
    return FolderRead(
        id=folder.id,
        name=folder.name,
        description=folder.description,
        color=folder.color,
        item_counts=_item_counts(folder.items),
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.patch("/{folder_id}", response_model=FolderRead)
async def update_folder(
    folder_id: UUID,
    data: FolderUpdate,
    user: CurrentUser,
    db: DbSession,
) -> FolderRead:
    """Update folder metadata."""
    result = await db.execute(
        select(Folder)
        .where(Folder.id == folder_id, Folder.tenant_id == user.tenant_id)
        .options(selectinload(Folder.items))
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dossier introuvable.",
        )
    if data.name is not None:
        folder.name = data.name
    if data.description is not None:
        folder.description = data.description
    if data.color is not None:
        folder.color = data.color
    await db.flush()
    await db.refresh(folder)
    return FolderRead(
        id=folder.id,
        name=folder.name,
        description=folder.description,
        color=folder.color,
        item_counts=_item_counts(folder.items),
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a folder and its item links (not the underlying items)."""
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.tenant_id == user.tenant_id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dossier introuvable.",
        )
    await db.delete(folder)
    await db.flush()


@router.get("/{folder_id}/items", response_model=list[FolderItemRead])
async def list_folder_items(
    folder_id: UUID,
    user: CurrentUser,
    db: DbSession,
    item_type: str | None = None,
) -> list[FolderItemRead]:
    """List items in a folder with enriched metadata."""
    result = await db.execute(
        select(Folder)
        .where(Folder.id == folder_id, Folder.tenant_id == user.tenant_id)
        .options(selectinload(Folder.items))
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dossier introuvable.",
        )
    items = folder.items
    if item_type:
        items = [i for i in items if i.item_type == item_type]

    enriched: list[FolderItemRead] = []
    for fi in items:
        title = "Sans titre"
        subtitle: str | None = None
        date_val: datetime = fi.added_at

        if fi.item_type == "conversation":
            try:
                conv_id = UUID(fi.item_id)
            except ValueError:
                continue
            msg_result = await db.execute(
                select(
                    Message.content,
                    Message.created_at,
                    Message.assistant_id,
                )
                .join(Assistant)
                .where(
                    Message.conversation_id == conv_id,
                    Assistant.tenant_id == user.tenant_id,
                )
                .order_by(Message.created_at.asc())
            )
            first_row = msg_result.first()
            if first_row:
                content = first_row[0] or ""
                title = (content[:50] + "...") if len(content) > 50 else (content or "Conversation")
                date_val = first_row[1]
                msg_count_result = await db.execute(
                    select(func.count(Message.id))
                    .join(Assistant)
                    .where(
                        Message.conversation_id == conv_id,
                        Assistant.tenant_id == user.tenant_id,
                    )
                )
                count = msg_count_result.scalar() or 0
                subtitle = f"{count} message(s)"
            else:
                title = "Conversation"
                subtitle = "Vide"

        elif fi.item_type == "document":
            try:
                doc_uuid = UUID(fi.item_id)
            except ValueError:
                subtitle = "ID invalide"
                enriched.append(
                    FolderItemRead(
                        id=fi.id,
                        item_type=fi.item_type,
                        item_id=fi.item_id,
                        title="Document",
                        subtitle=subtitle,
                        date=fi.added_at,
                        added_at=fi.added_at,
                    )
                )
                continue
            doc_result = await db.execute(
                select(WorkspaceDocument)
                .where(
                    WorkspaceDocument.id == doc_uuid,
                    WorkspaceDocument.tenant_id == user.tenant_id,
                )
            )
            doc = doc_result.scalar_one_or_none()
            if doc:
                title = doc.title or "Sans titre"
                subtitle = f"{doc.doc_type} · {doc.status}"
                date_val = doc.updated_at
            else:
                subtitle = "Supprimé"

        elif fi.item_type == "email_thread":
            thread_result = await db.execute(
                select(MailMessage)
                .where(
                    MailMessage.tenant_id == user.tenant_id,
                    or_(
                        MailMessage.provider_thread_id == fi.item_id,
                        MailMessage.provider_message_id == fi.item_id,
                    ),
                )
                .order_by(MailMessage.date.desc())
            )
            msgs = list(thread_result.scalars().all())
            if msgs:
                title = msgs[0].subject or "(Sans objet)"
                participants = []
                for m in msgs[:3]:
                    s = m.sender
                    if isinstance(s, dict) and s.get("email"):
                        participants.append(s["email"])
                    elif isinstance(s, dict) and s.get("name"):
                        participants.append(s["name"])
                subtitle = ", ".join(set(participants))[:80] if participants else None
                date_val = msgs[0].date or fi.added_at
            else:
                subtitle = "Thread supprimé"

        enriched.append(
            FolderItemRead(
                id=fi.id,
                item_type=fi.item_type,
                item_id=fi.item_id,
                title=title,
                subtitle=subtitle,
                date=date_val,
                added_at=fi.added_at,
            )
        )

    # Sort by date desc
    enriched.sort(key=lambda x: x.date, reverse=True)
    return enriched


@router.post("/{folder_id}/items", response_model=FolderItemRead, status_code=status.HTTP_201_CREATED)
async def add_folder_item(
    folder_id: UUID,
    data: FolderItemAdd,
    user: CurrentUser,
    db: DbSession,
) -> FolderItemRead:
    """Add an item to a folder."""
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.tenant_id == user.tenant_id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dossier introuvable.",
        )

    # Check if already in folder
    existing = await db.execute(
        select(FolderItem).where(
            FolderItem.folder_id == folder_id,
            FolderItem.item_type == data.item_type,
            FolderItem.item_id == data.item_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet élément est déjà dans ce dossier.",
        )

    fi = FolderItem(
        folder_id=folder_id,
        item_type=data.item_type,
        item_id=data.item_id,
    )
    db.add(fi)
    await db.flush()
    await db.refresh(fi)

    # Enrich for response (simplified)
    return FolderItemRead(
        id=fi.id,
        item_type=fi.item_type,
        item_id=fi.item_id,
        title=data.item_id[:30] + "..." if len(data.item_id) > 30 else data.item_id,
        subtitle=None,
        date=fi.added_at,
        added_at=fi.added_at,
    )


@router.delete("/{folder_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_folder_item(
    folder_id: UUID,
    item_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Remove an item from a folder (item_id is the FolderItem.id)."""
    result = await db.execute(
        select(FolderItem)
        .join(Folder)
        .where(
            FolderItem.id == item_id,
            FolderItem.folder_id == folder_id,
            Folder.tenant_id == user.tenant_id,
        )
    )
    fi = result.scalar_one_or_none()
    if not fi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Élément introuvable.",
        )
    await db.delete(fi)
    await db.flush()
