"""Stats service — aggregated analytics from agent_runs and llm_traces."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.llm_trace import LLMTrace
from app.schemas.stats import (
    ProfileBreakdown,
    RunStats,
    StatsOverview,
    ToolUsageBreakdown,
)


class StatsService:
    """Runs aggregation queries for the stats dashboard."""

    async def get_overview(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        days: int = 30,
    ) -> StatsOverview:
        """Dashboard summary: totals, avg latency, tool usage."""
        since = datetime.now(UTC) - timedelta(days=days)

        # Aggregate from agent_runs
        runs_q = await db.execute(
            select(
                func.count(AgentRun.id).label("total"),
                func.count(case((AgentRun.status == "completed", 1))).label("completed"),
                func.count(case((AgentRun.status == "failed", 1))).label("failed"),
                func.coalesce(func.sum(AgentRun.tokens_input), 0).label("tokens_in"),
                func.coalesce(func.sum(AgentRun.tokens_output), 0).label("tokens_out"),
            )
            .where(AgentRun.tenant_id == tenant_id)
            .where(AgentRun.created_at >= since)
        )
        row = runs_q.one()

        # Avg latency from llm_traces
        latency_q = await db.execute(
            select(func.avg(LLMTrace.latency_ms))
            .where(LLMTrace.tenant_id == tenant_id)
            .where(LLMTrace.created_at >= since)
            .where(LLMTrace.latency_ms.is_not(None))
        )
        avg_latency = latency_q.scalar()

        # Tool usage: count tool_rounds > 0 by profile as a proxy
        # (detailed per-tool tracking would require audit_log instrumentation)
        tool_q = await db.execute(
            select(
                AgentRun.profile,
                func.count(AgentRun.id).label("count"),
            )
            .where(AgentRun.tenant_id == tenant_id)
            .where(AgentRun.created_at >= since)
            .where(AgentRun.tool_rounds > 0)
            .group_by(AgentRun.profile)
        )
        tool_usage = [
            ToolUsageBreakdown(tool_name=f"profile:{r.profile}", call_count=r.count)
            for r in tool_q.all()
        ]

        return StatsOverview(
            total_runs=row.total,
            completed_runs=row.completed,
            failed_runs=row.failed,
            total_tokens_input=row.tokens_in,
            total_tokens_output=row.tokens_out,
            avg_latency_ms=float(avg_latency) if avg_latency else None,
            tool_usage=tool_usage,
            period_start=since,
            period_end=datetime.now(UTC),
        )

    async def get_run_stats(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        days: int = 30,
    ) -> RunStats:
        """Run stats broken down by profile."""
        since = datetime.now(UTC) - timedelta(days=days)

        q = await db.execute(
            select(
                AgentRun.profile,
                func.count(AgentRun.id).label("run_count"),
                func.avg(
                    func.coalesce(AgentRun.tokens_input, 0)
                    + func.coalesce(AgentRun.tokens_output, 0)
                ).label("avg_tokens"),
                func.avg(func.coalesce(AgentRun.tool_rounds, 0)).label("avg_rounds"),
                func.count(case((AgentRun.status == "completed", 1))).label("completed"),
            )
            .where(AgentRun.tenant_id == tenant_id)
            .where(AgentRun.created_at >= since)
            .group_by(AgentRun.profile)
        )

        profiles = []
        total = 0
        for r in q.all():
            rate = (r.completed / r.run_count) if r.run_count else 0.0
            profiles.append(ProfileBreakdown(
                profile=r.profile or "unknown",
                run_count=r.run_count,
                avg_tokens=float(r.avg_tokens or 0),
                avg_tool_rounds=float(r.avg_rounds or 0),
                success_rate=rate,
            ))
            total += r.run_count

        # Avg completion seconds
        avg_q = await db.execute(
            select(
                func.avg(
                    func.extract("epoch", AgentRun.completed_at - AgentRun.started_at)
                )
            )
            .where(AgentRun.tenant_id == tenant_id)
            .where(AgentRun.created_at >= since)
            .where(AgentRun.completed_at.is_not(None))
            .where(AgentRun.started_at.is_not(None))
        )
        avg_seconds = avg_q.scalar()

        return RunStats(
            profiles=profiles,
            total_runs=total,
            avg_completion_seconds=float(avg_seconds) if avg_seconds else None,
        )


stats_service = StatsService()
