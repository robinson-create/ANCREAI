"""Tests for PR5: Planner, agent loop, and source coverage."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.planner import (
    AgentPlan,
    PlanStep,
    PlanStepStatus,
    _default_plan,
    max_tool_rounds,
    needs_planning,
)
from app.core.source_coverage import (
    SourceCoverageResult,
    analyze_source_coverage,
    check_source_coverage_heuristic,
)

# ── PlanStep model ────────────────────────────────────────────────


class TestPlanStep:
    def test_defaults(self):
        step = PlanStep(action="search_documents", description="Search docs")
        assert step.status == PlanStepStatus.PENDING
        assert step.tool is None
        assert step.result_summary is None
        assert len(step.id) == 8

    def test_with_tool(self):
        step = PlanStep(
            action="search_documents",
            description="Search docs",
            tool="search_documents",
        )
        assert step.tool == "search_documents"


# ── AgentPlan model ───────────────────────────────────────────────


class TestAgentPlan:
    def _make_plan(self) -> AgentPlan:
        return AgentPlan(
            steps=[
                PlanStep(id="s1", action="search_documents", description="Search"),
                PlanStep(id="s2", action="synthesize", description="Synthesize"),
                PlanStep(id="s3", action="ensure_source_coverage", description="Check"),
            ],
            reasoning="Test plan",
            profile="balanced",
        )

    def test_pending_steps_all_pending(self):
        plan = self._make_plan()
        assert len(plan.pending_steps()) == 3

    def test_current_step_returns_first_pending(self):
        plan = self._make_plan()
        assert plan.current_step().id == "s1"

    def test_mark_step_completed(self):
        plan = self._make_plan()
        plan.mark_step("s1", PlanStepStatus.COMPLETED, "Found 5 chunks")
        assert plan.steps[0].status == PlanStepStatus.COMPLETED
        assert plan.steps[0].result_summary == "Found 5 chunks"
        assert plan.current_step().id == "s2"

    def test_mark_step_skipped(self):
        plan = self._make_plan()
        plan.mark_step("s2", PlanStepStatus.SKIPPED)
        assert plan.steps[1].status == PlanStepStatus.SKIPPED

    def test_is_complete_false_initially(self):
        plan = self._make_plan()
        assert plan.is_complete() is False

    def test_is_complete_true_when_all_done(self):
        plan = self._make_plan()
        for step in plan.steps:
            plan.mark_step(step.id, PlanStepStatus.COMPLETED)
        assert plan.is_complete() is True

    def test_is_complete_with_mix_of_completed_and_skipped(self):
        plan = self._make_plan()
        plan.mark_step("s1", PlanStepStatus.COMPLETED)
        plan.mark_step("s2", PlanStepStatus.SKIPPED)
        plan.mark_step("s3", PlanStepStatus.COMPLETED)
        assert plan.is_complete() is True

    def test_is_complete_false_with_failed(self):
        plan = self._make_plan()
        plan.mark_step("s1", PlanStepStatus.COMPLETED)
        plan.mark_step("s2", PlanStepStatus.FAILED)
        plan.mark_step("s3", PlanStepStatus.COMPLETED)
        assert plan.is_complete() is False

    def test_current_step_none_when_all_done(self):
        plan = self._make_plan()
        for step in plan.steps:
            plan.mark_step(step.id, PlanStepStatus.COMPLETED)
        assert plan.current_step() is None

    def test_to_prompt_summary(self):
        plan = self._make_plan()
        plan.mark_step("s1", PlanStepStatus.COMPLETED, "5 chunks found")
        summary = plan.to_prompt_summary()
        assert "PLAN:" in summary
        assert "✓ search_documents: Search" in summary
        assert "→ 5 chunks found" in summary
        assert "○ synthesize: Synthesize" in summary
        assert "○ ensure_source_coverage: Check" in summary

    def test_empty_plan(self):
        plan = AgentPlan(steps=[], reasoning="Empty", profile="balanced")
        assert plan.is_complete() is True
        assert plan.current_step() is None
        assert plan.pending_steps() == []

    def test_model_dump_json(self):
        plan = self._make_plan()
        data = plan.model_dump(mode="json")
        assert len(data["steps"]) == 3
        assert data["profile"] == "balanced"
        assert data["reasoning"] == "Test plan"


# ── Profile helpers ───────────────────────────────────────────────


class TestProfileHelpers:
    @pytest.mark.parametrize(
        "profile,expected",
        [
            ("reactive", False),
            ("balanced", True),
            ("pro", True),
            ("exec", True),
            ("unknown", False),
        ],
    )
    def test_needs_planning(self, profile, expected):
        assert needs_planning(profile) is expected

    @pytest.mark.parametrize(
        "profile,expected",
        [
            ("reactive", 1),
            ("balanced", 3),
            ("pro", 5),
            ("exec", 5),
            ("unknown", 1),
        ],
    )
    def test_max_tool_rounds(self, profile, expected):
        assert max_tool_rounds(profile) == expected


# ── Default plan ──────────────────────────────────────────────────


class TestDefaultPlan:
    def test_has_three_steps(self):
        plan = _default_plan("balanced")
        assert len(plan.steps) == 3

    def test_steps_order(self):
        plan = _default_plan("pro")
        actions = [s.action for s in plan.steps]
        assert actions == ["search_documents", "synthesize", "ensure_source_coverage"]

    def test_first_step_has_tool(self):
        plan = _default_plan("balanced")
        assert plan.steps[0].tool == "search_documents"

    def test_profile_propagated(self):
        plan = _default_plan("exec")
        assert plan.profile == "exec"


# ── generate_plan (mocked LLM) ───────────────────────────────────


class TestGeneratePlan:
    @pytest.mark.asyncio
    async def test_successful_plan_generation(self):
        from app.core.planner import generate_plan

        llm_response = {
            "reasoning": "Question documentaire",
            "steps": [
                {"action": "search_documents", "description": "Chercher", "tool": "search_documents"},
                {"action": "synthesize", "description": "Répondre", "tool": None},
                {"action": "ensure_source_coverage", "description": "Vérifier", "tool": None},
            ],
        }

        mock_message = MagicMock()
        mock_message.content = json.dumps(llm_response)
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            plan = await generate_plan(message="Quels sont les KPIs ?", profile="balanced")

        assert len(plan.steps) == 3
        assert plan.reasoning == "Question documentaire"
        assert plan.profile == "balanced"
        assert plan.steps[0].action == "search_documents"

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        from app.core.planner import generate_plan

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API down"))

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            plan = await generate_plan(message="Test", profile="pro")

        # Should fall back to default plan
        assert len(plan.steps) == 3
        assert plan.profile == "pro"
        assert plan.steps[0].action == "search_documents"

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_json(self):
        from app.core.planner import generate_plan

        mock_message = MagicMock()
        mock_message.content = "not json at all"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            plan = await generate_plan(message="Test", profile="balanced")

        assert len(plan.steps) == 3  # fallback plan


# ── Source coverage heuristic ─────────────────────────────────────


class TestSourceCoverageHeuristic:
    def test_no_claims_is_adequate(self):
        result = check_source_coverage_heuristic("Bonjour, comment ça va ?", 0)
        assert result.coverage_adequate is True
        assert result.claims_count == 0

    def test_claims_with_citations_is_adequate(self):
        result = check_source_coverage_heuristic(
            "Le chiffre d'affaires est de 100M€ [Source: rapport]",
            citations_count=1,
        )
        assert result.coverage_adequate is True

    def test_claims_without_citations_inadequate(self):
        result = check_source_coverage_heuristic(
            "Le budget est de 500M€ et la date limite est le 15/03/2025.",
            citations_count=0,
        )
        assert result.coverage_adequate is False
        assert result.claims_count > 0
        assert result.disclaimer is not None

    def test_claims_with_existing_disclaimer_is_adequate(self):
        result = check_source_coverage_heuristic(
            "Le budget est de 500M€ (à confirmer).",
            citations_count=0,
        )
        assert result.coverage_adequate is True

    def test_needs_disclaimer_property(self):
        result = SourceCoverageResult(
            claims_count=3,
            citations_count=0,
            coverage_adequate=False,
            disclaimer="Check sources",
        )
        assert result.needs_disclaimer is True

    def test_needs_disclaimer_false_when_adequate(self):
        result = SourceCoverageResult(
            claims_count=3,
            citations_count=3,
            coverage_adequate=True,
        )
        assert result.needs_disclaimer is False

    def test_number_patterns_detected(self):
        text = "Le montant est de 1 500 EUR et représente 42 millions du total"
        result = check_source_coverage_heuristic(text, 0)
        assert result.claims_count >= 2

    def test_date_patterns_detected(self):
        text = "La réunion du 15/03/2025 et celle de janvier 2026"
        result = check_source_coverage_heuristic(text, 0)
        assert result.claims_count >= 2


# ── Source coverage detailed analysis ─────────────────────────────


class TestSourceCoverageAnalysis:
    def test_all_cited_is_adequate(self):
        text = "Le budget est de 500M€ [Source: rapport annuel]."
        citations = [{"chunk_id": "c1"}]
        result = analyze_source_coverage(text, citations)
        assert result.coverage_adequate is True

    def test_uncited_paragraph_flagged(self):
        text = (
            "Le chiffre d'affaires est de 100 millions EUR.\n\n"
            "Le résultat net atteint 20 millions EUR.\n\n"
            "Bonjour tout le monde."
        )
        citations = []
        result = analyze_source_coverage(text, citations)
        assert result.coverage_adequate is False
        assert len(result.uncited_paragraphs) >= 2
        assert result.disclaimer is not None

    def test_mixed_cited_and_uncited(self):
        text = (
            "Le budget est de 500M€ [1].\n\n"
            "La date de livraison est le 15/06/2025."
        )
        citations = [{"chunk_id": "c1"}]
        result = analyze_source_coverage(text, citations)
        assert result.coverage_adequate is False
        assert len(result.uncited_paragraphs) == 1

    def test_no_factual_content(self):
        text = "Bonjour, je suis votre assistant.\nComment puis-je vous aider ?"
        result = analyze_source_coverage(text, [])
        assert result.coverage_adequate is True
        assert result.claims_count == 0

    def test_disclaimer_with_sous_reserve(self):
        text = "Le budget est de 500M€ (sous réserve de validation)."
        result = analyze_source_coverage(text, [])
        assert result.coverage_adequate is True


# ── Agent loop events (mocked) ────────────────────────────────────


class TestAgentLoop:
    @pytest.mark.asyncio
    async def test_emits_status_and_done(self):
        from app.core.agent_loop import AgentContext, AgentEvent, run_agent_loop

        # Mock OpenAI client to return a simple text response (no tool calls)
        mock_message_delta = MagicMock()
        mock_message_delta.content = "Voici la réponse."
        mock_message_delta.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.delta = mock_message_delta

        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        mock_chunk.usage = None

        async def mock_stream():
            yield mock_chunk

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        ctx = AgentContext(
            tenant_id=uuid4(),
            assistant_id=uuid4(),
            conversation_id=uuid4(),
            message="Test question",
            system_prompt="Tu es un assistant.",
            profile="balanced",
        )

        events: list[AgentEvent] = []
        with patch("app.core.agent_loop.AsyncOpenAI", return_value=mock_client):
            async for event in run_agent_loop(ctx):
                events.append(event)

        event_types = [e.event for e in events]
        assert "status" in event_types
        assert "token" in event_types
        assert "done" in event_types
        # The token event should contain our text
        token_events = [e for e in events if e.event == "token"]
        assert token_events[0].data == "Voici la réponse."

    @pytest.mark.asyncio
    async def test_done_event_contains_stats(self):
        from app.core.agent_loop import AgentContext, run_agent_loop

        mock_message_delta = MagicMock()
        mock_message_delta.content = "OK"
        mock_message_delta.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.delta = mock_message_delta

        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        mock_chunk.usage = None

        async def mock_stream():
            yield mock_chunk

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        ctx = AgentContext(
            tenant_id=uuid4(),
            assistant_id=uuid4(),
            conversation_id=uuid4(),
            message="Hi",
            system_prompt="Test",
            profile="balanced",
        )

        with patch("app.core.agent_loop.AsyncOpenAI", return_value=mock_client):
            events = [e async for e in run_agent_loop(ctx)]

        done_events = [e for e in events if e.event == "done"]
        assert len(done_events) == 1
        data = done_events[0].data
        assert "tokens_input" in data
        assert "tokens_output" in data
        assert "tool_rounds" in data
        assert "blocks_count" in data
        assert "citations_count" in data

    @pytest.mark.asyncio
    async def test_plan_emitted_when_present(self):
        from app.core.agent_loop import AgentContext, run_agent_loop

        mock_message_delta = MagicMock()
        mock_message_delta.content = "Done"
        mock_message_delta.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.delta = mock_message_delta

        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        mock_chunk.usage = None

        async def mock_stream():
            yield mock_chunk

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        plan = AgentPlan(
            steps=[PlanStep(id="s1", action="synthesize", description="Test")],
            reasoning="Test plan",
            profile="balanced",
        )

        ctx = AgentContext(
            tenant_id=uuid4(),
            assistant_id=uuid4(),
            conversation_id=uuid4(),
            message="Hi",
            system_prompt="Test",
            profile="balanced",
            plan=plan,
        )

        with patch("app.core.agent_loop.AsyncOpenAI", return_value=mock_client):
            events = [e async for e in run_agent_loop(ctx)]

        plan_events = [e for e in events if e.event == "plan"]
        assert len(plan_events) == 1

    @pytest.mark.asyncio
    async def test_error_on_llm_failure(self):
        from app.core.agent_loop import AgentContext, run_agent_loop

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API error")
        )

        ctx = AgentContext(
            tenant_id=uuid4(),
            assistant_id=uuid4(),
            conversation_id=uuid4(),
            message="Test",
            system_prompt="Test",
            profile="balanced",
        )

        with patch("app.core.agent_loop.AsyncOpenAI", return_value=mock_client):
            events = [e async for e in run_agent_loop(ctx)]

        error_events = [e for e in events if e.event == "error"]
        assert len(error_events) == 1
        assert "API error" in error_events[0].data

    @pytest.mark.asyncio
    async def test_budget_stops_loop(self):
        """When budget is exhausted, the loop should stop early."""
        from app.core.agent_loop import AgentContext, run_agent_loop
        from app.core.budget import BudgetManager

        mock_message_delta = MagicMock()
        mock_message_delta.content = "OK"
        mock_message_delta.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.delta = mock_message_delta

        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        mock_chunk.usage = None

        async def mock_stream():
            yield mock_chunk

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

        # Budget with 0 remaining → should skip immediately
        budget = BudgetManager(total=100, consumed=100)

        ctx = AgentContext(
            tenant_id=uuid4(),
            assistant_id=uuid4(),
            conversation_id=uuid4(),
            message="Hi",
            system_prompt="Test",
            profile="balanced",
            budget=budget,
        )

        with patch("app.core.agent_loop.AsyncOpenAI", return_value=mock_client):
            events = [e async for e in run_agent_loop(ctx)]

        # Should emit status + done but no token events (budget blocked the LLM call)
        event_types = [e.event for e in events]
        assert "done" in event_types
        token_events = [e for e in events if e.event == "token"]
        assert len(token_events) == 0


# ── SourceCoverageResult ──────────────────────────────────────────


class TestSourceCoverageResult:
    def test_slots(self):
        result = SourceCoverageResult()
        assert result.claims_count == 0
        assert result.citations_count == 0
        assert result.coverage_adequate is True
        assert result.disclaimer is None
        assert result.uncited_paragraphs == []

    def test_needs_disclaimer_true(self):
        result = SourceCoverageResult(
            coverage_adequate=False,
            disclaimer="Check this",
        )
        assert result.needs_disclaimer is True

    def test_needs_disclaimer_false_no_disclaimer(self):
        result = SourceCoverageResult(
            coverage_adequate=False,
            disclaimer=None,
        )
        assert result.needs_disclaimer is False
