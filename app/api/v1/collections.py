"""Collection endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import CurrentUser, DbSession
from app.models.collection import Collection
from app.models.document import Document
from app.models.chunk import Chunk
from app.schemas.collection import (
    CollectionCreate,
    CollectionRead,
    CollectionReadWithStats,
    CollectionUpdate,
)

router = APIRouter()


@router.get("", response_model=list[CollectionReadWithStats])
async def list_collections(
    user: CurrentUser,
    db: DbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List collections for tenant with document stats."""
    tenant_id = user.tenant_id
    
    # Get collections with document count
    result = await db.execute(
        select(
            Collection,
            func.count(Document.id).label("documents_count"),
        )
        .outerjoin(Document)
        .where(Collection.tenant_id == tenant_id)
        .group_by(Collection.id)
        .order_by(Collection.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    collections_data = []
    for row in result.all():
        collection = row[0]
        doc_count = row[1]
        
        # Get total chunks
        chunk_result = await db.execute(
            select(func.count(Chunk.id))
            .join(Document)
            .where(Document.collection_id == collection.id)
        )
        chunk_count = chunk_result.scalar() or 0
        
        collections_data.append({
            **CollectionRead.model_validate(collection).model_dump(),
            "documents_count": doc_count,
            "total_chunks": chunk_count,
        })
    
    return collections_data


@router.get("/{collection_id}", response_model=CollectionReadWithStats)
async def get_collection(
    collection_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get a specific collection with stats."""
    result = await db.execute(
        select(Collection)
        .where(Collection.id == collection_id)
        .where(Collection.tenant_id == user.tenant_id)
    )
    collection = result.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )
    
    # Get document count
    doc_result = await db.execute(
        select(func.count(Document.id))
        .where(Document.collection_id == collection_id)
    )
    doc_count = doc_result.scalar() or 0
    
    # Get chunk count
    chunk_result = await db.execute(
        select(func.count(Chunk.id))
        .join(Document)
        .where(Document.collection_id == collection_id)
    )
    chunk_count = chunk_result.scalar() or 0
    
    return {
        **CollectionRead.model_validate(collection).model_dump(),
        "documents_count": doc_count,
        "total_chunks": chunk_count,
    }


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
async def create_collection(
    data: CollectionCreate,
    user: CurrentUser,
    db: DbSession,
) -> Collection:
    """Create a new collection."""
    collection = Collection(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return collection


@router.patch("/{collection_id}", response_model=CollectionRead)
async def update_collection(
    collection_id: UUID,
    data: CollectionUpdate,
    user: CurrentUser,
    db: DbSession,
) -> Collection:
    """Update a collection."""
    result = await db.execute(
        select(Collection)
        .where(Collection.id == collection_id)
        .where(Collection.tenant_id == user.tenant_id)
    )
    collection = result.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(collection, key, value)
    
    await db.commit()
    await db.refresh(collection)
    return collection


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a collection and all its documents."""
    from app.core.vector_store import vector_store
    
    result = await db.execute(
        select(Collection)
        .where(Collection.id == collection_id)
        .where(Collection.tenant_id == user.tenant_id)
    )
    collection = result.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )
    
    # Delete all vectors for this collection
    await vector_store.delete_by_collection(collection_id)
    
    # Delete from DB (cascades to documents and chunks)
    await db.delete(collection)
    await db.commit()
