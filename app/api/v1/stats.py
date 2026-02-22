"""Stats endpoints — aggregated analytics dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.deps import DbSession, TenantId
from app.schemas.stats import RunStats, StatsOverview
from app.services.stats import stats_service

router = APIRouter()


@router.get("/overview", response_model=StatsOverview)
async def get_stats_overview(
    tenant_id: TenantId,
    db: DbSession,
    days: int = Query(30, ge=1, le=365),
) -> StatsOverview:
    """Dashboard summary: total runs, tokens, latency, tool usage."""
    return await stats_service.get_overview(db, tenant_id, days=days)


@router.get("/runs", response_model=RunStats)
async def get_run_stats(
    tenant_id: TenantId,
    db: DbSession,
    days: int = Query(30, ge=1, le=365),
) -> RunStats:
    """Run statistics by profile and status."""
    return await stats_service.get_run_stats(db, tenant_id, days=days)
