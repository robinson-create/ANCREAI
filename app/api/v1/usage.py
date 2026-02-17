"""Usage endpoints."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import DbSession, TenantId
from app.models.usage import Usage
from app.schemas.usage import UsageRead, UsageSummary
from app.services.usage import usage_service

router = APIRouter()


@router.get("", response_model=UsageSummary)
async def get_current_usage(
    tenant_id: TenantId,
    db: DbSession,
) -> dict:
    """Get current period usage summary with limits."""
    try:
        summary = await usage_service.get_usage_summary(db, tenant_id)
        return summary
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/history", response_model=list[UsageRead])
async def get_usage_history(
    tenant_id: TenantId,
    db: DbSession,
    limit: int = 12,
) -> list[Usage]:
    """Get usage history for past periods."""
    result = await db.execute(
        select(Usage)
        .where(Usage.tenant_id == tenant_id)
        .order_by(Usage.period.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{period}", response_model=UsageRead)
async def get_usage_by_period(
    period: date,
    tenant_id: TenantId,
    db: DbSession,
) -> Usage:
    """Get usage for a specific period."""
    result = await db.execute(
        select(Usage)
        .where(Usage.tenant_id == tenant_id)
        .where(Usage.period == period)
    )
    usage = result.scalar_one_or_none()
    
    if not usage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No usage data for period {period}",
        )
    
    return usage
