"""Tests for PR4: Email tool, document tool, and tool executor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.tool_registry import ToolCategory, ToolDefinition, ToolRegistry
from app.core.tools.executor import (
    ToolExecutionResult,
    execute_tool_call,
)

# ── Email tool schema ──────────────────────────────────────────────


class TestEmailToolSchema:
    def test_schema_structure(self):
        from app.core.tools.email_tool import SUGGEST_EMAIL_SCHEMA

        assert SUGGEST_EMAIL_SCHEMA["type"] == "function"
        func = SUGGEST_EMAIL_SCHEMA["function"]
        assert func["name"] == "suggestEmail"
        assert func["strict"] is True

        props = func["parameters"]["properties"]
        assert "subject" in props
        assert "body_draft" in props
        assert "tone" in props
        assert "reason" in props
        assert set(func["parameters"]["required"]) == {
            "subject", "body_draft", "tone", "reason"
        }

    def test_tone_enum(self):
        from app.core.tools.email_tool import SUGGEST_EMAIL_SCHEMA

        tone = SUGGEST_EMAIL_SCHEMA["function"]["parameters"]["properties"]["tone"]
        assert tone["enum"] == ["formal", "friendly", "neutral"]


class TestEmailToolRegistration:
    def test_registers_in_registry(self):
        from app.core.tools.email_tool import register_email_tool

        reg = ToolRegistry()
        import app.core.tools.email_tool as mod
        original = mod.tool_registry
        mod.tool_registry = reg

        try:
            register_email_tool()
            tool = reg.get("suggestEmail")
            assert tool is not None
            assert tool.category == ToolCategory.EMAIL
            assert tool.block_type == "email_suggestion"
            assert tool.continues_loop is False
            assert tool.min_profile == "reactive"
            # Handler should be registered
            assert reg.get_handler("suggestEmail") is not None
        finally:
            mod.tool_registry = original


class TestEmailToolHandler:
    @pytest.mark.asyncio
    async def test_handle_creates_bundle(self):
        from app.core.tools.email_tool import handle_suggest_email

        tenant_id = uuid4()
        conversation_id = uuid4()
        args = {
            "subject": "Synthèse réunion",
            "body_draft": "<p>Bonjour,</p><p>Suite à notre réunion...</p>",
            "tone": "formal",
            "reason": "Cette synthèse peut être envoyée aux participants",
        }

        mock_bundle = MagicMock()
        mock_bundle.id = uuid4()

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.database.async_session_maker", return_value=mock_session),
            patch("app.models.mail.EmailDraftBundle", return_value=mock_bundle),
        ):
            result = await handle_suggest_email(
                args=args,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                citations=[{"chunk_id": "c1"}],
            )

        assert result["type"] == "email_suggestion"
        assert result["payload"]["bundle_id"] == str(mock_bundle.id)
        assert result["payload"]["subject"] == "Synthèse réunion"
        assert result["payload"]["tone"] == "formal"
        mock_session.add.assert_called_once_with(mock_bundle)
        mock_session.commit.assert_called_once()


# ── Document tool schema ───────────────────────────────────────────


class TestDocumentToolSchema:
    def test_schema_structure(self):
        from app.core.tools.document_tool import CREATE_DOCUMENT_SCHEMA

        assert CREATE_DOCUMENT_SCHEMA["type"] == "function"
        func = CREATE_DOCUMENT_SCHEMA["function"]
        assert func["name"] == "createDocument"
        assert func["strict"] is True

        props = func["parameters"]["properties"]
        assert "title" in props
        assert "doc_type" in props
        assert "content_html" in props
        assert "reason" in props
        assert set(func["parameters"]["required"]) == {
            "title", "doc_type", "content_html", "reason"
        }

    def test_doc_type_enum(self):
        from app.core.tools.document_tool import CREATE_DOCUMENT_SCHEMA

        doc_type = CREATE_DOCUMENT_SCHEMA["function"]["parameters"]["properties"]["doc_type"]
        assert "generic" in doc_type["enum"]
        assert "proposal" in doc_type["enum"]
        assert "report" in doc_type["enum"]
        assert "contract" in doc_type["enum"]


class TestDocumentToolRegistration:
    def test_registers_in_registry(self):
        from app.core.tools.document_tool import register_document_tool

        reg = ToolRegistry()
        import app.core.tools.document_tool as mod
        original = mod.tool_registry
        mod.tool_registry = reg

        try:
            register_document_tool()
            tool = reg.get("createDocument")
            assert tool is not None
            assert tool.category == ToolCategory.BLOCK
            assert tool.block_type == "doc_suggestion"
            assert tool.continues_loop is False
            assert reg.get_handler("createDocument") is not None
        finally:
            mod.tool_registry = original


class TestDocumentToolHandler:
    @pytest.mark.asyncio
    async def test_handle_creates_document(self):
        from app.core.tools.document_tool import handle_create_document

        tenant_id = uuid4()
        assistant_id = uuid4()
        conversation_id = uuid4()
        args = {
            "title": "Proposition commerciale",
            "doc_type": "proposal",
            "content_html": "<h1>Proposition</h1><p>Détails de l'offre...</p>",
            "reason": "Le contenu de la conversation peut être transformé en proposition",
        }

        mock_doc = MagicMock()
        mock_doc.id = uuid4()

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.database.async_session_maker", return_value=mock_session),
            patch("app.models.workspace_document.WorkspaceDocument", return_value=mock_doc),
        ):
            result = await handle_create_document(
                args=args,
                tenant_id=tenant_id,
                assistant_id=assistant_id,
                conversation_id=conversation_id,
            )

        assert result["type"] == "doc_suggestion"
        assert result["payload"]["document_id"] == str(mock_doc.id)
        assert result["payload"]["title"] == "Proposition commerciale"
        assert result["payload"]["doc_type"] == "proposal"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_with_db_session(self):
        """When a db session is provided, use it directly instead of creating one."""
        from app.core.tools.document_tool import handle_create_document

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        mock_doc = MagicMock()
        mock_doc.id = uuid4()

        with patch("app.models.workspace_document.WorkspaceDocument", return_value=mock_doc):
            result = await handle_create_document(
                args={
                    "title": "Test Doc",
                    "doc_type": "generic",
                    "content_html": "<p>Test</p>",
                    "reason": "test",
                },
                tenant_id=uuid4(),
                db=mock_db,
            )

        assert result["type"] == "doc_suggestion"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()


class TestHtmlToProsemirror:
    def test_basic_conversion(self):
        from app.core.tools.document_tool import _html_to_prosemirror

        result = _html_to_prosemirror("<p>Hello world</p>")
        assert result["type"] == "doc"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "paragraph"
        assert result["content"][0]["content"][0]["text"] == "<p>Hello world</p>"


# ── Tool executor ──────────────────────────────────────────────────


class TestToolExecutionResult:
    def test_success_result(self):
        result = ToolExecutionResult(
            tool_name="test",
            category=ToolCategory.BLOCK,
            result={"key": "value"},
        )
        assert result.success is True
        assert result.error is None
        assert '"key"' in result.to_tool_message()

    def test_error_result(self):
        result = ToolExecutionResult(
            tool_name="test",
            category=ToolCategory.BLOCK,
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert "error" in result.to_tool_message()

    def test_block_result(self):
        block = {"id": "123", "type": "kpi_cards", "payload": {"cards": []}}
        result = ToolExecutionResult(
            tool_name="renderKpiCards",
            category=ToolCategory.BLOCK,
            result=block,
            block=block,
        )
        assert result.block is not None
        assert result.block["type"] == "kpi_cards"


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await execute_tool_call(
            tool_name="nonexistent_tool",
            arguments={},
            tenant_id=uuid4(),
        )
        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_block_tool_without_handler(self):
        """Block tools without handlers should return the arguments as a block."""
        from app.core.tool_registry import tool_registry

        # Register a block tool without a handler
        tool_registry.register(ToolDefinition(
            name="testBlockTool",
            category=ToolCategory.BLOCK,
            description="Test block tool",
            openai_schema={"type": "function", "function": {"name": "testBlockTool"}},
            block_type="test_block",
        ))

        try:
            result = await execute_tool_call(
                tool_name="testBlockTool",
                arguments={"cards": [{"label": "Revenue", "value": "100K"}]},
                tenant_id=uuid4(),
            )
            assert result.success is True
            assert result.block is not None
            assert result.block["type"] == "test_block"
        finally:
            # Cleanup
            del tool_registry._tools["testBlockTool"]

    @pytest.mark.asyncio
    async def test_handler_execution(self):
        """Tools with handlers should have their handler invoked."""
        from app.core.tool_registry import tool_registry

        async def mock_handler(**kwargs):
            return {"type": "test_result", "payload": {"ok": True}}

        tool_registry.register(
            ToolDefinition(
                name="testHandlerTool",
                category=ToolCategory.BLOCK,
                description="Test handler tool",
                openai_schema={"type": "function", "function": {"name": "testHandlerTool"}},
            ),
            handler=mock_handler,
        )

        try:
            result = await execute_tool_call(
                tool_name="testHandlerTool",
                arguments={"key": "value"},
                tenant_id=uuid4(),
            )
            assert result.success is True
            assert result.result == {"type": "test_result", "payload": {"ok": True}}
        finally:
            del tool_registry._tools["testHandlerTool"]
            del tool_registry._handlers["testHandlerTool"]

    @pytest.mark.asyncio
    async def test_handler_timeout(self):
        """Tools that exceed their timeout should return an error."""
        import asyncio

        from app.core.tool_registry import tool_registry

        async def slow_handler(**kwargs):
            await asyncio.sleep(10)
            return {"result": "too late"}

        tool_registry.register(
            ToolDefinition(
                name="slowTool",
                category=ToolCategory.BLOCK,
                description="Slow tool",
                openai_schema={"type": "function", "function": {"name": "slowTool"}},
                timeout_seconds=1,
            ),
            handler=slow_handler,
        )

        try:
            result = await execute_tool_call(
                tool_name="slowTool",
                arguments={},
                tenant_id=uuid4(),
            )
            assert result.success is False
            assert "timed out" in result.error
        finally:
            del tool_registry._tools["slowTool"]
            del tool_registry._handlers["slowTool"]

    @pytest.mark.asyncio
    async def test_handler_exception(self):
        """Tools that raise exceptions should return an error."""
        from app.core.tool_registry import tool_registry

        async def failing_handler(**kwargs):
            raise ValueError("Something broke")

        tool_registry.register(
            ToolDefinition(
                name="failingTool",
                category=ToolCategory.BLOCK,
                description="Failing tool",
                openai_schema={"type": "function", "function": {"name": "failingTool"}},
            ),
            handler=failing_handler,
        )

        try:
            result = await execute_tool_call(
                tool_name="failingTool",
                arguments={},
                tenant_id=uuid4(),
            )
            assert result.success is False
            assert "Something broke" in result.error
        finally:
            del tool_registry._tools["failingTool"]
            del tool_registry._handlers["failingTool"]


# ── Integration: registry with all PR4 tools ───────────────────────


class TestPR4ToolsIntegration:
    def test_all_pr4_tools_register(self):
        """Verify both email and document tools can be registered together."""
        from app.core.tools.document_tool import register_document_tool
        from app.core.tools.email_tool import register_email_tool

        reg = ToolRegistry()

        # Temporarily swap registries
        import app.core.tools.document_tool as doc_mod
        import app.core.tools.email_tool as email_mod
        orig_email = email_mod.tool_registry
        orig_doc = doc_mod.tool_registry
        email_mod.tool_registry = reg
        doc_mod.tool_registry = reg

        try:
            register_email_tool()
            register_document_tool()

            assert reg.get("suggestEmail") is not None
            assert reg.get("createDocument") is not None

            # Both should be accessible to reactive profile
            allowed = reg.get_allowed_tools(profile="reactive")
            names = {t.name for t in allowed}
            assert "suggestEmail" in names
            assert "createDocument" in names

            # Both should have handlers
            assert reg.get_handler("suggestEmail") is not None
            assert reg.get_handler("createDocument") is not None
        finally:
            email_mod.tool_registry = orig_email
            doc_mod.tool_registry = orig_doc

    def test_email_tool_category_is_email(self):
        """Email tool should be in EMAIL category (not BLOCK)."""
        from app.core.tools.email_tool import register_email_tool

        reg = ToolRegistry()
        import app.core.tools.email_tool as mod
        orig = mod.tool_registry
        mod.tool_registry = reg

        try:
            register_email_tool()
            tool = reg.get("suggestEmail")
            assert tool.category == ToolCategory.EMAIL
        finally:
            mod.tool_registry = orig

    def test_document_tool_category_is_block(self):
        """Document tool should be in BLOCK category."""
        from app.core.tools.document_tool import register_document_tool

        reg = ToolRegistry()
        import app.core.tools.document_tool as mod
        orig = mod.tool_registry
        mod.tool_registry = reg

        try:
            register_document_tool()
            tool = reg.get("createDocument")
            assert tool.category == ToolCategory.BLOCK
        finally:
            mod.tool_registry = orig
