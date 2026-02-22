#!/usr/bin/env python
"""Test email RAG indexing manually."""

import asyncio

from sqlalchemy import select

from app.database import async_session_maker
from app.models.mail import MailAccount, MailMessage
from app.services.mail.indexer import (
    get_or_create_email_collection,
    index_unindexed_emails,
)


async def test_indexing():
    async with async_session_maker() as db:
        # Get account
        result = await db.execute(
            select(MailAccount).where(MailAccount.status == "connected").limit(1)
        )
        account = result.scalar_one_or_none()

        if not account:
            print("❌ No connected account")
            return

        # Check for unindexed emails
        result = await db.execute(
            select(MailMessage).where(
                MailMessage.mail_account_id == account.id,
                MailMessage.is_indexed == False,
                MailMessage.is_draft == False,
            )
        )
        unindexed = list(result.scalars().all())
        print(f"Found {len(unindexed)} unindexed email(s)")

        if not unindexed:
            print("✓ All emails already indexed")
            return

        # Index them
        print("\n🔄 Indexing emails into RAG...")
        collection_id = await get_or_create_email_collection(db, account.tenant_id)
        print(f"✓ Email collection: {collection_id}")

        chunks_count = await index_unindexed_emails(
            db, account.id, account.tenant_id, collection_id
        )
        await db.commit()

        print(f"✓ Indexed {chunks_count} chunks")

        # Verify
        result = await db.execute(
            select(MailMessage).where(
                MailMessage.mail_account_id == account.id, MailMessage.is_indexed == True
            )
        )
        indexed = list(result.scalars().all())
        print(f"\n✅ Total indexed emails: {len(indexed)}")

        # Show chunk details
        from sqlalchemy import text

        result = await db.execute(
            text(
                """
            SELECT COUNT(*) as count, source_type
            FROM chunks
            WHERE tenant_id = :tenant_id
            GROUP BY source_type
        """
            ),
            {"tenant_id": str(account.tenant_id)},
        )
        print("\nChunks by source type:")
        for row in result.fetchall():
            print(f"  {row.source_type or 'document'}: {row.count}")


if __name__ == "__main__":
    asyncio.run(test_indexing())
