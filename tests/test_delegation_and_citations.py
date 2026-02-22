"""Tests for PR7 — delegation tool + citation registry.

Covers:
- CitationEntry dedup key
- CitationRegistry: add / merge / dedup / all_dicts
- Delegation budget caps per profile
- Delegation tool schema structure
- Delegation tool registration
- Executor _build_handler_kwargs for DELEGATION
- Delegation handler (mocked DB, retrieval, LLM)
- Agent loop delegation result handling
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.budget import BudgetManager
from app.core.citation_registry import CitationEntry, CitationRegistry

# ═══════════════════════════════════════════════════════════════════
#  Citation Registry
# ═══════════════════════════════════════════════════════════════════


class TestCitationEntry:
    """CitationEntry.dedup_key logic."""

    def test_dedup_key_with_page(self):
        entry = CitationEntry(
            chunk_id="c1", document_id="d1", document_filename="f.pdf", page_number=3
        )
        assert entry.dedup_key == "d1:p3"

    def test_dedup_key_without_page(self):
        entry = CitationEntry(
            chunk_id="c1", document_id="d1", document_filename="f.pdf"
        )
        assert entry.dedup_key == "d1:c1"

    def test_dedup_key_page_zero(self):
        entry = CitationEntry(
            chunk_id="c1", document_id="d1", document_filename="f.pdf", page_number=0
        )
        assert entry.dedup_key == "d1:p0"


class TestCitationRegistry:
    """CitationRegistry add/merge/dedup."""

    def _entry(self, *, doc="d1", page=None, chunk="c1", score=0.5):
        return CitationEntry(
            chunk_id=chunk, document_id=doc, document_filename="f.pdf",
            page_number=page, score=score,
        )

    def test_add_new(self):
        reg = CitationRegistry()
        assert reg.add(self._entry()) is True
        assert reg.count == 1

    def test_add_duplicate_returns_false(self):
        reg = CitationRegistry()
        reg.add(self._entry(score=0.5))
        assert reg.add(self._entry(score=0.3)) is False
        assert reg.count == 1

    def test_add_duplicate_keeps_higher_score(self):
        reg = CitationRegistry()
        reg.add(self._entry(score=0.3))
        reg.add(self._entry(score=0.8))
        entries = reg.all_dicts()
        assert len(entries) == 1
        assert entries[0]["score"] == 0.8

    def test_add_duplicate_lower_score_no_replace(self):
        reg = CitationRegistry()
        reg.add(self._entry(score=0.9))
        reg.add(self._entry(score=0.1))
        assert reg.all_dicts()[0]["score"] == 0.9

    def test_add_different_pages_are_different(self):
        reg = CitationRegistry()
        reg.add(self._entry(page=1))
        reg.add(self._entry(page=2))
        assert reg.count == 2

    def test_merge_returns_only_new(self):
        reg = CitationRegistry()
        reg.add(self._entry(doc="d1", chunk="c1"))

        new = reg.merge(
            [
                {"chunk_id": "c1", "document_id": "d1", "document_filename": "f.pdf"},
                {"chunk_id": "c2", "document_id": "d2", "document_filename": "g.pdf"},
            ],
            source_assistant_id="a1",
        )
        assert len(new) == 1
        assert new[0]["chunk_id"] == "c2"
        assert reg.count == 2

    def test_add_from_dict_with_url(self):
        reg = CitationRegistry()
        reg.add_from_dict({
            "chunk_id": "web_1", "document_id": "web:http://x.com",
            "document_filename": "x.com", "url": "http://x.com",
        })
        dicts = reg.all_dicts()
        assert len(dicts) == 1
        assert dicts[0]["url"] == "http://x.com"

    def test_all_dicts_omits_none_url_and_source(self):
        reg = CitationRegistry()
        reg.add(self._entry())
        d = reg.all_dicts()[0]
        assert "url" not in d
        assert "source_assistant_id" not in d

    def test_all_dicts_includes_source_assistant(self):
        reg = CitationRegistry()
        reg.add_from_dict(
            {"chunk_id": "c1", "document_id": "d1", "document_filename": "f.pdf"},
            source_assistant_id="a99",
        )
        d = reg.all_dicts()[0]
        assert d["source_assistant_id"] == "a99"

    def test_clear(self):
        reg = CitationRegistry()
        reg.add(self._entry())
        reg.clear()
        assert reg.count == 0


# ═══════════════════════════════════════════════════════════════════
#  Delegation budget caps
# ═══════════════════════════════════════════════════════════════════


class TestDelegationBudgetCaps:
    """delegation_budget_cap() per profile."""

    def test_reactive_no_delegation(self):
        from app.core.tools.delegation_tool import delegation_budget_cap
        caps = delegation_budget_cap("reactive")
        assert caps["max_delegations"] == 0

    def test_balanced_limits(self):
        from app.core.tools.delegation_tool import delegation_budget_cap
        caps = delegation_budget_cap("balanced")
        assert caps["max_delegations"] == 1
        assert caps["max_tokens_per"] == 800

    def test_pro_limits(self):
        from app.core.tools.delegation_tool import delegation_budget_cap
        caps = delegation_budget_cap("pro")
        assert caps["max_delegations"] == 2
        assert caps["max_tokens_per"] == 1200

    def test_exec_same_as_pro(self):
        from app.core.tools.delegation_tool import delegation_budget_cap
        assert delegation_budget_cap("exec") == delegation_budget_cap("pro")

    def test_unknown_profile(self):
        from app.core.tools.delegation_tool import delegation_budget_cap
        caps = delegation_budget_cap("unknown")
        assert caps["max_delegations"] == 0


# ═══════════════════════════════════════════════════════════════════
#  Delegation tool schema & registration
# ═══════════════════════════════════════════════════════════════════


class TestDelegateSchema:
    """DELEGATE_SCHEMA structure."""

    def test_schema_type(self):
        from app.core.tools.delegation_tool import DELEGATE_SCHEMA
        assert DELEGATE_SCHEMA["type"] == "function"

    def test_schema_name(self):
        from app.core.tools.delegation_tool import DELEGATE_SCHEMA
        assert DELEGATE_SCHEMA["function"]["name"] == "delegate_to_assistant"

    def test_schema_required_params(self):
        from app.core.tools.delegation_tool import DELEGATE_SCHEMA
        required = DELEGATE_SCHEMA["function"]["parameters"]["required"]
        assert "target_assistant_id" in required
        assert "query" in required

    def test_schema_optional_params(self):
        from app.core.tools.delegation_tool import DELEGATE_SCHEMA
        props = DELEGATE_SCHEMA["function"]["parameters"]["properties"]
        assert "context" in props
        assert "expected_output" in props


class TestDelegateRegistration:
    """register_delegation_tool() sets correct attributes."""

    def test_registration(self):
        # Use a fresh registry to test registration
        import app.core.tools.delegation_tool as mod
        from app.core.tool_registry import ToolCategory, ToolRegistry
        from app.core.tools.delegation_tool import (
            handle_delegate_to_assistant,
            register_delegation_tool,
        )
        original = mod.tool_registry
        test_reg = ToolRegistry()
        mod.tool_registry = test_reg
        try:
            register_delegation_tool()
            defn = test_reg.get("delegate_to_assistant")
            assert defn is not None
            assert defn.category == ToolCategory.DELEGATION
            assert defn.continues_loop is True
            assert defn.min_profile == "balanced"
            assert defn.timeout_seconds == 60
            assert test_reg.get_handler("delegate_to_assistant") is handle_delegate_to_assistant
        finally:
            mod.tool_registry = original


# ═══════════════════════════════════════════════════════════════════
#  Executor: _build_handler_kwargs for DELEGATION
# ═══════════════════════════════════════════════════════════════════


class TestExecutorDelegation:
    """_build_handler_kwargs dispatches DELEGATION correctly."""

    def test_build_kwargs_delegation(self):
        from app.core.tool_registry import ToolCategory, ToolDefinition
        from app.core.tools.executor import _build_handler_kwargs

        defn = ToolDefinition(
            name="delegate_to_assistant",
            category=ToolCategory.DELEGATION,
            description="test",
            openai_schema={},
        )
        tid = uuid4()
        aid = uuid4()
        bm = BudgetManager(total=10000)

        kwargs = _build_handler_kwargs(
            definition=defn,
            arguments={"target_assistant_id": "abc", "query": "hello"},
            tenant_id=tid,
            assistant_id=aid,
            conversation_id=None,
            collection_ids=None,
            citations=None,
            budget=bm,
            profile="pro",
        )

        assert kwargs["args"] == {"target_assistant_id": "abc", "query": "hello"}
        assert kwargs["tenant_id"] == tid
        assert kwargs["assistant_id"] == aid
        assert kwargs["budget"] is bm
        assert kwargs["profile"] == "pro"


# ═══════════════════════════════════════════════════════════════════
#  Delegation handler
# ═══════════════════════════════════════════════════════════════════

_TID = UUID("00000000-0000-0000-0000-000000000001")
_AID = UUID("00000000-0000-0000-0000-000000000002")
_TARGET = UUID("00000000-0000-0000-0000-000000000003")


def _fake_chunk(*, chunk_id="c1", doc_id="d1", filename="f.pdf", page=1, score=0.8):
    return SimpleNamespace(
        chunk_id=chunk_id,
        document_id=doc_id,
        document_filename=filename,
        page_number=page,
        content="Lorem ipsum dolor sit amet " * 20,
        score=score,
    )


def _fake_collection(cid=None):
    return SimpleNamespace(id=cid or uuid4())


def _fake_assistant(*, name="Legal", collections=None):
    a = SimpleNamespace(name=name, collections=collections or [_fake_collection()])
    return a


def _llm_response(text="Voici la réponse.", total_tokens=200):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(total_tokens=total_tokens),
    )


class TestDelegationHandler:
    """handle_delegate_to_assistant with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_missing_args(self):
        from app.core.tools.delegation_tool import handle_delegate_to_assistant
        result = await handle_delegate_to_assistant(
            args={}, tenant_id=_TID, profile="balanced",
        )
        assert "error" in result
        assert result["answer_text"] == ""

    @pytest.mark.asyncio
    async def test_invalid_uuid(self):
        from app.core.tools.delegation_tool import handle_delegate_to_assistant
        result = await handle_delegate_to_assistant(
            args={"target_assistant_id": "not-a-uuid", "query": "test"},
            tenant_id=_TID, profile="balanced",
        )
        assert "error" in result
        assert "Invalid assistant ID" in result["error"]

    @pytest.mark.asyncio
    async def test_reactive_profile_blocked(self):
        from app.core.tools.delegation_tool import handle_delegate_to_assistant
        result = await handle_delegate_to_assistant(
            args={"target_assistant_id": str(_TARGET), "query": "test"},
            tenant_id=_TID, profile="reactive",
        )
        assert "error" in result
        assert "does not support delegation" in result["error"]

    @pytest.mark.asyncio
    async def test_target_not_found(self):
        from app.core.tools.delegation_tool import handle_delegate_to_assistant

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await handle_delegate_to_assistant(
            args={"target_assistant_id": str(_TARGET), "query": "test"},
            tenant_id=_TID, profile="balanced", db=mock_session,
        )
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_no_collections(self):
        from app.core.tools.delegation_tool import handle_delegate_to_assistant

        mock_session = AsyncMock()
        mock_result = MagicMock()
        target = _fake_assistant(collections=[])
        mock_result.scalar_one_or_none.return_value = target
        mock_session.execute.return_value = mock_result

        with patch("app.services.retrieval.retrieval_service") as mock_rs:
            mock_rs.retrieve = AsyncMock(return_value=[])
            result = await handle_delegate_to_assistant(
                args={"target_assistant_id": str(_TARGET), "query": "test"},
                tenant_id=_TID, profile="balanced", db=mock_session,
            )
        # Empty collections → handler returns error or empty delegation
        assert result["citations"] == []
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_no_chunks_found(self):
        from app.core.tools.delegation_tool import handle_delegate_to_assistant

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = _fake_assistant()
        mock_session.execute.return_value = mock_result

        with patch("app.services.retrieval.retrieval_service") as mock_rs:
            mock_rs.retrieve = AsyncMock(return_value=[])
            result = await handle_delegate_to_assistant(
                args={"target_assistant_id": str(_TARGET), "query": "test"},
                tenant_id=_TID, profile="balanced", db=mock_session,
            )

        assert result["answer_text"] == "Aucune information pertinente trouvée dans les documents de cet assistant."
        assert result["citations"] == []
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_successful_delegation(self):
        from app.core.tools.delegation_tool import handle_delegate_to_assistant

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = _fake_assistant(name="Finance")
        mock_session.execute.return_value = mock_result

        chunks = [_fake_chunk(chunk_id="c1"), _fake_chunk(chunk_id="c2", score=0.6)]

        with (
            patch("app.services.retrieval.retrieval_service") as mock_rs,
            patch("openai.AsyncOpenAI") as mock_oai_cls,
        ):
            mock_rs.retrieve = AsyncMock(return_value=chunks)
            mock_rs.build_context = MagicMock(return_value="context text")

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=_llm_response("La réponse synthétisée.", 150)
            )
            mock_oai_cls.return_value = mock_client

            result = await handle_delegate_to_assistant(
                args={
                    "target_assistant_id": str(_TARGET),
                    "query": "Quel est le budget ?",
                    "context": "Projet Alpha",
                    "expected_output": "Un résumé",
                },
                tenant_id=_TID, profile="pro", db=mock_session,
            )

        assert result["target_assistant_name"] == "Finance"
        assert result["answer_text"] == "La réponse synthétisée."
        assert len(result["citations"]) == 2
        assert result["citations"][0]["source_assistant_id"] == str(_TARGET)
        assert result["confidence"] == 0.8  # first chunk's score
        assert result["tokens_used"] == 150

    @pytest.mark.asyncio
    async def test_budget_reservation_and_release(self):
        from app.core.tools.delegation_tool import handle_delegate_to_assistant

        budget = BudgetManager(total=5000)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = _fake_assistant()
        mock_session.execute.return_value = mock_result

        with (
            patch("app.services.retrieval.retrieval_service") as mock_rs,
            patch("openai.AsyncOpenAI") as mock_oai_cls,
        ):
            mock_rs.retrieve = AsyncMock(return_value=[_fake_chunk()])
            mock_rs.build_context = MagicMock(return_value="ctx")
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=_llm_response("ok", 300)
            )
            mock_oai_cls.return_value = mock_client

            result = await handle_delegate_to_assistant(
                args={"target_assistant_id": str(_TARGET), "query": "test"},
                tenant_id=_TID, profile="balanced", budget=budget, db=mock_session,
            )

        # Budget should have consumed 300 tokens (from reservation release)
        assert budget.consumed == 300
        # No active reservations
        assert len(budget._reservations) == 0
        assert "error" not in result


# ═══════════════════════════════════════════════════════════════════
#  Agent loop: delegation result handling
# ═══════════════════════════════════════════════════════════════════


class TestAgentLoopDelegation:
    """Agent loop handles delegation results correctly."""

    @pytest.mark.asyncio
    async def test_delegation_result_merges_citations(self):
        """When a delegation tool returns, its citations are merged into all_citations."""
        from app.core.agent_loop import AgentContext, run_agent_loop
        from app.core.tool_registry import ToolCategory

        ctx = AgentContext(
            tenant_id=_TID,
            assistant_id=_AID,
            conversation_id=uuid4(),
            message="Délègue la question au juridique",
            system_prompt="Tu es un assistant.",
            profile="balanced",
        )

        # Build a fake LLM stream that emits one delegation tool call, then a final answer
        delegation_result_dict = {
            "target_assistant_id": str(_TARGET),
            "target_assistant_name": "Juridique",
            "answer_text": "Les clauses sont conformes.",
            "citations": [
                {
                    "chunk_id": "legal_c1",
                    "document_id": "legal_d1",
                    "document_filename": "contrat.pdf",
                    "page_number": 5,
                    "excerpt": "Article 12...",
                    "score": 0.9,
                    "source_assistant_id": str(_TARGET),
                },
            ],
            "confidence": 0.9,
            "tokens_used": 200,
        }

        # Mock tool_registry to have delegation tool
        mock_defn = MagicMock()
        mock_defn.category = ToolCategory.DELEGATION
        mock_defn.continues_loop = True

        # We'll capture events
        events = []

        # Mock the full streaming flow
        # Round 1: LLM returns tool call → execute → delegation result
        # Round 2: LLM returns text answer (no tool calls)

        call_count = 0

        async def fake_stream_factory(**kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First round: tool call
                chunks = [
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(
                            content=None,
                            tool_calls=[SimpleNamespace(
                                index=0,
                                id="call_1",
                                function=SimpleNamespace(
                                    name="delegate_to_assistant",
                                    arguments=json.dumps({
                                        "target_assistant_id": str(_TARGET),
                                        "query": "conformité contrat",
                                    }),
                                ),
                            )],
                        ))],
                        usage=None,
                    ),
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(
                            content=None, tool_calls=None,
                        ))],
                        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50),
                    ),
                ]
            else:
                # Second round: text answer
                chunks = [
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(
                            content="D'après l'assistant juridique, ",
                            tool_calls=None,
                        ))],
                        usage=None,
                    ),
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(
                            content="les clauses sont conformes.",
                            tool_calls=None,
                        ))],
                        usage=SimpleNamespace(prompt_tokens=200, completion_tokens=30),
                    ),
                ]

            async def gen():
                for c in chunks:
                    yield c

            return gen()

        from app.core.tools.executor import ToolExecutionResult

        mock_exec_result = ToolExecutionResult(
            tool_name="delegate_to_assistant",
            category=ToolCategory.DELEGATION,
            result=delegation_result_dict,
        )

        with (
            patch("app.core.agent_loop.tool_registry") as mock_tr,
            patch("app.core.agent_loop.AsyncOpenAI") as mock_oai,
            patch("app.core.agent_loop.execute_tool_call", new_callable=AsyncMock) as mock_exec,
        ):
            mock_tr.get_openai_schemas.return_value = [{"type": "function"}]
            mock_tr.get.return_value = mock_defn

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=fake_stream_factory)
            mock_oai.return_value = mock_client

            mock_exec.return_value = mock_exec_result

            async for event in run_agent_loop(ctx):
                events.append(event)

        # Check we got citations event
        citation_events = [e for e in events if e.event == "citations"]
        assert len(citation_events) >= 1
        cit_data = citation_events[0].data
        assert any(c["chunk_id"] == "legal_c1" for c in cit_data)

        # Check done event
        done_events = [e for e in events if e.event == "done"]
        assert len(done_events) == 1

        # Check token events (text from round 2)
        token_events = [e for e in events if e.event == "token"]
        text = "".join(e.data for e in token_events)
        assert "les clauses sont conformes" in text


# ═══════════════════════════════════════════════════════════════════
#  ToolCategory.DELEGATION exists
# ═══════════════════════════════════════════════════════════════════


class TestToolCategoryDelegation:
    """DELEGATION is a valid ToolCategory."""

    def test_delegation_in_enum(self):
        from app.core.tool_registry import ToolCategory
        assert ToolCategory.DELEGATION == "delegation"

    def test_delegation_category_filtering(self):
        from app.core.tool_registry import ToolCategory, ToolDefinition, ToolRegistry

        reg = ToolRegistry()
        reg.register(ToolDefinition(
            name="test_deleg",
            category=ToolCategory.DELEGATION,
            description="test",
            openai_schema={},
        ))
        assert len(reg.by_category(ToolCategory.DELEGATION)) == 1
        assert len(reg.by_category(ToolCategory.BLOCK)) == 0
