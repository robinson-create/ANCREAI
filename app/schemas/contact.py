"""Pydantic schemas for contacts."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Company ──────────────────────────────────────────────────────────


class CompanyBase(BaseModel):
    """Base company schema."""

    company_name: str
    company_domain: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    notes: str | None = None


class CompanyCreate(CompanyBase):
    """Schema for creating a company."""

    pass


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""

    company_name: str | None = None
    company_domain: str | None = None
    company_industry: str | None = None
    company_size: str | None = None
    notes: str | None = None


class CompanyRead(CompanyBase):
    """Schema for reading a company."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


# ── Contact ──────────────────────────────────────────────────────────


class ContactBase(BaseModel):
    """Base contact schema with shared fields."""

    first_name: str | None = None
    last_name: str | None = None
    primary_email: str
    phone: str | None = None
    title: str | None = None
    contact_type: str = "autre"
    language: str | None = None
    timezone: str | None = None

    company_id: UUID | None = None

    country: str | None = None
    city: str | None = None
    address: str | None = None

    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    source: str = "manual"


class ContactCreate(ContactBase):
    """Schema for creating a contact."""

    pass


class ContactUpdate(BaseModel):
    """Schema for updating a contact (all fields optional)."""

    first_name: str | None = None
    last_name: str | None = None
    primary_email: str | None = None
    phone: str | None = None
    title: str | None = None
    contact_type: str | None = None
    language: str | None = None
    timezone: str | None = None

    company_id: UUID | None = None

    country: str | None = None
    city: str | None = None
    address: str | None = None

    notes: str | None = None
    tags: list[str] | None = None


class ContactRead(ContactBase):
    """Schema for reading a contact."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    confidence_score: Decimal
    field_confidence: dict | None = None
    created_at: datetime
    updated_at: datetime

    company: CompanyRead | None = None


class ContactBrief(BaseModel):
    """Lightweight contact summary for lists."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str | None
    last_name: str | None
    primary_email: str
    contact_type: str
    company_name: str | None = None


class ContactSearchResult(ContactRead):
    """Contact search result with relevance score."""

    relevance_score: float | None = None


# ── Contact Update (audit) ───────────────────────────────────────────


class ContactUpdateRead(BaseModel):
    """Schema for reading a contact update (audit trail)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    update_type: str
    source: str | None
    field_name: str | None
    old_value: str | None
    new_value: str | None
    confidence: Decimal | None
    evidence: dict | None
    created_at: datetime


# ── Import ───────────────────────────────────────────────────────────


class ContactImportRequest(BaseModel):
    """Request to import contacts from email."""

    source: str  # 'gmail' | 'microsoft'
    mail_account_id: UUID
    date_range_days: int = 90


class ContactImportReport(BaseModel):
    """Result of email import operation."""

    total_emails_scanned: int
    contacts_created: int
    contacts_updated: int
    contacts_skipped: int
    errors: list[str] = Field(default_factory=list)


# ── Suggestion (from agent) ──────────────────────────────────────────


class ContactSuggestion(BaseModel):
    """AI-suggested contact creation/update."""

    action: str  # 'create' | 'update' | 'ignore'
    contact_id: UUID | None = None  # If update

    # Extracted fields
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company_name: str | None = None
    title: str | None = None

    # Evidence
    confidence: Decimal
    evidence: dict  # {"source": "email_signature", "message_id": "..."}
    reason: str  # Human-readable explanation


class ContactUpsertRequest(BaseModel):
    """Agent tool request to create or update contact."""

    email: str  # Deduplication key
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    company_name: str | None = None
    title: str | None = None
    contact_type: str | None = None
    notes: str | None = None

    evidence: dict | None = None
    confidence: Decimal = Decimal("0.6")
