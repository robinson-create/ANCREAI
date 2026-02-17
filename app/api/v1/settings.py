"""User/tenant settings endpoints (signature mail, etc.)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models.tenant import Tenant


router = APIRouter()


class TenantSettingsRead(BaseModel):
    """Tenant settings for current user."""

    mail_signature: str = ""


class TenantSettingsUpdate(BaseModel):
    """Update tenant settings."""

    mail_signature: str | None = None


@router.get("", response_model=TenantSettingsRead)
async def get_tenant_settings(user: CurrentUser, db: DbSession) -> TenantSettingsRead:
    """Get current user's tenant settings."""
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return TenantSettingsRead()
    settings = tenant.settings or {}
    return TenantSettingsRead(
        mail_signature=settings.get("mail_signature", "") or "",
    )


@router.patch("", response_model=TenantSettingsRead)
async def update_tenant_settings(
    data: TenantSettingsUpdate,
    user: CurrentUser,
    db: DbSession,
) -> TenantSettingsRead:
    """Update current user's tenant settings."""
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    settings = dict(tenant.settings or {})
    if data.mail_signature is not None:
        settings["mail_signature"] = data.mail_signature

    tenant.settings = settings
    await db.commit()
    await db.refresh(tenant)

    return TenantSettingsRead(
        mail_signature=settings.get("mail_signature", "") or "",
    )
