#!/usr/bin/env python3
"""Test script for Contacts feature."""

import asyncio
from uuid import uuid4
from decimal import Decimal

from app.database import async_session_maker
from app.services.contact_service import contact_service
from app.schemas.contact import ContactCreate


async def test_contacts():
    """Test contact CRUD operations."""

    tenant_id = uuid4()  # Mock tenant for testing
    user_id = uuid4()  # Mock user for testing

    async with async_session_maker() as db:
        print("=" * 60)
        print("TEST CONTACTS FEATURE")
        print("=" * 60)

        # 1. Create contact
        print("\n1. Creating contact...")
        contact_data = ContactCreate(
            primary_email="test@example.com",
            first_name="Test",
            last_name="User",
            phone="+33612345678",
            contact_type="client",
            source="manual",
            confidence_score=Decimal("1.0"),
        )

        contact = await contact_service.create_contact(db, tenant_id, contact_data, user_id)
        await db.commit()
        print(f"✓ Contact created: {contact.id}")
        print(f"  Name: {contact.first_name} {contact.last_name}")
        print(f"  Email: {contact.primary_email}")
        print(f"  Type: {contact.contact_type}")

        # 2. Get contact by ID
        print("\n2. Getting contact by ID...")
        fetched = await contact_service.get_contact(db, contact.id, tenant_id)
        assert fetched is not None
        print(f"✓ Contact fetched: {fetched.primary_email}")

        # 3. Get contact by email
        print("\n3. Getting contact by email...")
        by_email = await contact_service.get_contact_by_email(
            db, "test@example.com", tenant_id
        )
        assert by_email is not None
        print(f"✓ Contact found by email: {by_email.id}")

        # 4. Search contacts (FTS)
        print("\n4. Testing FTS search...")
        results = await contact_service.search_contacts(db, tenant_id, "Test User", limit=10)
        print(f"✓ Search found {len(results)} results")
        if results:
            contact, score = results[0]
            print(f"  Top result: {contact.first_name} {contact.last_name} (score: {score:.4f})")

        # 5. List contacts
        print("\n5. Listing all contacts...")
        contacts = await contact_service.list_contacts(db, tenant_id, limit=10)
        print(f"✓ Listed {len(contacts)} contacts")

        # 6. Update contact
        print("\n6. Updating contact...")
        from app.schemas.contact import ContactUpdate
        update_data = ContactUpdate(title="CEO", notes="Test contact")
        updated = await contact_service.update_contact(db, contact, update_data, user_id)
        await db.commit()
        print(f"✓ Contact updated: title={updated.title}, notes={updated.notes}")

        # 7. Create company
        print("\n7. Creating company...")
        company = await contact_service.find_or_create_company(
            db, tenant_id, "Test Corp", "test-corp.com"
        )
        await db.commit()
        print(f"✓ Company created: {company.company_name}")

        # 8. Delete contact
        print("\n8. Deleting contact...")
        await contact_service.delete_contact(db, contact)
        await db.commit()
        print(f"✓ Contact deleted")

        # Verify deletion
        deleted = await contact_service.get_contact(db, contact.id, tenant_id)
        assert deleted is None
        print(f"✓ Deletion verified")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_contacts())
