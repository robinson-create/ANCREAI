"""Stats schemas for analytics endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ToolUsageBreakdown(BaseModel):
    tool_name: str
    call_count: int


class ProfileBreakdown(BaseModel):
    profile: str
    run_count: int
    avg_tokens: float
    avg_tool_rounds: float
    success_rate: float


class StatsOverview(BaseModel):
    """Dashboard summary."""

    total_runs: int
    completed_runs: int
    failed_runs: int
    total_tokens_input: int
    total_tokens_output: int
    avg_latency_ms: float | None = None
    tool_usage: list[ToolUsageBreakdown] = []
    period_start: datetime | None = None
    period_end: datetime | None = None


class RunStats(BaseModel):
    """Run statistics by profile."""

    profiles: list[ProfileBreakdown]
    total_runs: int
    avg_completion_seconds: float | None = None
