"""Contact agent tools for searching and managing contacts."""

from decimal import Decimal
from uuid import UUID

from app.core.tool_registry import ToolCategory, ToolDefinition, tool_registry
from app.database import async_session_maker
from app.models.contact import Contact, ContactUpdate as ContactUpdateModel
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.contact_service import contact_service


# ── Tool schemas ─────────────────────────────────────────────────────


TOOL_SEARCH_CONTACTS = {
    "type": "function",
    "function": {
        "name": "search_contacts",
        "description": "Search for contacts by name, email, or company. Returns top matching contacts with relevance score.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (name, email, company, etc.)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_GET_CONTACT_BY_EMAIL = {
    "type": "function",
    "function": {
        "name": "get_contact_by_email",
        "description": "Get contact details by email address.",
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Email address",
                },
            },
            "required": ["email"],
        },
    },
}

TOOL_GET_CONTACT = {
    "type": "function",
    "function": {
        "name": "get_contact",
        "description": "Get full contact details by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "Contact UUID",
                },
            },
            "required": ["contact_id"],
        },
    },
}

TOOL_UPSERT_CONTACT = {
    "type": "function",
    "function": {
        "name": "upsert_contact",
        "description": "Create or update a contact. Requires EXEC profile and user confirmation. Use when you have high-confidence contact info from conversation context.",
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Primary email (deduplication key)",
                },
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "phone": {"type": "string"},
                "company_name": {"type": "string"},
                "title": {"type": "string"},
                "contact_type": {
                    "type": "string",
                    "enum": [
                        "client",
                        "prospect",
                        "partenaire",
                        "fournisseur",
                        "candidat",
                        "interne",
                        "autre",
                    ],
                },
                "notes": {"type": "string"},
                "evidence": {
                    "type": "object",
                    "description": "Evidence justifying this update (message context, etc.)",
                },
            },
            "required": ["email"],
        },
    },
}

TOOL_SUGGEST_CONTACT_UPDATE = {
    "type": "function",
    "function": {
        "name": "suggest_contact_update",
        "description": "Suggest a contact creation or update via generative UI block. Safe for all profiles. Use when you detect potential contact info but aren't certain.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update"],
                    "description": "Create new or update existing",
                },
                "contact_id": {
                    "type": "string",
                    "description": "Contact UUID (required for update)",
                },
                "email": {"type": "string"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "phone": {"type": "string"},
                "company_name": {"type": "string"},
                "title": {"type": "string"},
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0.0-1.0",
                },
                "reason": {
                    "type": "string",
                    "description": "Why you're suggesting this (shown to user)",
                },
            },
            "required": ["action", "email", "confidence", "reason"],
        },
    },
}


# ── Tool handlers ────────────────────────────────────────────────────


async def handle_search_contacts(
    *,
    query: str,
    limit: int = 5,
    tenant_id: UUID,
    **kwargs,
) -> str:
    """Handler for search_contacts tool.

    Returns:
        JSON string with search results
    """
    async with async_session_maker() as db:
        results = await contact_service.search_contacts(db, tenant_id, query, limit)

        contacts = [
            {
                "id": str(contact.id),
                "name": f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                or "Unknown",
                "email": contact.primary_email,
                "company": contact.company.company_name if contact.company else None,
                "type": contact.contact_type,
                "relevance": score,
            }
            for contact, score in results
        ]

        return f"Found {len(contacts)} contacts:\n" + "\n".join(
            f"- {c['name']} ({c['email']}) - {c.get('company', 'No company')} - Relevance: {c['relevance']:.2f}"
            for c in contacts
        )


async def handle_get_contact_by_email(
    *,
    email: str,
    tenant_id: UUID,
    **kwargs,
) -> str:
    """Handler for get_contact_by_email tool.

    Returns:
        JSON string with contact details or not found message
    """
    async with async_session_maker() as db:
        contact = await contact_service.get_contact_by_email(db, email, tenant_id)

        if not contact:
            return f"No contact found with email: {email}"

        return _format_contact_details(contact)


async def handle_get_contact(
    *,
    contact_id: str,
    tenant_id: UUID,
    **kwargs,
) -> str:
    """Handler for get_contact tool.

    Returns:
        JSON string with contact details or error
    """
    try:
        contact_uuid = UUID(contact_id)
    except ValueError:
        return f"Invalid contact ID: {contact_id}"

    async with async_session_maker() as db:
        contact = await contact_service.get_contact(db, contact_uuid, tenant_id)

        if not contact:
            return f"Contact not found: {contact_id}"

        return _format_contact_details(contact)


async def handle_upsert_contact(
    *,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
    company_name: str | None = None,
    title: str | None = None,
    contact_type: str | None = None,
    notes: str | None = None,
    evidence: dict | None = None,
    tenant_id: UUID,
    user_id: UUID,
    run_id: UUID,
    **kwargs,
) -> str:
    """Handler for upsert_contact tool (exec profile, gated).

    Returns:
        Success message with action taken
    """
    async with async_session_maker() as db:
        # Check if contact exists
        existing = await contact_service.get_contact_by_email(db, email, tenant_id)

        if existing:
            # Update existing contact
            update_data = ContactUpdate(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                title=title,
                contact_type=contact_type,
                notes=notes,
            )
            contact = await contact_service.update_contact(
                db, existing, update_data, user_id
            )

            # Audit
            db.add(
                ContactUpdateModel(
                    tenant_id=tenant_id,
                    contact_id=contact.id,
                    update_type="agent_update",
                    source="agent_tool",
                    evidence=evidence,
                    user_id=user_id,
                    run_id=run_id,
                )
            )

            action = "updated"
        else:
            # Create new contact
            company_id = None
            if company_name:
                company = await contact_service.find_or_create_company(
                    db, tenant_id, company_name
                )
                company_id = company.id

            create_data = ContactCreate(
                primary_email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                title=title,
                contact_type=contact_type or "autre",
                company_id=company_id,
                notes=notes,
                source="agent",
                confidence_score=Decimal("0.8"),
            )
            contact = await contact_service.create_contact(
                db, tenant_id, create_data, user_id
            )

            # Audit
            db.add(
                ContactUpdateModel(
                    tenant_id=tenant_id,
                    contact_id=contact.id,
                    update_type="agent_create",
                    source="agent_tool",
                    evidence=evidence,
                    user_id=user_id,
                    run_id=run_id,
                )
            )

            action = "created"

        await db.commit()

        return f"Contact {action} successfully: {contact.first_name or ''} {contact.last_name or ''} ({contact.primary_email})"


async def handle_suggest_contact_update(
    *,
    action: str,
    email: str,
    confidence: float,
    reason: str,
    contact_id: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
    company_name: str | None = None,
    title: str | None = None,
    **kwargs,
) -> dict:
    """Handler for suggest_contact_update tool (returns block).

    Returns:
        Block payload for frontend rendering
    """
    # This is a BLOCK tool - returns payload for frontend rendering
    return {
        "block_type": "contact_suggestion",
        "action": action,
        "contact_id": contact_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "company_name": company_name,
        "title": title,
        "confidence": confidence,
        "reason": reason,
    }


def _format_contact_details(contact: Contact) -> str:
    """Format contact for tool response."""
    lines = [
        f"Contact: {contact.first_name or ''} {contact.last_name or ''}".strip()
        or "Unknown",
        f"Email: {contact.primary_email}",
    ]

    if contact.phone:
        lines.append(f"Phone: {contact.phone}")
    if contact.title:
        lines.append(f"Title: {contact.title}")
    if contact.company:
        lines.append(f"Company: {contact.company.company_name}")
    if contact.contact_type:
        lines.append(f"Type: {contact.contact_type}")
    if contact.language:
        lines.append(f"Language: {contact.language}")
    if contact.notes:
        lines.append(f"Notes: {contact.notes[:200]}")

    return "\n".join(lines)


# ── Registration ─────────────────────────────────────────────────────


def register_contact_tools():
    """Register all contact tools."""

    # Search (reactive+, no loop)
    tool_registry.register(
        ToolDefinition(
            name="search_contacts",
            category=ToolCategory.RETRIEVAL,
            description="Search contacts by name/email/company",
            openai_schema=TOOL_SEARCH_CONTACTS,
            continues_loop=False,
            min_profile="reactive",
        ),
        handler=handle_search_contacts,
    )

    # Get by email (reactive+, no loop)
    tool_registry.register(
        ToolDefinition(
            name="get_contact_by_email",
            category=ToolCategory.RETRIEVAL,
            description="Get contact by email",
            openai_schema=TOOL_GET_CONTACT_BY_EMAIL,
            continues_loop=False,
            min_profile="reactive",
        ),
        handler=handle_get_contact_by_email,
    )

    # Get by ID (reactive+, no loop)
    tool_registry.register(
        ToolDefinition(
            name="get_contact",
            category=ToolCategory.RETRIEVAL,
            description="Get contact by ID",
            openai_schema=TOOL_GET_CONTACT,
            continues_loop=False,
            min_profile="reactive",
        ),
        handler=handle_get_contact,
    )

    # Upsert (exec only, gated, continues loop)
    tool_registry.register(
        ToolDefinition(
            name="upsert_contact",
            category=ToolCategory.INTEGRATION,
            description="Create or update contact (exec profile, requires confirmation)",
            openai_schema=TOOL_UPSERT_CONTACT,
            continues_loop=True,
            requires_confirmation=True,
            min_profile="exec",
        ),
        handler=handle_upsert_contact,
    )

    # Suggest (all profiles, safe, block UI)
    tool_registry.register(
        ToolDefinition(
            name="suggest_contact_update",
            category=ToolCategory.BLOCK,
            description="Suggest contact update via UI block",
            openai_schema=TOOL_SUGGEST_CONTACT_UPDATE,
            block_type="contact_suggestion",
            continues_loop=False,
            min_profile="reactive",
        ),
        handler=handle_suggest_contact_update,
    )
