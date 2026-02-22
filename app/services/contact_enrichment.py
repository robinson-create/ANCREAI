"""Contact enrichment from emails and AI extraction."""

import logging
import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact, ContactUpdate
from app.models.mail import MailMessage
from app.services.contact_service import contact_service

logger = logging.getLogger(__name__)


class ContactEnrichmentService:
    """Parse email signatures and extract contact info."""

    # Blacklist patterns to avoid false positives
    BLACKLIST_PATTERNS = [
        r"no-?reply",
        r"do-?not-?reply",
        r"newsletter",
        r"notification",
        r"automated",
        r"support@",
        r"hello@",
        r"info@",
        r"contact@",
        r"admin@",
        r"postmaster@",
    ]

    def is_blacklisted_email(self, email: str) -> bool:
        """Check if email should be ignored (no-reply, newsletters, etc.).

        Args:
            email: Email address to check

        Returns:
            True if email should be blacklisted
        """
        email_lower = email.lower()
        return any(
            re.search(pattern, email_lower) for pattern in self.BLACKLIST_PATTERNS
        )

    def extract_domain_from_email(self, email: str) -> str | None:
        """Extract company domain from email address.

        Excludes common free email providers (Gmail, Outlook, etc.).

        Args:
            email: Email address

        Returns:
            Domain name or None if free provider
        """
        match = re.match(r"[^@]+@(.+)", email)
        if match:
            domain = match.group(1).lower()
            # Exclude free email providers
            free_providers = [
                "gmail.com",
                "googlemail.com",
                "outlook.com",
                "hotmail.com",
                "live.com",
                "yahoo.com",
                "yahoo.fr",
                "icloud.com",
                "me.com",
                "protonmail.com",
            ]
            if domain not in free_providers:
                return domain
        return None

    def parse_signature(self, body_text: str) -> dict:
        """Parse email signature for contact info.

        Simple heuristic-based extraction. In production, could use NER or LLM.

        Args:
            body_text: Email body text

        Returns:
            Dict with extracted fields and confidence scores
        """
        result = {
            "phone": None,
            "title": None,
            "company_name": None,
            "confidence": {},
        }

        if not body_text:
            return result

        # Phone regex (French format: +33 or 0 followed by 9 digits)
        phone_patterns = [
            r"(\+33|0)[1-9](\s?\d{2}){4}",  # French
            r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}",  # International
        ]

        for pattern in phone_patterns:
            phone_match = re.search(pattern, body_text)
            if phone_match:
                result["phone"] = phone_match.group(0).replace(" ", "")
                result["confidence"]["phone"] = 0.8
                break

        # Title heuristic: line before email in signature
        lines = body_text.split("\n")
        for i, line in enumerate(lines):
            if "@" in line and i > 0:
                prev_line = lines[i - 1].strip()
                if prev_line and len(prev_line) < 100 and not prev_line.startswith(">"):
                    result["title"] = prev_line
                    result["confidence"]["title"] = 0.6
                    break

        return result

    async def enrich_contact_from_email(
        self,
        db: AsyncSession,
        contact: Contact,
        message: MailMessage,
    ) -> bool:
        """Enrich contact from email body/signature.

        Only updates missing fields with good confidence.

        Args:
            db: Database session
            contact: Contact to enrich
            message: Email message to extract from

        Returns:
            True if contact was updated
        """
        if not message.body_text:
            return False

        extracted = self.parse_signature(message.body_text)
        updated = False

        # Update phone if missing and confidence is good
        if extracted["phone"] and not contact.phone:
            confidence = extracted["confidence"].get("phone", 0)
            if confidence > 0.7:
                contact.phone = extracted["phone"]

                db.add(
                    ContactUpdate(
                        tenant_id=contact.tenant_id,
                        contact_id=contact.id,
                        update_type="auto_enrichment",
                        source="email_signature",
                        field_name="phone",
                        new_value=extracted["phone"],
                        confidence=Decimal(str(confidence)),
                        evidence={"mail_message_id": str(message.id)},
                    )
                )
                updated = True

        # Update title if missing
        if extracted["title"] and not contact.title:
            confidence = extracted["confidence"].get("title", 0)
            if confidence > 0.5:
                contact.title = extracted["title"]

                db.add(
                    ContactUpdate(
                        tenant_id=contact.tenant_id,
                        contact_id=contact.id,
                        update_type="auto_enrichment",
                        source="email_signature",
                        field_name="title",
                        new_value=extracted["title"],
                        confidence=Decimal(str(confidence)),
                        evidence={"mail_message_id": str(message.id)},
                    )
                )
                updated = True

        if updated:
            await db.flush()

        return updated

    async def create_contact_from_email_participant(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        email: str,
        name: str | None,
        message: MailMessage,
    ) -> Contact | None:
        """Create contact from email participant if valid.

        Args:
            db: Database session
            tenant_id: Tenant ID
            email: Participant email
            name: Participant name (from display name)
            message: Email message context

        Returns:
            Contact (existing or new) or None if blacklisted
        """
        # Skip blacklisted emails
        if self.is_blacklisted_email(email):
            logger.debug(f"Skipping blacklisted email: {email}")
            return None

        # Check if contact exists
        existing = await contact_service.get_contact_by_email(db, email, tenant_id)
        if existing:
            # Try to enrich
            await self.enrich_contact_from_email(db, existing, message)
            return existing

        # Parse name
        first_name, last_name = None, None
        if name:
            parts = name.strip().split()
            if len(parts) == 1:
                first_name = parts[0]
            elif len(parts) >= 2:
                first_name = parts[0]
                last_name = " ".join(parts[1:])

        # Extract company from domain
        domain = self.extract_domain_from_email(email)
        company_id = None
        if domain:
            company = await contact_service.find_or_create_company(
                db, tenant_id, company_name=domain, company_domain=domain
            )
            company_id = company.id

        # Create contact
        contact = Contact(
            tenant_id=tenant_id,
            first_name=first_name,
            last_name=last_name,
            primary_email=email,
            company_id=company_id,
            source="import_email",
            confidence_score=Decimal("0.6"),  # Medium confidence
            field_confidence={
                "primary_email": 1.0,
                "first_name": 0.6 if first_name else 0.0,
                "last_name": 0.6 if last_name else 0.0,
            },
        )
        db.add(contact)
        await db.flush()

        # Audit
        db.add(
            ContactUpdate(
                tenant_id=tenant_id,
                contact_id=contact.id,
                update_type="auto_enrichment",
                source="import_email",
                evidence={"mail_message_id": str(message.id)},
            )
        )

        # Try signature enrichment
        await self.enrich_contact_from_email(db, contact, message)

        return contact


# Singleton instance
contact_enrichment_service = ContactEnrichmentService()
