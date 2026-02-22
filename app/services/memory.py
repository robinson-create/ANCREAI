"""Memory service — CRUD and compression for user/assistant/conversation memory."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_memory import AssistantMemory
from app.models.conversation_context import ConversationContext
from app.models.user_memory import UserMemory


class MemoryService:
    """Manages cold memory (user/assistant) and hot memory (conversation context).

    Cold memory is stable across conversations and injected into system prompt.
    Hot memory is per-conversation and updated every N interactions.
    """

    # ── User Memory ──────────────────────────────────────────────

    async def get_user_memory(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
    ) -> UserMemory | None:
        result = await db.execute(
            select(UserMemory)
            .where(UserMemory.tenant_id == tenant_id)
            .where(UserMemory.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert_user_memory(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        raw_json: dict,
    ) -> UserMemory:
        """Create or update user memory (upsert on unique constraint)."""
        stmt = (
            pg_insert(UserMemory)
            .values(tenant_id=tenant_id, user_id=user_id, raw_json=raw_json)
            .on_conflict_do_update(
                constraint="uq_user_memory_tenant_user",
                set_={"raw_json": raw_json},
            )
            .returning(UserMemory)
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    async def update_user_memory_compression(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        compressed_text: str,
        token_count: int,
    ) -> None:
        """Update the compressed text cache for a user memory."""
        mem = await self.get_user_memory(db, tenant_id, user_id)
        if mem:
            mem.compressed_text = compressed_text
            mem.compressed_token_count = token_count

    # ── Assistant Memory ─────────────────────────────────────────

    async def get_assistant_memory(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        assistant_id: UUID,
    ) -> AssistantMemory | None:
        result = await db.execute(
            select(AssistantMemory)
            .where(AssistantMemory.tenant_id == tenant_id)
            .where(AssistantMemory.assistant_id == assistant_id)
        )
        return result.scalar_one_or_none()

    async def upsert_assistant_memory(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        assistant_id: UUID,
        raw_json: dict,
    ) -> AssistantMemory:
        """Create or update assistant memory (upsert on unique constraint)."""
        stmt = (
            pg_insert(AssistantMemory)
            .values(tenant_id=tenant_id, assistant_id=assistant_id, raw_json=raw_json)
            .on_conflict_do_update(
                constraint="uq_assistant_memory_tenant_assistant",
                set_={"raw_json": raw_json},
            )
            .returning(AssistantMemory)
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    async def update_assistant_memory_compression(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        assistant_id: UUID,
        compressed_text: str,
        token_count: int,
    ) -> None:
        """Update the compressed text cache for an assistant memory."""
        mem = await self.get_assistant_memory(db, tenant_id, assistant_id)
        if mem:
            mem.compressed_text = compressed_text
            mem.compressed_token_count = token_count

    # ── Conversation Context (hot memory) ────────────────────────

    async def get_conversation_context(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        conversation_id: UUID,
    ) -> ConversationContext | None:
        result = await db.execute(
            select(ConversationContext)
            .where(ConversationContext.tenant_id == tenant_id)
            .where(ConversationContext.conversation_id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_conversation_context(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        conversation_id: UUID,
        assistant_id: UUID,
    ) -> ConversationContext:
        """Get or create conversation context (upsert)."""
        ctx = await self.get_conversation_context(db, tenant_id, conversation_id)
        if ctx:
            return ctx

        stmt = (
            pg_insert(ConversationContext)
            .values(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                assistant_id=assistant_id,
            )
            .on_conflict_do_nothing(constraint="uq_conv_ctx_tenant_conversation")
            .returning(ConversationContext)
        )
        result = await db.execute(stmt)
        ctx = result.scalar_one_or_none()

        if not ctx:
            ctx = await self.get_conversation_context(db, tenant_id, conversation_id)

        return ctx  # type: ignore[return-value]

    async def update_conversation_context(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        conversation_id: UUID,
        *,
        summary_text: str | None = None,
        constraints: list | None = None,
        decisions: list | None = None,
        open_questions: list | None = None,
        facts: list | None = None,
        increment_message_count: bool = False,
    ) -> ConversationContext | None:
        """Partial update of conversation context fields."""
        ctx = await self.get_conversation_context(db, tenant_id, conversation_id)
        if not ctx:
            return None

        if summary_text is not None:
            ctx.summary_text = summary_text
        if constraints is not None:
            ctx.constraints = constraints
        if decisions is not None:
            ctx.decisions = decisions
        if open_questions is not None:
            ctx.open_questions = open_questions
        if facts is not None:
            ctx.facts = facts
        if increment_message_count:
            ctx.message_count += 1

        return ctx

    async def increment_message_count(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        conversation_id: UUID,
    ) -> int:
        """Increment message count and return new value."""
        ctx = await self.get_conversation_context(db, tenant_id, conversation_id)
        if not ctx:
            return 0
        ctx.message_count += 1
        return ctx.message_count

    # ── Context assembly (for system prompt injection) ───────────

    async def assemble_memory_context(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        assistant_id: UUID,
        conversation_id: UUID,
    ) -> dict:
        """Assemble all memory layers for prompt injection.

        Returns dict with keys: assistant_memory, user_memory, conversation_context.
        Each value is the compressed/summary text or None.
        """
        assistant_mem = await self.get_assistant_memory(db, tenant_id, assistant_id)
        user_mem = await self.get_user_memory(db, tenant_id, user_id)
        conv_ctx = await self.get_conversation_context(db, tenant_id, conversation_id)

        result: dict = {
            "assistant_memory": assistant_mem.compressed_text if assistant_mem else None,
            "user_memory": user_mem.compressed_text if user_mem else None,
            "conversation_summary": conv_ctx.summary_text if conv_ctx else None,
            "constraints": (conv_ctx.constraints or []) if conv_ctx else [],
            "decisions": (conv_ctx.decisions or []) if conv_ctx else [],
            "open_questions": (conv_ctx.open_questions or []) if conv_ctx else [],
            "facts": (conv_ctx.facts or []) if conv_ctx else [],
        }
        return result


# Singleton
memory_service = MemoryService()
