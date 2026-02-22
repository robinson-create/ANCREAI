"""Import contacts from email (Gmail/Outlook via Nango)."""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mail import MailAccount, MailMessage
from app.models.contact import ContactEmailLink
from app.schemas.contact import ContactImportReport
from app.services.contact_enrichment import contact_enrichment_service

logger = logging.getLogger(__name__)


class ContactImportService:
    """Import contacts from synced emails."""

    async def import_from_mail_account(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        mail_account_id: UUID,
        date_range_days: int = 90,
    ) -> ContactImportReport:
        """Import contacts from email account.

        Scans sent/received emails, creates contacts from participants,
        and links them to messages for traceability.

        Args:
            db: Database session
            tenant_id: Tenant ID
            mail_account_id: Mail account to import from
            date_range_days: Number of days back to scan (default 90)

        Returns:
            Import report with stats and errors
        """
        report = ContactImportReport(
            total_emails_scanned=0,
            contacts_created=0,
            contacts_updated=0,
            contacts_skipped=0,
        )

        # Get mail account
        result = await db.execute(
            select(MailAccount).where(
                MailAccount.id == mail_account_id,
                MailAccount.tenant_id == tenant_id,
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            report.errors.append("Mail account not found")
            return report

        # Get messages from last N days
        cutoff = datetime.utcnow() - timedelta(days=date_range_days)

        stmt = (
            select(MailMessage)
            .where(
                MailMessage.mail_account_id == mail_account_id,
                MailMessage.tenant_id == tenant_id,
                MailMessage.date >= cutoff,
                MailMessage.is_draft == False,
            )
            .order_by(MailMessage.date.desc())
            .limit(1000)  # Safety limit
        )

        result = await db.execute(stmt)
        messages = result.scalars().all()

        report.total_emails_scanned = len(messages)
        logger.info(
            f"Importing contacts from {len(messages)} emails for tenant {tenant_id}"
        )

        # Process each message
        for msg in messages:
            try:
                # Process sender (for received emails)
                if not msg.is_sent and msg.sender:
                    sender_email = msg.sender.get("email")
                    sender_name = msg.sender.get("name")

                    if sender_email:
                        contact = await contact_enrichment_service.create_contact_from_email_participant(
                            db, tenant_id, sender_email, sender_name, msg
                        )

                        if contact:
                            # Link to message
                            existing_link = await db.execute(
                                select(ContactEmailLink).where(
                                    ContactEmailLink.contact_id == contact.id,
                                    ContactEmailLink.mail_message_id == msg.id,
                                    ContactEmailLink.link_type == "sender",
                                )
                            )
                            if not existing_link.scalar_one_or_none():
                                db.add(
                                    ContactEmailLink(
                                        tenant_id=tenant_id,
                                        contact_id=contact.id,
                                        mail_message_id=msg.id,
                                        link_type="sender",
                                    )
                                )
                                report.contacts_created += 1
                        else:
                            report.contacts_skipped += 1

                # Process recipients (for sent emails)
                if msg.is_sent and msg.to_recipients:
                    for recipient in msg.to_recipients:
                        recipient_email = recipient.get("email")
                        recipient_name = recipient.get("name")

                        if recipient_email:
                            contact = await contact_enrichment_service.create_contact_from_email_participant(
                                db, tenant_id, recipient_email, recipient_name, msg
                            )

                            if contact:
                                # Link to message
                                existing_link = await db.execute(
                                    select(ContactEmailLink).where(
                                        ContactEmailLink.contact_id == contact.id,
                                        ContactEmailLink.mail_message_id == msg.id,
                                        ContactEmailLink.link_type == "recipient",
                                    )
                                )
                                if not existing_link.scalar_one_or_none():
                                    db.add(
                                        ContactEmailLink(
                                            tenant_id=tenant_id,
                                            contact_id=contact.id,
                                            mail_message_id=msg.id,
                                            link_type="recipient",
                                        )
                                    )
                                    report.contacts_created += 1
                            else:
                                report.contacts_skipped += 1

            except Exception as e:
                logger.error(f"Error processing message {msg.id}: {e}", exc_info=True)
                report.errors.append(f"Message {msg.id}: {str(e)}")
                report.contacts_skipped += 1

        await db.flush()

        logger.info(
            f"Import complete: {report.contacts_created} created, "
            f"{report.contacts_updated} updated, {report.contacts_skipped} skipped"
        )

        return report


# Singleton instance
contact_import_service = ContactImportService()
