"""Centralized tool registry — single source of truth for all agent tools.

Each tool has:
- A Pydantic-strict definition (name, category, metadata)
- An OpenAI function-calling schema (passed to the LLM)
- Gating rules (which profiles/providers can use it)
- An optional async handler

The registry is populated at import time by register_builtin_tools().
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

# ── Enums ────────────────────────────────────────────────────────────


class ToolCategory(StrEnum):
    """Tool category determines execution path."""

    BLOCK = "block"              # Generative UI — no loop continuation
    RETRIEVAL = "retrieval"      # Internal RAG search
    CALENDAR = "calendar"        # Calendar actions — loop continues
    INTEGRATION = "integration"  # Nango-based external APIs — loop continues
    EMAIL = "email"              # Email suggestion — no loop continuation
    DELEGATION = "delegation"    # Delegate to another assistant — loop continues


# ── Tool definition ──────────────────────────────────────────────────


class ToolDefinition(BaseModel):
    """Pydantic-strict tool registration entry."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    category: ToolCategory
    provider: str | None = None  # e.g. "hubspot", "gmail", None for builtins
    description: str
    openai_schema: dict  # Full OpenAI function-calling dict
    block_type: str | None = None  # Block type for UI rendering
    continues_loop: bool = False  # Whether tool result re-enters LLM loop
    requires_confirmation: bool = False  # Exec-profile: needs user confirm
    timeout_seconds: int = 30
    max_retries: int = 0
    min_profile: str = "reactive"  # Minimum agent profile required


# ── Registry ─────────────────────────────────────────────────────────

# Profile hierarchy for comparison
_PROFILE_ORDER = {"reactive": 0, "balanced": 1, "pro": 2, "exec": 3}


class ToolRegistry:
    """In-memory registry of all available tools.

    Thread-safe for reads (populated once at startup).
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}

    def register(
        self,
        definition: ToolDefinition,
        handler: Callable[..., Coroutine[Any, Any, Any]] | None = None,
    ) -> None:
        self._tools[definition.name] = definition
        if handler is not None:
            self._handlers[definition.name] = handler

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_handler(self, name: str) -> Callable[..., Coroutine[Any, Any, Any]] | None:
        return self._handlers.get(name)

    def all_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def by_category(self, category: ToolCategory) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.category == category]

    def by_provider(self, provider: str) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.provider == provider]

    def names(self) -> set[str]:
        return set(self._tools.keys())

    # ── Filtering for a specific run context ─────────────────────

    def get_allowed_tools(
        self,
        *,
        profile: str = "reactive",
        providers: list[str] | None = None,
        allowed_categories: set[ToolCategory] | None = None,
        blocked_tools: set[str] | None = None,
    ) -> list[ToolDefinition]:
        """Return tools allowed for a given profile + provider set.

        Args:
            profile: Agent profile (reactive/balanced/pro/exec)
            providers: Connected integration providers (e.g. ["hubspot", "gmail"])
            allowed_categories: Whitelist of categories (None = all)
            blocked_tools: Explicit blocklist of tool names
        """
        profile_level = _PROFILE_ORDER.get(profile, 0)
        result: list[ToolDefinition] = []

        for tool in self._tools.values():
            # Profile gating
            tool_min = _PROFILE_ORDER.get(tool.min_profile, 0)
            if profile_level < tool_min:
                continue

            # Category gating
            if allowed_categories is not None and tool.category not in allowed_categories:
                continue

            # Explicit blocklist
            if blocked_tools and tool.name in blocked_tools:
                continue

            # Integration tools require provider to be connected
            if tool.category == ToolCategory.INTEGRATION and (
                providers is None or tool.provider not in providers
            ):
                continue

            result.append(tool)

        return result

    def get_openai_schemas(
        self,
        tools: list[ToolDefinition] | None = None,
        **filter_kwargs,
    ) -> list[dict]:
        """Get OpenAI function-calling schemas for allowed tools.

        Either pass pre-filtered tools or filter kwargs for get_allowed_tools().
        """
        if tools is None:
            tools = self.get_allowed_tools(**filter_kwargs)
        return [t.openai_schema for t in tools]

    def find_provider(self, tool_name: str) -> str | None:
        """Find which provider owns a tool."""
        tool = self._tools.get(tool_name)
        return tool.provider if tool else None


# ── Singleton ────────────────────────────────────────────────────────

tool_registry = ToolRegistry()


# ── Built-in tool registration ───────────────────────────────────────

def _register_block_tools() -> None:
    """Register the 5 generative UI block tools."""
    from app.services.chat import (
        BLOCK_TOOL_CALLOUT,
        BLOCK_TOOL_KPI,
        BLOCK_TOOL_STEPS,
        BLOCK_TOOL_TABLE,
    )

    _BLOCK_DEFS = [
        (BLOCK_TOOL_KPI, "kpi_cards", "Display KPI metric cards"),
        (BLOCK_TOOL_TABLE, "table", "Display data in a table"),
        (BLOCK_TOOL_STEPS, "steps", "Display sequential steps"),
        (BLOCK_TOOL_CALLOUT, "callout", "Display alert or callout"),
    ]

    for schema, block_type, desc in _BLOCK_DEFS:
        tool_registry.register(ToolDefinition(
            name=schema["function"]["name"],
            category=ToolCategory.BLOCK,
            description=desc,
            openai_schema=schema,
            block_type=block_type,
            continues_loop=False,
            min_profile="reactive",
        ))


def _register_email_tool() -> None:
    """Register the suggestEmail tool with its handler."""
    from app.core.tools.email_tool import register_email_tool
    register_email_tool()


def _register_calendar_tools() -> None:
    """Register calendar tools with handlers."""
    from app.core.tools.calendar_tool import register_calendar_tools
    register_calendar_tools()


def _register_integration_tools() -> None:
    """Register all Nango provider tools."""
    from app.integrations.nango.tools.registry import (
        _PROVIDER_MODULES,
        get_tools_for_provider,
    )

    for provider in _PROVIDER_MODULES:
        for schema in get_tools_for_provider(provider):
            name = schema["function"]["name"]
            tool_registry.register(ToolDefinition(
                name=name,
                category=ToolCategory.INTEGRATION,
                provider=provider,
                description=schema["function"].get("description", name),
                openai_schema=schema,
                continues_loop=True,
                min_profile="balanced",
                timeout_seconds=30,
            ))


def register_builtin_tools() -> None:
    """Register all built-in tools. Call once at startup."""
    _register_block_tools()
    _register_email_tool()
    _register_calendar_tools()
    _register_integration_tools()

    from app.core.tools.contact_tools import register_contact_tools
    from app.core.tools.delegation_tool import register_delegation_tool
    from app.core.tools.document_tool import register_document_tool
    from app.core.tools.retrieval_tool import register_retrieval_tool
    from app.core.tools.web_search_tool import register_web_search_tool
    register_retrieval_tool()
    register_contact_tools()
    register_document_tool()
    register_web_search_tool()
    register_delegation_tool()
