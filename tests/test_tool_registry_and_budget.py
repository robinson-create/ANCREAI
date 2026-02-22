"""Tests for PR3: Tool registry, budget manager, and retrieval tool."""

import pytest

from app.core.budget import (
    BudgetExhausted,
    BudgetManager,
    Reservation,
    ReservationError,
    default_budget_for_profile,
)
from app.core.tool_registry import (
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

# ── ToolCategory enum ───────────────────────────────────────────────


class TestToolCategory:
    def test_values(self):
        assert ToolCategory.BLOCK == "block"
        assert ToolCategory.RETRIEVAL == "retrieval"
        assert ToolCategory.CALENDAR == "calendar"
        assert ToolCategory.INTEGRATION == "integration"
        assert ToolCategory.EMAIL == "email"

    def test_all_categories(self):
        assert len(ToolCategory) == 6


# ── ToolDefinition model ────────────────────────────────────────────


class TestToolDefinition:
    def test_minimal_definition(self):
        td = ToolDefinition(
            name="test_tool",
            category=ToolCategory.BLOCK,
            description="A test tool",
            openai_schema={"type": "function", "function": {"name": "test_tool"}},
        )
        assert td.name == "test_tool"
        assert td.category == ToolCategory.BLOCK
        assert td.continues_loop is False
        assert td.requires_confirmation is False
        assert td.timeout_seconds == 30
        assert td.max_retries == 0
        assert td.min_profile == "reactive"
        assert td.provider is None
        assert td.block_type is None

    def test_full_definition(self):
        td = ToolDefinition(
            name="hubspot_search",
            category=ToolCategory.INTEGRATION,
            provider="hubspot",
            description="Search HubSpot contacts",
            openai_schema={"type": "function", "function": {"name": "hubspot_search"}},
            continues_loop=True,
            requires_confirmation=True,
            timeout_seconds=60,
            max_retries=2,
            min_profile="balanced",
        )
        assert td.provider == "hubspot"
        assert td.continues_loop is True
        assert td.requires_confirmation is True
        assert td.timeout_seconds == 60
        assert td.min_profile == "balanced"


# ── ToolRegistry ────────────────────────────────────────────────────


def _make_tool(name: str, category: ToolCategory = ToolCategory.BLOCK,
               provider: str | None = None, min_profile: str = "reactive") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        category=category,
        provider=provider,
        description=f"Test tool: {name}",
        openai_schema={"type": "function", "function": {"name": name}},
        continues_loop=category != ToolCategory.BLOCK,
        min_profile=min_profile,
    )


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = _make_tool("my_tool")
        reg.register(tool)
        assert reg.get("my_tool") == tool
        assert reg.get("nonexistent") is None

    def test_names(self):
        reg = ToolRegistry()
        reg.register(_make_tool("a"))
        reg.register(_make_tool("b"))
        assert reg.names() == {"a", "b"}

    def test_all_tools(self):
        reg = ToolRegistry()
        reg.register(_make_tool("x"))
        reg.register(_make_tool("y"))
        assert len(reg.all_tools()) == 2

    def test_by_category(self):
        reg = ToolRegistry()
        reg.register(_make_tool("block1", ToolCategory.BLOCK))
        reg.register(_make_tool("cal1", ToolCategory.CALENDAR))
        reg.register(_make_tool("block2", ToolCategory.BLOCK))

        blocks = reg.by_category(ToolCategory.BLOCK)
        assert len(blocks) == 2
        assert all(t.category == ToolCategory.BLOCK for t in blocks)

    def test_by_provider(self):
        reg = ToolRegistry()
        reg.register(_make_tool("hs1", ToolCategory.INTEGRATION, provider="hubspot"))
        reg.register(_make_tool("hs2", ToolCategory.INTEGRATION, provider="hubspot"))
        reg.register(_make_tool("gm1", ToolCategory.INTEGRATION, provider="gmail"))

        hs = reg.by_provider("hubspot")
        assert len(hs) == 2

    def test_handler_registration(self):
        reg = ToolRegistry()
        tool = _make_tool("handled")

        async def handler(**kwargs):
            return "result"

        reg.register(tool, handler=handler)
        assert reg.get_handler("handled") is handler
        assert reg.get_handler("nonexistent") is None

    def test_find_provider(self):
        reg = ToolRegistry()
        reg.register(_make_tool("hs_tool", ToolCategory.INTEGRATION, provider="hubspot"))
        assert reg.find_provider("hs_tool") == "hubspot"
        assert reg.find_provider("missing") is None


# ── Profile gating ──────────────────────────────────────────────────


class TestProfileGating:
    def setup_method(self):
        self.reg = ToolRegistry()
        self.reg.register(_make_tool("reactive_tool", min_profile="reactive"))
        self.reg.register(_make_tool("balanced_tool", min_profile="balanced"))
        self.reg.register(_make_tool("pro_tool", min_profile="pro"))
        self.reg.register(_make_tool("exec_tool", min_profile="exec"))

    def test_reactive_sees_only_reactive(self):
        tools = self.reg.get_allowed_tools(profile="reactive")
        names = {t.name for t in tools}
        assert names == {"reactive_tool"}

    def test_balanced_sees_reactive_and_balanced(self):
        tools = self.reg.get_allowed_tools(profile="balanced")
        names = {t.name for t in tools}
        assert names == {"reactive_tool", "balanced_tool"}

    def test_pro_sees_three(self):
        tools = self.reg.get_allowed_tools(profile="pro")
        names = {t.name for t in tools}
        assert names == {"reactive_tool", "balanced_tool", "pro_tool"}

    def test_exec_sees_all(self):
        tools = self.reg.get_allowed_tools(profile="exec")
        names = {t.name for t in tools}
        assert names == {"reactive_tool", "balanced_tool", "pro_tool", "exec_tool"}

    def test_unknown_profile_treated_as_reactive(self):
        tools = self.reg.get_allowed_tools(profile="unknown")
        names = {t.name for t in tools}
        assert names == {"reactive_tool"}


# ── Category & provider filtering ───────────────────────────────────


class TestToolFiltering:
    def setup_method(self):
        self.reg = ToolRegistry()
        self.reg.register(_make_tool("block1", ToolCategory.BLOCK))
        self.reg.register(_make_tool("retrieval1", ToolCategory.RETRIEVAL))
        self.reg.register(_make_tool("cal1", ToolCategory.CALENDAR, min_profile="balanced"))
        self.reg.register(
            _make_tool("hs_search", ToolCategory.INTEGRATION, provider="hubspot", min_profile="balanced")
        )
        self.reg.register(
            _make_tool("gm_send", ToolCategory.INTEGRATION, provider="gmail", min_profile="balanced")
        )

    def test_category_whitelist(self):
        tools = self.reg.get_allowed_tools(
            profile="exec",
            allowed_categories={ToolCategory.BLOCK, ToolCategory.RETRIEVAL},
        )
        names = {t.name for t in tools}
        assert names == {"block1", "retrieval1"}

    def test_integration_needs_provider(self):
        # Without providers, integration tools are excluded
        tools = self.reg.get_allowed_tools(profile="exec")
        names = {t.name for t in tools}
        assert "hs_search" not in names
        assert "gm_send" not in names

    def test_integration_with_connected_provider(self):
        tools = self.reg.get_allowed_tools(profile="exec", providers=["hubspot"])
        names = {t.name for t in tools}
        assert "hs_search" in names
        assert "gm_send" not in names

    def test_blocked_tools(self):
        tools = self.reg.get_allowed_tools(
            profile="exec",
            blocked_tools={"block1", "retrieval1"},
        )
        names = {t.name for t in tools}
        assert "block1" not in names
        assert "retrieval1" not in names

    def test_get_openai_schemas(self):
        schemas = self.reg.get_openai_schemas(profile="reactive")
        assert all(isinstance(s, dict) for s in schemas)
        assert len(schemas) == 2  # block1 + retrieval1 (both reactive min_profile)


# ── BudgetManager ───────────────────────────────────────────────────


class TestBudgetManager:
    def test_initial_state(self):
        bm = BudgetManager(total=10_000)
        assert bm.total == 10_000
        assert bm.consumed == 0
        assert bm.remaining == 10_000
        assert bm.hard_remaining == 10_000

    def test_consume(self):
        bm = BudgetManager(total=10_000)
        bm.consume(3_000)
        assert bm.consumed == 3_000
        assert bm.remaining == 7_000

    def test_consume_exceeds_budget(self):
        bm = BudgetManager(total=1_000)
        with pytest.raises(BudgetExhausted) as exc_info:
            bm.consume(2_000)
        assert exc_info.value.requested == 2_000
        assert exc_info.value.remaining == 1_000

    def test_consume_safe(self):
        bm = BudgetManager(total=1_000)
        assert bm.consume_safe(500) is True
        assert bm.consumed == 500
        assert bm.consume_safe(600) is False
        assert bm.consumed == 500  # unchanged

    def test_check(self):
        bm = BudgetManager(total=1_000)
        assert bm.check(500) is True
        assert bm.check(1_001) is False

    def test_multiple_consumes(self):
        bm = BudgetManager(total=10_000)
        bm.consume(3_000)
        bm.consume(2_000)
        bm.consume(4_000)
        assert bm.remaining == 1_000
        with pytest.raises(BudgetExhausted):
            bm.consume(1_001)


# ── Reservations ────────────────────────────────────────────────────


class TestReservations:
    def test_reserve_subtracts_from_remaining(self):
        bm = BudgetManager(total=10_000)
        res = bm.reserve("child1", 3_000)
        assert bm.remaining == 7_000
        assert bm.hard_remaining == 10_000  # not consumed yet
        assert res.allocated == 3_000
        assert res.remaining == 3_000

    def test_reserve_exceeds_remaining(self):
        bm = BudgetManager(total=5_000)
        bm.consume(3_000)
        with pytest.raises(BudgetExhausted):
            bm.reserve("big", 3_000)

    def test_duplicate_reservation_label(self):
        bm = BudgetManager(total=10_000)
        bm.reserve("child1", 2_000)
        with pytest.raises(ReservationError):
            bm.reserve("child1", 1_000)

    def test_release_returns_unused(self):
        bm = BudgetManager(total=10_000)
        res = bm.reserve("child1", 5_000)
        res.consume(2_000)

        returned = bm.release(res)
        assert returned == 3_000
        assert bm.consumed == 2_000  # only consumed part
        assert bm.remaining == 8_000

    def test_release_unknown_reservation(self):
        bm = BudgetManager(total=10_000)
        fake = Reservation(label="ghost", allocated=1_000)
        with pytest.raises(ReservationError):
            bm.release(fake)

    def test_reservation_consume_exceeds(self):
        res = Reservation(label="test", allocated=1_000)
        with pytest.raises(BudgetExhausted):
            res.consume(1_500)

    def test_multiple_reservations(self):
        bm = BudgetManager(total=20_000)
        r1 = bm.reserve("search", 5_000)
        r2 = bm.reserve("delegation", 8_000)
        assert bm.remaining == 7_000

        r1.consume(2_000)
        bm.release(r1)  # returns 3_000 to pool
        assert bm.remaining == 10_000  # 20_000 - 2_000 consumed - 8_000 reserved

        r2.consume(4_000)
        bm.release(r2)
        assert bm.remaining == 14_000  # 20_000 - 6_000 consumed


# ── Budget snapshot ─────────────────────────────────────────────────


class TestBudgetSnapshot:
    def test_snapshot_empty(self):
        bm = BudgetManager(total=5_000)
        snap = bm.snapshot()
        assert snap["total"] == 5_000
        assert snap["consumed"] == 0
        assert snap["remaining"] == 5_000
        assert snap["reservations"] == {}

    def test_snapshot_with_reservation(self):
        bm = BudgetManager(total=10_000)
        bm.consume(2_000)
        res = bm.reserve("child", 3_000)
        res.consume(1_000)

        snap = bm.snapshot()
        assert snap["total"] == 10_000
        assert snap["consumed"] == 2_000
        assert snap["remaining"] == 6_000  # 10_000 - 2_000 consumed - 2_000 res.remaining
        assert "child" in snap["reservations"]
        assert snap["reservations"]["child"]["allocated"] == 3_000
        assert snap["reservations"]["child"]["consumed"] == 1_000


# ── Default budgets per profile ─────────────────────────────────────


class TestDefaultBudgets:
    def test_reactive(self):
        assert default_budget_for_profile("reactive") == 8_000

    def test_balanced(self):
        assert default_budget_for_profile("balanced") == 30_000

    def test_pro(self):
        assert default_budget_for_profile("pro") == 80_000

    def test_exec(self):
        assert default_budget_for_profile("exec") == 200_000

    def test_unknown_defaults_to_reactive(self):
        assert default_budget_for_profile("unknown") == 8_000


# ── Retrieval tool schema ──────────────────────────────────────────


class TestRetrievalToolSchema:
    def test_schema_structure(self):
        from app.core.tools.retrieval_tool import RETRIEVAL_TOOL_SCHEMA

        assert RETRIEVAL_TOOL_SCHEMA["type"] == "function"
        func = RETRIEVAL_TOOL_SCHEMA["function"]
        assert func["name"] == "search_documents"
        assert "query" in func["parameters"]["properties"]
        assert "query" in func["parameters"]["required"]

    def test_register_retrieval_tool(self):
        from app.core.tools.retrieval_tool import register_retrieval_tool

        reg = ToolRegistry()
        # Use a fresh registry via monkeypatch
        import app.core.tools.retrieval_tool as rt_mod
        original = rt_mod.tool_registry
        rt_mod.tool_registry = reg

        try:
            register_retrieval_tool()
            tool = reg.get("search_documents")
            assert tool is not None
            assert tool.category == ToolCategory.RETRIEVAL
            assert tool.continues_loop is True
            assert tool.min_profile == "reactive"
        finally:
            rt_mod.tool_registry = original
