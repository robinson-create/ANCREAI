"""Contact (CRM) endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models.contact import Company
from app.schemas.contact import (
    CompanyCreate,
    CompanyRead,
    ContactBrief,
    ContactCreate,
    ContactImportReport,
    ContactImportRequest,
    ContactRead,
    ContactSearchResult,
    ContactUpdate,
    ContactUpdateRead,
)
from app.services.contact_import import contact_import_service
from app.services.contact_service import contact_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Contacts ────────────────────────────────────────────────────────


@router.get("", response_model=list[ContactBrief])
async def list_contacts(
    user: CurrentUser,
    db: DbSession,
    search: str | None = Query(None, description="Full-text search query"),
    contact_type: str | None = Query(None, description="Filter by contact type"),
    source: str | None = Query(None, description="Filter by source"),
    limit: int = Query(50, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List contacts with filtering and pagination.

    Returns lightweight contact summaries with company name if available.
    """
    contacts = await contact_service.list_contacts(
        db,
        user.tenant_id,
        search_query=search,
        contact_type=contact_type,
        source=source,
        limit=limit,
        offset=offset,
    )

    # Convert to brief format with company name
    result = []
    for c in contacts:
        brief = ContactBrief.model_validate(c)
        if c.company:
            brief.company_name = c.company.company_name
        result.append(brief)

    return result


@router.get("/search", response_model=list[ContactSearchResult])
async def search_contacts(
    user: CurrentUser,
    db: DbSession,
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, le=50, description="Maximum results"),
):
    """Full-text search contacts with relevance ranking.

    Uses PostgreSQL FTS with French stemming.
    """
    results = await contact_service.search_contacts(db, user.tenant_id, q, limit)

    return [
        ContactSearchResult(
            **contact.__dict__, company=contact.company, relevance_score=score
        )
        for contact, score in results
    ]


@router.get("/{contact_id}", response_model=ContactRead)
async def get_contact(
    contact_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Get contact by ID with full details."""
    contact = await contact_service.get_contact(db, contact_id, user.tenant_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    return contact


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
async def create_contact(
    data: ContactCreate,
    user: CurrentUser,
    db: DbSession,
):
    """Create a new contact.

    Validates email uniqueness per tenant (case-insensitive).
    """
    try:
        contact = await contact_service.create_contact(
            db, user.tenant_id, data, user.id
        )
        await db.commit()
        await db.refresh(contact, ["company"])
        return contact
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.patch("/{contact_id}", response_model=ContactRead)
async def update_contact(
    contact_id: UUID,
    data: ContactUpdate,
    user: CurrentUser,
    db: DbSession,
):
    """Update contact fields.

    All updates are logged in audit trail with user ID and timestamps.
    """
    contact = await contact_service.get_contact(db, contact_id, user.tenant_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    updated = await contact_service.update_contact(db, contact, data, user.id)
    await db.commit()
    await db.refresh(updated, ["company"])
    return updated


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Delete contact.

    Cascades to contact updates and email links automatically.
    """
    contact = await contact_service.get_contact(db, contact_id, user.tenant_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    await contact_service.delete_contact(db, contact)
    await db.commit()


@router.get("/{contact_id}/updates", response_model=list[ContactUpdateRead])
async def get_contact_updates(
    contact_id: UUID,
    user: CurrentUser,
    db: DbSession,
):
    """Get audit trail for contact.

    Returns all updates (manual edits, auto-enrichment, imports) with evidence.
    """
    contact = await contact_service.get_contact(db, contact_id, user.tenant_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    return contact.updates


# ── Import ──────────────────────────────────────────────────────────


@router.post("/import/email", response_model=ContactImportReport)
async def import_contacts_from_email(
    data: ContactImportRequest,
    user: CurrentUser,
    db: DbSession,
):
    """Import contacts from email account.

    Scans emails from the last N days, extracts participants,
    and creates contacts with enrichment from signatures.

    Blacklists no-reply, newsletter, and automated addresses.
    """
    logger.info(
        f"Starting email import for account {data.mail_account_id}, "
        f"tenant {user.tenant_id}, range {data.date_range_days} days"
    )

    report = await contact_import_service.import_from_mail_account(
        db,
        user.tenant_id,
        data.mail_account_id,
        data.date_range_days,
    )
    await db.commit()

    logger.info(
        f"Email import complete: {report.contacts_created} created, "
        f"{report.contacts_skipped} skipped, {len(report.errors)} errors"
    )

    return report


# ── Companies ───────────────────────────────────────────────────────


@router.get("/companies", response_model=list[CompanyRead], deprecated=True)
async def list_companies(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, le=100),
):
    """List companies for tenant.

    Note: This endpoint is deprecated. Companies are managed through contacts.
    """
    stmt = (
        select(Company)
        .where(Company.tenant_id == user.tenant_id)
        .order_by(Company.company_name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/companies", response_model=CompanyRead, status_code=status.HTTP_201_CREATED, deprecated=True)
async def create_company(
    data: CompanyCreate,
    user: CurrentUser,
    db: DbSession,
):
    """Create a company.

    Note: This endpoint is deprecated. Use find_or_create_company in service layer.
    """
    company = await contact_service.find_or_create_company(
        db, user.tenant_id, data.company_name, data.company_domain
    )
    await db.commit()
    return company
