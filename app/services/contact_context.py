"""Contact context injection for agent conversations."""

import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.services.contact_service import contact_service

logger = logging.getLogger(__name__)


class ContactContextService:
    """Inject contact context into agent system prompt."""

    async def detect_relevant_contacts(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        message: str,
        conversation_context: dict | None = None,
    ) -> list[Contact]:
        """Detect contacts mentioned in message or conversation context.

        Strategies:
        1. Extract email addresses from message
        2. Search for names mentioned in quotes
        3. Check conversation context for contact_id hints

        Args:
            db: Database session
            tenant_id: Tenant ID
            message: User message text
            conversation_context: Optional conversation context dict

        Returns:
            List of relevant contacts (deduplicated)
        """
        contacts = []

        # Strategy 1: Extract emails
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, message)

        for email in emails:
            contact = await contact_service.get_contact_by_email(
                db, email, tenant_id
            )
            if contact:
                contacts.append(contact)
                logger.debug(f"Found contact by email: {email}")

        # Strategy 2: Search for names (in quotes or after common patterns)
        # Pattern 1: Quoted names
        name_pattern = r'"([^"]+)"'
        quoted_names = re.findall(name_pattern, message)
        for name in quoted_names:
            if len(name.split()) >= 2:  # Likely a full name
                results = await contact_service.search_contacts(
                    db, tenant_id, name, limit=1
                )
                if results:
                    contact, score = results[0]
                    if score > 0.3:  # Minimum relevance threshold
                        contacts.append(contact)
                        logger.debug(
                            f"Found contact by quoted name: {name} (score: {score})"
                        )

        # Pattern 2: Common prefixes like "à", "pour", "de", "avec"
        prefix_pattern = r"(?:à|pour|de|avec|chez)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
        prefix_matches = re.findall(prefix_pattern, message)
        for name in prefix_matches:
            results = await contact_service.search_contacts(
                db, tenant_id, name, limit=1
            )
            if results:
                contact, score = results[0]
                if score > 0.3:
                    contacts.append(contact)
                    logger.debug(
                        f"Found contact by prefix pattern: {name} (score: {score})"
                    )

        # Strategy 3: Conversation context (if provided)
        if conversation_context and "contact_id" in conversation_context:
            try:
                contact_id = UUID(conversation_context["contact_id"])
                contact = await contact_service.get_contact(
                    db, contact_id, tenant_id
                )
                if contact:
                    contacts.append(contact)
                    logger.debug(f"Found contact from conversation context: {contact_id}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid contact_id in conversation_context: {e}")

        # Deduplicate by ID
        seen = set()
        unique_contacts = []
        for c in contacts:
            if c.id not in seen:
                seen.add(c.id)
                unique_contacts.append(c)

        logger.info(f"Detected {len(unique_contacts)} relevant contacts")
        return unique_contacts

    def format_contact_context(self, contacts: list[Contact]) -> str:
        """Format contact context for system prompt injection.

        Args:
            contacts: List of relevant contacts

        Returns:
            Formatted context string for system prompt
        """
        if not contacts:
            return ""

        lines = ["\n\nCONTEXTE: Contacts pertinents"]
        lines.append("-" * 60)

        for contact in contacts:
            name = (
                f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                or "Nom inconnu"
            )
            company = contact.company.company_name if contact.company else "N/A"
            contact_type = contact.contact_type
            language = contact.language or "unknown"

            # Tone suggestion based on type
            tone_map = {
                "client": "professionnel et chaleureux",
                "prospect": "engageant et informatif",
                "partenaire": "collaboratif",
                "fournisseur": "courtois et direct",
                "candidat": "accueillant et encourageant",
                "interne": "décontracté et efficace",
                "autre": "neutre",
            }
            tone = tone_map.get(contact_type, "neutre")

            lines.append(f"\n{name} ({contact.primary_email})")
            lines.append(f"  Société: {company}")
            lines.append(f"  Type: {contact_type} → Ton suggéré: {tone}")
            lines.append(f"  Langue: {language}")

            if contact.title:
                lines.append(f"  Fonction: {contact.title}")

            if contact.notes:
                # Truncate notes to first 200 chars
                notes = contact.notes[:200]
                if len(contact.notes) > 200:
                    notes += "..."
                lines.append(f"  Notes: {notes}")

        lines.append("-" * 60)
        return "\n".join(lines)

    async def get_contact_context_for_message(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        message: str,
        conversation_context: dict | None = None,
        max_contacts: int = 5,
    ) -> str:
        """Get formatted contact context for a message.

        Args:
            db: Database session
            tenant_id: Tenant ID
            message: User message
            conversation_context: Optional conversation context
            max_contacts: Maximum contacts to include (default 5)

        Returns:
            Formatted contact context string (empty if no relevant contacts)
        """
        contacts = await self.detect_relevant_contacts(
            db, tenant_id, message, conversation_context
        )

        # Limit to max_contacts to avoid prompt overflow
        if len(contacts) > max_contacts:
            logger.warning(
                f"Limiting contacts from {len(contacts)} to {max_contacts}"
            )
            contacts = contacts[:max_contacts]

        return self.format_contact_context(contacts)


# Singleton instance
contact_context_service = ContactContextService()
