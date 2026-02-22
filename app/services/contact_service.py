"""Contact management service."""

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contact import Contact, Company, ContactUpdate
from app.schemas.contact import ContactCreate, ContactUpdate as ContactUpdateSchema

logger = logging.getLogger(__name__)


class ContactService:
    """CRUD and search operations for contacts."""

    async def list_contacts(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        *,
        search_query: str | None = None,
        contact_type: str | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        """List contacts with filtering and pagination.

        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            search_query: Full-text search query
            contact_type: Filter by contact type
            tags: Filter by tags (JSONB contains)
            source: Filter by source
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of contacts with company loaded
        """
        stmt = (
            select(Contact)
            .where(Contact.tenant_id == tenant_id)
            .options(selectinload(Contact.company))
        )

        # Full-text search
        if search_query:
            stmt = stmt.where(
                Contact.search_vector.op("@@")(
                    func.plainto_tsquery("french", search_query)
                )
            )

        # Filters
        if contact_type:
            stmt = stmt.where(Contact.contact_type == contact_type)

        if tags:
            # JSONB array contains
            stmt = stmt.where(Contact.tags.op("@>")(tags))

        if source:
            stmt = stmt.where(Contact.source == source)

        stmt = (
            stmt.order_by(Contact.updated_at.desc()).limit(limit).offset(offset)
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def search_contacts(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        query: str,
        limit: int = 10,
    ) -> list[tuple[Contact, float]]:
        """Full-text search with relevance ranking.

        Args:
            db: Database session
            tenant_id: Tenant ID
            query: Search query
            limit: Maximum results

        Returns:
            List of (contact, relevance_score) tuples
        """
        rank_expr = func.ts_rank(
            Contact.search_vector, func.plainto_tsquery("french", query)
        ).label("rank")

        stmt = (
            select(Contact, rank_expr)
            .where(
                Contact.tenant_id == tenant_id,
                Contact.search_vector.op("@@")(
                    func.plainto_tsquery("french", query)
                ),
            )
            .options(selectinload(Contact.company))
            .order_by(rank_expr.desc())
            .limit(limit)
        )

        result = await db.execute(stmt)
        rows = result.all()

        return [(row.Contact, float(row.rank)) for row in rows]

    async def get_contact(
        self,
        db: AsyncSession,
        contact_id: UUID,
        tenant_id: UUID,
    ) -> Contact | None:
        """Get contact by ID with tenant isolation.

        Args:
            db: Database session
            contact_id: Contact UUID
            tenant_id: Tenant ID for verification

        Returns:
            Contact or None if not found
        """
        stmt = (
            select(Contact)
            .where(Contact.id == contact_id, Contact.tenant_id == tenant_id)
            .options(
                selectinload(Contact.company), selectinload(Contact.updates)
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_contact_by_email(
        self,
        db: AsyncSession,
        email: str,
        tenant_id: UUID,
    ) -> Contact | None:
        """Get contact by email (case-insensitive).

        Args:
            db: Database session
            email: Email address
            tenant_id: Tenant ID

        Returns:
            Contact or None
        """
        stmt = (
            select(Contact)
            .where(
                Contact.tenant_id == tenant_id,
                func.lower(Contact.primary_email) == email.lower(),
            )
            .options(selectinload(Contact.company))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_contact(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        data: ContactCreate,
        user_id: UUID | None = None,
    ) -> Contact:
        """Create a new contact.

        Args:
            db: Database session
            tenant_id: Tenant ID
            data: Contact creation data
            user_id: User creating the contact (for audit)

        Returns:
            Created contact

        Raises:
            ValueError: If email already exists for tenant
        """
        # Check for existing contact by email
        existing = await self.get_contact_by_email(
            db, data.primary_email, tenant_id
        )
        if existing:
            raise ValueError(
                f"Contact with email {data.primary_email} already exists"
            )

        # Create contact
        contact = Contact(
            tenant_id=tenant_id,
            **data.model_dump(),
        )
        db.add(contact)
        await db.flush()
        await db.refresh(contact)

        # Audit trail
        db.add(
            ContactUpdate(
                tenant_id=tenant_id,
                contact_id=contact.id,
                update_type="manual_create",
                source="user_create",
                user_id=user_id,
            )
        )

        return contact

    async def update_contact(
        self,
        db: AsyncSession,
        contact: Contact,
        data: ContactUpdateSchema,
        user_id: UUID | None = None,
    ) -> Contact:
        """Update contact fields.

        Args:
            db: Database session
            contact: Contact to update
            data: Update data
            user_id: User making the update

        Returns:
            Updated contact
        """
        update_dict = data.model_dump(exclude_unset=True)

        # Track changes for audit
        for field, new_value in update_dict.items():
            old_value = getattr(contact, field, None)
            if old_value != new_value:
                setattr(contact, field, new_value)

                # Log update
                db.add(
                    ContactUpdate(
                        tenant_id=contact.tenant_id,
                        contact_id=contact.id,
                        update_type="manual_edit",
                        source="user_edit",
                        field_name=field,
                        old_value=str(old_value) if old_value else None,
                        new_value=str(new_value) if new_value else None,
                        user_id=user_id,
                    )
                )

        await db.flush()
        await db.refresh(contact)
        return contact

    async def delete_contact(
        self,
        db: AsyncSession,
        contact: Contact,
    ) -> None:
        """Delete a contact (cascades to updates and links).

        Args:
            db: Database session
            contact: Contact to delete
        """
        await db.delete(contact)
        await db.flush()

    async def find_or_create_company(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        company_name: str,
        company_domain: str | None = None,
    ) -> Company:
        """Find or create company by domain (priority) or name.

        Args:
            db: Database session
            tenant_id: Tenant ID
            company_name: Company name
            company_domain: Company domain (optional)

        Returns:
            Existing or newly created company
        """
        # Try by domain first
        if company_domain:
            stmt = select(Company).where(
                Company.tenant_id == tenant_id,
                func.lower(Company.company_domain) == company_domain.lower(),
            )
            result = await db.execute(stmt)
            company = result.scalar_one_or_none()
            if company:
                return company

        # Try by name
        stmt = select(Company).where(
            Company.tenant_id == tenant_id,
            func.lower(Company.company_name) == company_name.lower(),
        )
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            company = Company(
                tenant_id=tenant_id,
                company_name=company_name,
                company_domain=company_domain,
            )
            db.add(company)
            await db.flush()

        return company


# Singleton instance
contact_service = ContactService()
