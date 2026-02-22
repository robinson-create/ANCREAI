"""Tests for PR8 — Calendar wiring, Stats service, Eval harness.

Covers:
- Calendar tool registration (4 tools with handlers)
- Calendar executor dispatch (CALENDAR kwargs)
- Calendar handler wrapper (mocked calendar_handlers)
- Stats schemas
- Stats service (mocked DB)
- Eval dataset from_jsonl + filter_by_tag
- Eval metrics (precision, recall, MRR, exact/fuzzy match)
- Eval runner with mocked retrieve_fn
- Sampler config defaults
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.tool_registry import ToolCategory, ToolDefinition, ToolRegistry

# ═══════════════════════════════════════════════════════════════════
#  Calendar tool registration
# ═══════════════════════════════════════════════════════════════════


class TestCalendarToolRegistration:
    """Calendar tools are registered with handlers."""

    def test_four_calendar_tools_registered(self):
        import app.core.tools.calendar_tool as mod
        original = mod.tool_registry
        reg = ToolRegistry()
        mod.tool_registry = reg
        try:
            mod.register_calendar_tools()
            names = reg.names()
            for name in (
                "calendar_parse_command",
                "calendar_execute_command",
                "calendar_list_events",
                "calendar_find_events",
            ):
                assert name in names, f"{name} not registered"
                assert reg.get(name).category == ToolCategory.CALENDAR
                assert reg.get_handler(name) is not None
        finally:
            mod.tool_registry = original

    def test_calendar_tools_balanced_min_profile(self):
        import app.core.tools.calendar_tool as mod
        original = mod.tool_registry
        reg = ToolRegistry()
        mod.tool_registry = reg
        try:
            mod.register_calendar_tools()
            for name in reg.names():
                assert reg.get(name).min_profile == "balanced"
        finally:
            mod.tool_registry = original

    def test_calendar_tools_continue_loop(self):
        import app.core.tools.calendar_tool as mod
        original = mod.tool_registry
        reg = ToolRegistry()
        mod.tool_registry = reg
        try:
            mod.register_calendar_tools()
            for name in reg.names():
                assert reg.get(name).continues_loop is True
        finally:
            mod.tool_registry = original


# ═══════════════════════════════════════════════════════════════════
#  Calendar executor dispatch
# ═══════════════════════════════════════════════════════════════════


class TestCalendarExecutorDispatch:
    """_build_handler_kwargs dispatches CALENDAR correctly."""

    def test_build_kwargs_calendar(self):
        from app.core.tools.executor import _build_handler_kwargs

        defn = ToolDefinition(
            name="calendar_parse_command",
            category=ToolCategory.CALENDAR,
            description="test",
            openai_schema={},
        )
        tid = uuid4()
        uctx = {"tenant_id": "t1", "user_id": "u1"}

        kwargs = _build_handler_kwargs(
            definition=defn,
            arguments={"text": "rdv demain"},
            tenant_id=tid,
            assistant_id=None,
            conversation_id=None,
            collection_ids=None,
            citations=None,
            user_context=uctx,
        )

        assert kwargs["args"] == {"text": "rdv demain"}
        assert kwargs["tenant_id"] == tid
        assert kwargs["user_context"] == uctx


# ═══════════════════════════════════════════════════════════════════
#  Calendar handler wrapper
# ═══════════════════════════════════════════════════════════════════


class TestCalendarHandlerWrapper:
    """_dispatch_calendar calls the right handler with a fresh DB session."""

    @pytest.mark.asyncio
    async def test_dispatch_calls_handler(self):
        from app.core.tools.calendar_tool import handle_calendar_parse_command

        mock_handler = AsyncMock(return_value={"type": "calendar_command", "command": {}})

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.database.async_session_maker", return_value=mock_ctx),
            patch(
                "app.services.chat_tools.calendar_handlers.CALENDAR_TOOL_HANDLERS",
                {"calendar_parse_command": mock_handler},
            ),
        ):
            result = await handle_calendar_parse_command(
                args={"text": "rdv demain"},
                tenant_id=uuid4(),
                user_context={"tenant_id": "t1", "user_id": "u1"},
            )

        assert result["type"] == "calendar_command"
        mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool(self):
        from app.core.tools.calendar_tool import _dispatch_calendar

        with patch(
            "app.services.chat_tools.calendar_handlers.CALENDAR_TOOL_HANDLERS",
            {},
        ):
            result = await _dispatch_calendar(
                "unknown_tool",
                args={},
                tenant_id=uuid4(),
            )

        assert result["type"] == "error"


# ═══════════════════════════════════════════════════════════════════
#  Stats schemas
# ═══════════════════════════════════════════════════════════════════


class TestStatsSchemas:
    def test_stats_overview(self):
        from app.schemas.stats import StatsOverview

        overview = StatsOverview(
            total_runs=100,
            completed_runs=90,
            failed_runs=10,
            total_tokens_input=50000,
            total_tokens_output=30000,
            avg_latency_ms=250.0,
        )
        assert overview.total_runs == 100
        assert overview.tool_usage == []

    def test_run_stats(self):
        from app.schemas.stats import ProfileBreakdown, RunStats

        stats = RunStats(
            profiles=[ProfileBreakdown(
                profile="balanced",
                run_count=50,
                avg_tokens=1500.0,
                avg_tool_rounds=2.5,
                success_rate=0.95,
            )],
            total_runs=50,
            avg_completion_seconds=3.2,
        )
        assert stats.profiles[0].success_rate == 0.95
        assert stats.avg_completion_seconds == 3.2

    def test_tool_usage_breakdown(self):
        from app.schemas.stats import ToolUsageBreakdown

        t = ToolUsageBreakdown(tool_name="search_web", call_count=42)
        assert t.call_count == 42


# ═══════════════════════════════════════════════════════════════════
#  Stats service
# ═══════════════════════════════════════════════════════════════════


class TestStatsService:
    """StatsService with mocked DB queries."""

    @pytest.mark.asyncio
    async def test_get_overview_returns_schema(self):
        from app.services.stats import stats_service

        # Mock the two DB queries
        mock_db = AsyncMock()

        # First query: runs aggregation
        runs_row = MagicMock()
        runs_row.total = 100
        runs_row.completed = 90
        runs_row.failed = 10
        runs_row.tokens_in = 50000
        runs_row.tokens_out = 30000
        runs_result = MagicMock()
        runs_result.one.return_value = runs_row

        # Second query: latency
        latency_result = MagicMock()
        latency_result.scalar.return_value = 250.5

        # Third query: tool usage
        tool_result = MagicMock()
        tool_result.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[runs_result, latency_result, tool_result]
        )

        overview = await stats_service.get_overview(mock_db, uuid4(), days=30)

        assert overview.total_runs == 100
        assert overview.completed_runs == 90
        assert overview.total_tokens_input == 50000
        assert overview.avg_latency_ms == 250.5

    @pytest.mark.asyncio
    async def test_get_run_stats_returns_schema(self):
        from app.services.stats import stats_service

        mock_db = AsyncMock()

        # Profile aggregation
        row = MagicMock()
        row.profile = "balanced"
        row.run_count = 50
        row.avg_tokens = 1500.0
        row.avg_rounds = 2.5
        row.completed = 48
        profile_result = MagicMock()
        profile_result.all.return_value = [row]

        # Avg completion
        avg_result = MagicMock()
        avg_result.scalar.return_value = 3.2

        mock_db.execute = AsyncMock(side_effect=[profile_result, avg_result])

        stats = await stats_service.get_run_stats(mock_db, uuid4(), days=30)

        assert stats.total_runs == 50
        assert len(stats.profiles) == 1
        assert stats.profiles[0].profile == "balanced"
        assert stats.profiles[0].success_rate == 48 / 50


# ═══════════════════════════════════════════════════════════════════
#  Eval dataset
# ═══════════════════════════════════════════════════════════════════


class TestEvalDataset:
    def test_from_jsonl(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text(
            '{"query": "test query", "expected_chunks": ["c1", "c2"]}\n'
            '{"query": "second", "expected_answer": "answer", "tags": ["legal"]}\n'
        )
        from app.core.eval.dataset import EvalDataset

        ds = EvalDataset.from_jsonl(jsonl)
        assert len(ds) == 2
        assert ds.examples[0].expected_chunks == ["c1", "c2"]
        assert ds.examples[1].tags == ["legal"]

    def test_filter_by_tag(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text(
            '{"query": "q1", "tags": ["a", "b"]}\n'
            '{"query": "q2", "tags": ["b"]}\n'
            '{"query": "q3", "tags": ["a"]}\n'
        )
        from app.core.eval.dataset import EvalDataset

        ds = EvalDataset.from_jsonl(jsonl)
        filtered = ds.filter_by_tag("a")
        assert len(filtered) == 2
        assert filtered.name == "test[a]"

    def test_from_sample_fixture(self):
        from app.core.eval.dataset import EvalDataset

        fixture = Path(__file__).parent / "eval_datasets" / "sample.jsonl"
        ds = EvalDataset.from_jsonl(fixture)
        assert len(ds) == 4
        assert ds.examples[0].query == "Quels sont les termes du contrat de service?"

    def test_empty_lines_skipped(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text('{"query": "q1"}\n\n\n{"query": "q2"}\n')
        from app.core.eval.dataset import EvalDataset

        ds = EvalDataset.from_jsonl(jsonl)
        assert len(ds) == 2


# ═══════════════════════════════════════════════════════════════════
#  Eval metrics
# ═══════════════════════════════════════════════════════════════════


class TestEvalMetrics:
    def test_precision_at_k(self):
        from app.core.eval.metrics import precision_at_k

        assert precision_at_k(["a", "b", "c"], ["a", "c"], k=3) == pytest.approx(2 / 3)
        assert precision_at_k(["x", "y"], ["a"], k=2) == 0.0
        assert precision_at_k([], ["a"], k=5) == 0.0

    def test_recall_at_k(self):
        from app.core.eval.metrics import recall_at_k

        assert recall_at_k(["a", "b", "c"], ["a", "c", "d"], k=3) == pytest.approx(2 / 3)
        assert recall_at_k(["a"], [], k=5) == 1.0

    def test_mrr(self):
        from app.core.eval.metrics import mean_reciprocal_rank

        assert mean_reciprocal_rank(["x", "a", "b"], ["a"]) == pytest.approx(0.5)
        assert mean_reciprocal_rank(["a", "b"], ["a"]) == 1.0
        assert mean_reciprocal_rank(["x", "y"], ["a"]) == 0.0

    def test_compute_retrieval_metrics(self):
        from app.core.eval.metrics import compute_retrieval_metrics

        m = compute_retrieval_metrics(["a", "b", "c"], ["a", "c"], k=3)
        assert m.precision_at_k == pytest.approx(2 / 3)
        assert m.recall_at_k == 1.0
        assert m.mrr == 1.0
        assert m.k == 3

    def test_exact_match(self):
        from app.core.eval.metrics import exact_match

        assert exact_match("Hello World", "hello world") is True
        assert exact_match(" foo ", "foo") is True
        assert exact_match("a", "b") is False

    def test_fuzzy_match(self):
        from app.core.eval.metrics import fuzzy_match

        assert fuzzy_match("the quick brown fox", "quick brown fox jumps", threshold=0.6) is True
        assert fuzzy_match("completely different", "quick brown fox", threshold=0.8) is False
        assert fuzzy_match("anything", "", threshold=0.8) is True


# ═══════════════════════════════════════════════════════════════════
#  Eval runner
# ═══════════════════════════════════════════════════════════════════


class TestEvalRunner:
    @pytest.mark.asyncio
    async def test_run_with_mocked_retrieval(self, tmp_path):
        from app.core.eval.dataset import EvalDataset
        from app.core.eval.runner import EvalRunner

        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text('{"query": "q1", "expected_chunks": ["c1", "c2"]}\n')
        ds = EvalDataset.from_jsonl(jsonl)

        async def mock_retrieve(query, collection_ids):
            return ["c1", "c3", "c2"]

        runner = EvalRunner(retrieve_fn=mock_retrieve, k=3)
        report = await runner.run(ds)

        assert len(report.results) == 1
        assert report.results[0].metrics is not None
        assert report.avg_precision > 0
        assert report.avg_recall > 0
        assert report.avg_mrr == 1.0  # c1 is first

    @pytest.mark.asyncio
    async def test_run_handles_errors(self, tmp_path):
        from app.core.eval.dataset import EvalDataset
        from app.core.eval.runner import EvalRunner

        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text('{"query": "q1", "expected_chunks": ["c1"]}\n')
        ds = EvalDataset.from_jsonl(jsonl)

        async def failing_retrieve(query, collection_ids):
            raise RuntimeError("Connection lost")

        runner = EvalRunner(retrieve_fn=failing_retrieve)
        report = await runner.run(ds)

        assert len(report.results) == 1
        assert report.results[0].error == "Connection lost"
        assert report.results[0].retrieved_ids == []

    @pytest.mark.asyncio
    async def test_run_without_expected_chunks(self, tmp_path):
        from app.core.eval.dataset import EvalDataset
        from app.core.eval.runner import EvalRunner

        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text('{"query": "q1"}\n')
        ds = EvalDataset.from_jsonl(jsonl)

        async def mock_retrieve(query, collection_ids):
            return ["c1", "c2"]

        runner = EvalRunner(retrieve_fn=mock_retrieve)
        report = await runner.run(ds)

        assert report.results[0].metrics is None
        assert report.results[0].retrieved_ids == ["c1", "c2"]


# ═══════════════════════════════════════════════════════════════════
#  Sampler
# ═══════════════════════════════════════════════════════════════════


class TestSampler:
    def test_sampling_config_defaults(self):
        from app.core.eval.sampler import SamplingConfig

        config = SamplingConfig()
        assert config.per_profile == 5
        assert config.seed is None

    def test_sampling_config_custom(self):
        from app.core.eval.sampler import SamplingConfig

        config = SamplingConfig(per_profile=10, seed=42)
        assert config.per_profile == 10
        assert config.seed == 42
