"""Usage tracking and quota enforcement service."""

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.usage import Usage


class UsageService:
    """Service for tracking and enforcing usage quotas."""

    @staticmethod
    def get_current_period() -> date:
        """Get the first day of current month."""
        today = datetime.now(timezone.utc).date()
        return today.replace(day=1)

    async def get_or_create_usage(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        period: date | None = None,
    ) -> Usage:
        """Get or create usage record for tenant and period.

        Uses INSERT ... ON CONFLICT DO NOTHING to handle concurrent requests
        that try to create the same (tenant_id, period) record simultaneously.
        """
        period = period or self.get_current_period()

        result = await db.execute(
            select(Usage)
            .where(Usage.tenant_id == tenant_id)
            .where(Usage.period == period)
        )
        usage = result.scalar_one_or_none()

        if not usage:
            stmt = (
                pg_insert(Usage)
                .values(tenant_id=tenant_id, period=period)
                .on_conflict_do_nothing(constraint="uq_usage_tenant_period")
                .returning(Usage)
            )
            result = await db.execute(stmt)
            usage = result.scalar_one_or_none()

            if not usage:
                # Another transaction won the race — just SELECT it
                result = await db.execute(
                    select(Usage)
                    .where(Usage.tenant_id == tenant_id)
                    .where(Usage.period == period)
                )
                usage = result.scalar_one()

        return usage

    async def get_usage_summary(
        self,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> dict:
        """Get usage summary with limits and percentages."""
        # Get tenant limits
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise ValueError("Tenant not found")
        
        # Get current usage
        usage = await self.get_or_create_usage(db, tenant_id)
        
        chat_tokens_used = usage.chat_input_tokens + usage.chat_output_tokens
        
        return {
            "period": usage.period,
            "ingestion_tokens_used": usage.ingestion_tokens,
            "chat_tokens_used": chat_tokens_used,
            "storage_bytes_used": usage.storage_bytes,
            "transcription_seconds_used": usage.transcription_seconds,
            "max_ingestion_tokens": tenant.max_ingestion_tokens,
            "max_chat_tokens": tenant.max_chat_tokens,
            "max_storage_bytes": tenant.max_storage_bytes,
            "max_transcription_seconds": tenant.max_transcription_seconds,
            "ingestion_percent": (usage.ingestion_tokens / tenant.max_ingestion_tokens * 100)
                if tenant.max_ingestion_tokens > 0 else 0,
            "chat_percent": (chat_tokens_used / tenant.max_chat_tokens * 100)
                if tenant.max_chat_tokens > 0 else 0,
            "storage_percent": (usage.storage_bytes / tenant.max_storage_bytes * 100)
                if tenant.max_storage_bytes > 0 else 0,
            "transcription_percent": (usage.transcription_seconds / tenant.max_transcription_seconds * 100)
                if tenant.max_transcription_seconds > 0 else 0,
            "documents_count": usage.documents_count,
            "messages_count": usage.messages_count,
        }

    async def check_ingestion_quota(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        estimated_tokens: int = 0,
    ) -> tuple[bool, str | None]:
        """
        Check if tenant can ingest more documents.
        
        Returns:
            Tuple of (allowed, error_message)
        """
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            return False, "Tenant not found"
        
        usage = await self.get_or_create_usage(db, tenant_id)
        
        if usage.ingestion_tokens + estimated_tokens > tenant.max_ingestion_tokens:
            return False, f"Ingestion quota exceeded (used: {usage.ingestion_tokens}, limit: {tenant.max_ingestion_tokens})"
        
        return True, None

    async def check_chat_quota(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        estimated_tokens: int = 0,
    ) -> tuple[bool, str | None]:
        """
        Check if tenant can send more chat messages.
        
        Returns:
            Tuple of (allowed, error_message)
        """
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            return False, "Tenant not found"
        
        usage = await self.get_or_create_usage(db, tenant_id)
        current_chat = usage.chat_input_tokens + usage.chat_output_tokens
        
        if current_chat + estimated_tokens > tenant.max_chat_tokens:
            return False, f"Chat quota exceeded (used: {current_chat}, limit: {tenant.max_chat_tokens})"
        
        return True, None

    async def check_storage_quota(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        file_size: int = 0,
    ) -> tuple[bool, str | None]:
        """
        Check if tenant can store more files.
        
        Returns:
            Tuple of (allowed, error_message)
        """
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            return False, "Tenant not found"
        
        usage = await self.get_or_create_usage(db, tenant_id)
        
        if usage.storage_bytes + file_size > tenant.max_storage_bytes:
            return False, f"Storage quota exceeded (used: {usage.storage_bytes}, limit: {tenant.max_storage_bytes})"
        
        return True, None

    async def record_ingestion(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        tokens: int,
        file_size: int,
    ) -> None:
        """Record ingestion usage."""
        usage = await self.get_or_create_usage(db, tenant_id)
        usage.ingestion_tokens += tokens
        usage.storage_bytes += file_size
        usage.documents_count += 1

    async def record_chat(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record chat usage."""
        usage = await self.get_or_create_usage(db, tenant_id)
        usage.chat_input_tokens += input_tokens
        usage.chat_output_tokens += output_tokens
        usage.messages_count += 1

    async def check_transcription_quota(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        estimated_seconds: int = 0,
    ) -> tuple[bool, str | None]:
        """
        Check if tenant can transcribe more audio.

        Returns:
            Tuple of (allowed, error_message)
        """
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()

        if not tenant:
            return False, "Tenant not found"

        usage = await self.get_or_create_usage(db, tenant_id)

        if usage.transcription_seconds + estimated_seconds > tenant.max_transcription_seconds:
            return False, (
                f"Quota de transcription atteint "
                f"({usage.transcription_seconds}s/{tenant.max_transcription_seconds}s). "
                f"Passez en Pro pour plus de minutes."
            )

        return True, None

    async def record_transcription(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        seconds: int,
    ) -> None:
        """Record transcription usage."""
        usage = await self.get_or_create_usage(db, tenant_id)
        usage.transcription_seconds += seconds

    async def reduce_storage(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        file_size: int,
    ) -> None:
        """Reduce storage usage (when file is deleted)."""
        usage = await self.get_or_create_usage(db, tenant_id)
        usage.storage_bytes = max(0, usage.storage_bytes - file_size)
        usage.documents_count = max(0, usage.documents_count - 1)


# Singleton instance
usage_service = UsageService()
