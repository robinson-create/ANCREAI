"""Run service — lifecycle management for agent runs + observability writes."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.audit_log import AuditLog
from app.models.llm_trace import LLMTrace


class RunService:
    """Manages agent run lifecycle, audit logging, and LLM trace recording."""

    # ── Agent Run CRUD ───────────────────────────────────────────

    async def create_run(
        self,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        assistant_id: UUID,
        conversation_id: UUID,
        input_text: str,
        profile: str = "reactive",
        budget_tokens: int | None = None,
        metadata_: dict | None = None,
    ) -> AgentRun:
        run = AgentRun(
            tenant_id=tenant_id,
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            input_text=input_text,
            profile=profile,
            status=AgentRunStatus.PENDING.value,
            budget_tokens=budget_tokens,
            budget_tokens_remaining=budget_tokens,
            metadata_=metadata_,
        )
        db.add(run)
        await db.flush()
        return run

    async def get_run(
        self,
        db: AsyncSession,
        run_id: UUID,
        tenant_id: UUID | None = None,
    ) -> AgentRun | None:
        stmt = select(AgentRun).where(AgentRun.id == run_id)
        if tenant_id is not None:
            stmt = stmt.where(AgentRun.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def start_run(self, db: AsyncSession, run_id: UUID) -> None:
        """Transition run to RUNNING."""
        await db.execute(
            update(AgentRun)
            .where(AgentRun.id == run_id)
            .values(
                status=AgentRunStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
        )

    async def complete_run(
        self,
        db: AsyncSession,
        run_id: UUID,
        *,
        output_text: str | None = None,
        tokens_input: int | None = None,
        tokens_output: int | None = None,
        tool_rounds: int | None = None,
        budget_tokens_remaining: int | None = None,
    ) -> None:
        """Transition run to COMPLETED."""
        values: dict = {
            "status": AgentRunStatus.COMPLETED.value,
            "completed_at": datetime.now(UTC),
        }
        if output_text is not None:
            values["output_text"] = output_text
        if tokens_input is not None:
            values["tokens_input"] = tokens_input
        if tokens_output is not None:
            values["tokens_output"] = tokens_output
        if tool_rounds is not None:
            values["tool_rounds"] = tool_rounds
        if budget_tokens_remaining is not None:
            values["budget_tokens_remaining"] = budget_tokens_remaining

        await db.execute(
            update(AgentRun).where(AgentRun.id == run_id).values(**values)
        )

    async def fail_run(
        self,
        db: AsyncSession,
        run_id: UUID,
        *,
        error_code: str,
        error_message: str | None = None,
        status: str = AgentRunStatus.FAILED.value,
    ) -> None:
        """Transition run to FAILED/ABORTED/TIMEOUT."""
        await db.execute(
            update(AgentRun)
            .where(AgentRun.id == run_id)
            .values(
                status=status,
                error_code=error_code,
                error_message=error_message,
                completed_at=datetime.now(UTC),
            )
        )

    async def list_runs(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        *,
        conversation_id: UUID | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(AgentRun.tenant_id == tenant_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        if conversation_id is not None:
            stmt = stmt.where(AgentRun.conversation_id == conversation_id)
        if status is not None:
            stmt = stmt.where(AgentRun.status == status)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def find_stuck_runs(
        self,
        db: AsyncSession,
        running_since_before: datetime,
    ) -> list[AgentRun]:
        """Find runs stuck in RUNNING state past the deadline (for watchdog)."""
        result = await db.execute(
            select(AgentRun)
            .where(AgentRun.status == AgentRunStatus.RUNNING.value)
            .where(AgentRun.started_at < running_since_before)
        )
        return list(result.scalars().all())

    # ── Audit Log ────────────────────────────────────────────────

    async def log_audit(
        self,
        db: AsyncSession,
        *,
        action: str,
        tenant_id: UUID | None = None,
        run_id: UUID | None = None,
        user_id: UUID | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        detail: dict | None = None,
        level: str = "info",
        message: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
            level=level,
            message=message,
        )
        db.add(entry)
        await db.flush()
        return entry

    # ── LLM Trace ────────────────────────────────────────────────

    async def record_llm_trace(
        self,
        db: AsyncSession,
        *,
        model: str,
        provider: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: int | None = None,
        tenant_id: UUID | None = None,
        run_id: UUID | None = None,
        status: str = "success",
        error_message: str | None = None,
        request_metadata: dict | None = None,
    ) -> LLMTrace:
        trace = LLMTrace(
            tenant_id=tenant_id,
            run_id=run_id,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
            request_metadata=request_metadata,
        )
        db.add(trace)
        await db.flush()
        return trace


# Singleton
run_service = RunService()
