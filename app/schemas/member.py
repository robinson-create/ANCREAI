"""Member schemas for org member management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MemberInvite(BaseModel):
    """Schema for inviting a new member by email."""

    email: str


class MemberUpdate(BaseModel):
    """Schema for updating a member's role or status."""

    role: str | None = None  # "admin" or "member"
    status: str | None = None  # "active" or "inactive"


class MemberRead(BaseModel):
    """Schema for reading a member with user details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    role: str
    status: str
    invited_by: UUID | None = None
    invited_at: datetime | None = None
    joined_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Flattened user fields (populated via join)
    email: str | None = None
    name: str | None = None


class PermissionMemberRead(BaseModel):
    """Schema for reading a member's permission on an assistant."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID  # permission id
    member_id: UUID
    user_id: UUID
    email: str | None = None
    name: str | None = None
    role: str
    created_at: datetime


class PermissionBulkSet(BaseModel):
    """Schema for replacing all permissions on an assistant."""

    member_ids: list[UUID]


class PermissionAdd(BaseModel):
    """Schema for adding permissions to members."""

    member_ids: list[UUID]
