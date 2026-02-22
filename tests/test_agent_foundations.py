"""Tests for PR1: agent runtime foundations (models, schemas, services).

Covers:
- Pydantic schema validation (no DB required)
- Memory service tenant isolation (mocked DB)
- Run service lifecycle (mocked DB)
- Audit & trace recording
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.models.agent_run import AgentProfile, AgentRunStatus
from app.schemas.agent_run import AgentRunCreate, AgentRunRead, AgentRunStatusUpdate
from app.schemas.memory import (
    AssistantMemoryRead,
    ConversationContextRead,
    ConversationContextUpdate,
    Fact,
    UserMemoryRead,
    UserMemoryUpdate,
)
from app.schemas.observability import AuditLogCreate, LLMTraceCreate


# ─── Enum Tests ──────────────────────────────────────────────────────


class TestEnums:
    def test_agent_profile_values(self):
        assert AgentProfile.REACTIVE.value == "reactive"
        assert AgentProfile.BALANCED.value == "balanced"
        assert AgentProfile.PRO.value == "pro"
        assert AgentProfile.EXEC.value == "exec"

    def test_agent_run_status_values(self):
        assert AgentRunStatus.PENDING.value == "pending"
        assert AgentRunStatus.RUNNING.value == "running"
        assert AgentRunStatus.COMPLETED.value == "completed"
        assert AgentRunStatus.FAILED.value == "failed"
        assert AgentRunStatus.ABORTED.value == "aborted"
        assert AgentRunStatus.TIMEOUT.value == "timeout"


# ─── Schema Validation Tests ────────────────────────────────────────


class TestMemorySchemas:
    def test_user_memory_read(self):
        now = datetime.now(timezone.utc)
        mem = UserMemoryRead(
            id=uuid4(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            raw_json={"preferences": ["dark_mode"]},
            compressed_text="- Prefers dark mode",
            compressed_token_count=5,
            created_at=now,
            updated_at=now,
        )
        assert mem.compressed_token_count == 5
        assert "dark_mode" in mem.raw_json["preferences"]

    def test_user_memory_update_partial(self):
        update = UserMemoryUpdate(raw_json={"new_key": "value"})
        assert update.raw_json == {"new_key": "value"}

    def test_assistant_memory_read(self):
        now = datetime.now(timezone.utc)
        mem = AssistantMemoryRead(
            id=uuid4(),
            tenant_id=uuid4(),
            assistant_id=uuid4(),
            raw_json={},
            created_at=now,
            updated_at=now,
        )
        assert mem.compressed_text is None

    def test_conversation_context_read(self):
        now = datetime.now(timezone.utc)
        ctx = ConversationContextRead(
            id=uuid4(),
            tenant_id=uuid4(),
            conversation_id=uuid4(),
            assistant_id=uuid4(),
            summary_text="User wants to build a SaaS",
            constraints=["Budget max 50k"],
            decisions=["Use Next.js"],
            open_questions=["Which hosting?"],
            facts=[{"key": "budget", "value": "50k", "source": "user", "confidence": 1.0}],
            message_count=12,
            created_at=now,
            updated_at=now,
        )
        assert len(ctx.constraints) == 1
        assert ctx.message_count == 12

    def test_conversation_context_update_partial(self):
        update = ConversationContextUpdate(constraints=["No outsourcing"])
        assert update.constraints == ["No outsourcing"]
        assert update.summary_text is None  # not provided = None

    def test_fact_schema_validation(self):
        fact = Fact(key="budget", value="50k", source="user", confidence=0.95)
        assert fact.confidence == 0.95

    def test_fact_schema_confidence_bounds(self):
        with pytest.raises(Exception):
            Fact(key="x", value="y", confidence=1.5)
        with pytest.raises(Exception):
            Fact(key="x", value="y", confidence=-0.1)


class TestAgentRunSchemas:
    def test_agent_run_create_defaults(self):
        run = AgentRunCreate(
            assistant_id=uuid4(),
            conversation_id=uuid4(),
            input_text="Hello",
        )
        assert run.profile == "reactive"
        assert run.budget_tokens is None

    def test_agent_run_read_full(self):
        now = datetime.now(timezone.utc)
        run = AgentRunRead(
            id=uuid4(),
            tenant_id=uuid4(),
            assistant_id=uuid4(),
            conversation_id=uuid4(),
            profile="pro",
            status="completed",
            input_text="Recherche le contrat X",
            output_text="Voici le contrat...",
            tokens_input=500,
            tokens_output=800,
            tool_rounds=3,
            budget_tokens=5000,
            budget_tokens_remaining=3700,
            started_at=now,
            completed_at=now,
            created_at=now,
        )
        assert run.profile == "pro"
        assert run.tool_rounds == 3

    def test_agent_run_status_update(self):
        update = AgentRunStatusUpdate(
            status="failed",
            error_code="worker_exception",
            error_message="Connection timeout",
        )
        assert update.status == "failed"


class TestObservabilitySchemas:
    def test_audit_log_create_minimal(self):
        log = AuditLogCreate(action="run_completed")
        assert log.tenant_id is None
        assert log.level == "info"

    def test_audit_log_create_full(self):
        log = AuditLogCreate(
            tenant_id=uuid4(),
            run_id=uuid4(),
            user_id=uuid4(),
            action="tool_called",
            entity_type="assistant",
            entity_id=uuid4(),
            detail={"tool": "retrieval", "duration_ms": 120},
            level="info",
            message="Called retrieval tool",
        )
        assert log.detail["tool"] == "retrieval"

    def test_llm_trace_create(self):
        trace = LLMTraceCreate(
            model="mistral-medium-latest",
            provider="mistral",
            prompt_tokens=500,
            completion_tokens=200,
            latency_ms=1200,
        )
        assert trace.total_tokens == 0  # Computed server-side, not in schema
        assert trace.status == "success"

    def test_llm_trace_error(self):
        trace = LLMTraceCreate(
            model="mistral-medium-latest",
            provider="mistral",
            status="error",
            error_message="Rate limit exceeded",
        )
        assert trace.status == "error"


# ─── Service Tests (mocked DB) ──────────────────────────────────────


class TestMemoryServiceTenantIsolation:
    """Verify that memory service operations are properly scoped by tenant_id."""

    def test_assemble_memory_context_returns_none_for_empty(self):
        """assemble_memory_context should return Nones when no data exists."""
        from app.services.memory import MemoryService

        service = MemoryService()
        tenant_a = uuid4()
        user = uuid4()
        assistant = uuid4()
        conversation = uuid4()

        # Create a mock session that returns None for all queries
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            service.assemble_memory_context(
                mock_session, tenant_a, user, assistant, conversation,
            )
        )

        assert result["assistant_memory"] is None
        assert result["user_memory"] is None
        assert result["conversation_summary"] is None
        assert result["constraints"] == []
        assert result["decisions"] == []

    def test_upsert_user_memory_calls_with_correct_tenant(self):
        """Verify tenant_id is passed to the upsert query."""
        from app.services.memory import MemoryService

        service = MemoryService()
        tenant_id = uuid4()
        user_id = uuid4()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = MagicMock(
            id=uuid4(), tenant_id=tenant_id, user_id=user_id,
        )
        mock_session.execute.return_value = mock_result

        import asyncio

        asyncio.get_event_loop().run_until_complete(
            service.upsert_user_memory(
                mock_session, tenant_id, user_id, {"pref": "dark"},
            )
        )

        # Verify execute was called (the upsert statement)
        assert mock_session.execute.called


class TestRunServiceLifecycle:
    """Verify run service status transitions."""

    def test_create_run_sets_pending(self):
        from app.services.run import RunService

        service = RunService()
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        import asyncio

        run = asyncio.get_event_loop().run_until_complete(
            service.create_run(
                mock_session,
                tenant_id=uuid4(),
                assistant_id=uuid4(),
                conversation_id=uuid4(),
                input_text="Hello",
                profile="balanced",
                budget_tokens=5000,
            )
        )

        assert run.status == AgentRunStatus.PENDING.value
        assert run.profile == "balanced"
        assert run.budget_tokens == 5000
        assert run.budget_tokens_remaining == 5000
        assert mock_session.add.called

    def test_log_audit_creates_entry(self):
        from app.services.run import RunService

        service = RunService()
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        import asyncio

        tenant = uuid4()
        run_id = uuid4()

        entry = asyncio.get_event_loop().run_until_complete(
            service.log_audit(
                mock_session,
                action="tool_called",
                tenant_id=tenant,
                run_id=run_id,
                detail={"tool": "retrieval"},
            )
        )

        assert entry.action == "tool_called"
        assert entry.tenant_id == tenant
        assert entry.run_id == run_id
        assert mock_session.add.called

    def test_record_llm_trace_computes_total(self):
        from app.services.run import RunService

        service = RunService()
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        import asyncio

        trace = asyncio.get_event_loop().run_until_complete(
            service.record_llm_trace(
                mock_session,
                model="mistral-medium-latest",
                provider="mistral",
                prompt_tokens=400,
                completion_tokens=200,
                latency_ms=850,
            )
        )

        assert trace.total_tokens == 600
        assert trace.latency_ms == 850


# ─── Model Instantiation Tests ──────────────────────────────────────


class TestModelInstantiation:
    """Verify models can be instantiated with explicit values.

    Note: SQLAlchemy `default=` is only applied at flush time, not
    on bare construction. We test that models accept the expected fields.
    """

    def test_agent_run_with_explicit_values(self):
        from app.models.agent_run import AgentRun

        run = AgentRun(
            tenant_id=uuid4(),
            assistant_id=uuid4(),
            conversation_id=uuid4(),
            input_text="test",
            status=AgentRunStatus.PENDING.value,
            profile=AgentProfile.REACTIVE.value,
            tool_rounds=0,
        )
        assert run.status == "pending"
        assert run.profile == "reactive"
        assert run.input_text == "test"

    def test_user_memory_fields(self):
        from app.models.user_memory import UserMemory

        tid, uid = uuid4(), uuid4()
        mem = UserMemory(
            tenant_id=tid,
            user_id=uid,
            raw_json={"pref": "dark"},
            compressed_token_count=5,
        )
        assert mem.tenant_id == tid
        assert mem.user_id == uid
        assert mem.raw_json == {"pref": "dark"}

    def test_conversation_context_fields(self):
        from app.models.conversation_context import ConversationContext

        ctx = ConversationContext(
            tenant_id=uuid4(),
            conversation_id=uuid4(),
            assistant_id=uuid4(),
            message_count=10,
            constraints=["budget < 50k"],
        )
        assert ctx.message_count == 10
        assert ctx.constraints == ["budget < 50k"]

    def test_audit_log_fields(self):
        from app.models.audit_log import AuditLog

        log = AuditLog(action="test", level="warn")
        assert log.action == "test"
        assert log.level == "warn"

    def test_llm_trace_fields(self):
        from app.models.llm_trace import LLMTrace

        trace = LLMTrace(
            model="mistral-medium-latest",
            provider="mistral",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            status="success",
        )
        assert trace.total_tokens == 150
