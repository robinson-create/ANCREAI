"""Stratified sampling from conversation/run history for regression detection."""

from __future__ import annotations

import random
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.eval.dataset import EvalDataset, EvalExample
from app.models.agent_run import AgentRun


@dataclass
class SamplingConfig:
    """Configuration for stratified sampling."""

    per_profile: int = 5
    seed: int | None = None


class HistorySampler:
    """Sample from past agent runs for regression eval datasets."""

    async def sample_by_profile(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        config: SamplingConfig | None = None,
    ) -> EvalDataset:
        """Stratified sample: N completed runs per profile."""
        config = config or SamplingConfig()
        if config.seed is not None:
            random.seed(config.seed)

        examples: list[EvalExample] = []

        for profile in ("reactive", "balanced", "pro", "exec"):
            q = await db.execute(
                select(AgentRun)
                .where(AgentRun.tenant_id == tenant_id)
                .where(AgentRun.profile == profile)
                .where(AgentRun.status == "completed")
                .where(AgentRun.input_text.is_not(None))
                .order_by(func.random())
                .limit(config.per_profile)
            )
            for run in q.scalars().all():
                examples.append(EvalExample(
                    query=run.input_text,
                    expected_answer=run.output_text,
                    tags=[f"profile:{profile}"],
                    metadata={"run_id": str(run.id), "profile": profile},
                ))

        return EvalDataset(name=f"sampled_{tenant_id}", examples=examples)
