"""Agent runtime foundations: memory, runs, observability.

Revision ID: 018
Revises: 017
Create Date: 2026-02-20

PR1 tables:
- user_memories: cold memory per user (compressed bullets)
- assistant_memories: cold memory per assistant (compressed bullets)
- conversation_contexts: hot memory per conversation (summary + structured fields)
- agent_runs: execution tracking with budget and status lifecycle
- audit_logs: immutable event log for agent actions
- llm_traces: per-call LLM telemetry
- assistants.agent_profile column: reactive/balanced/pro/exec
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- agent_profile on assistants ---
    op.add_column(
        "assistants",
        sa.Column("agent_profile", sa.String(20), nullable=False, server_default="reactive"),
    )

    # --- user_memories ---
    op.create_table(
        "user_memories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("compressed_text", sa.Text(), nullable=True),
        sa.Column("compressed_token_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_user_memories_tenant_id", "user_memories", ["tenant_id"])
    op.create_unique_constraint("uq_user_memory_tenant_user", "user_memories", ["tenant_id", "user_id"])

    # --- assistant_memories ---
    op.create_table(
        "assistant_memories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assistant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("compressed_text", sa.Text(), nullable=True),
        sa.Column("compressed_token_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_assistant_memories_tenant_id", "assistant_memories", ["tenant_id"])
    op.create_index("ix_assistant_memories_assistant_id", "assistant_memories", ["assistant_id"])
    op.create_unique_constraint(
        "uq_assistant_memory_tenant_assistant", "assistant_memories", ["tenant_id", "assistant_id"],
    )

    # --- conversation_contexts ---
    op.create_table(
        "conversation_contexts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "assistant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("constraints", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("decisions", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("open_questions", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("facts", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_conversation_contexts_tenant_id", "conversation_contexts", ["tenant_id"])
    op.create_index("ix_conversation_contexts_conversation_id", "conversation_contexts", ["conversation_id"])
    op.create_index("ix_conversation_contexts_assistant_id", "conversation_contexts", ["assistant_id"])
    op.create_unique_constraint(
        "uq_conv_ctx_tenant_conversation", "conversation_contexts", ["tenant_id", "conversation_id"],
    )

    # --- agent_runs ---
    op.create_table(
        "agent_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assistant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile", sa.String(20), nullable=False, server_default="reactive"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("tool_rounds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("budget_tokens", sa.Integer(), nullable=True),
        sa.Column("budget_tokens_remaining", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_runs_tenant_id", "agent_runs", ["tenant_id"])
    op.create_index("ix_agent_runs_assistant_id", "agent_runs", ["assistant_id"])
    op.create_index("ix_agent_runs_conversation_id", "agent_runs", ["conversation_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("level", sa.String(10), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_run_id", "audit_logs", ["run_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # --- llm_traces ---
    op.create_table(
        "llm_traces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_llm_traces_tenant_id", "llm_traces", ["tenant_id"])
    op.create_index("ix_llm_traces_run_id", "llm_traces", ["run_id"])
    op.create_index("ix_llm_traces_created_at", "llm_traces", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_traces_created_at", table_name="llm_traces")
    op.drop_index("ix_llm_traces_run_id", table_name="llm_traces")
    op.drop_index("ix_llm_traces_tenant_id", table_name="llm_traces")
    op.drop_table("llm_traces")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_run_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_conversation_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_assistant_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_tenant_id", table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_unique_constraint("uq_conv_ctx_tenant_conversation", table_name="conversation_contexts")
    op.drop_index("ix_conversation_contexts_assistant_id", table_name="conversation_contexts")
    op.drop_index("ix_conversation_contexts_conversation_id", table_name="conversation_contexts")
    op.drop_index("ix_conversation_contexts_tenant_id", table_name="conversation_contexts")
    op.drop_table("conversation_contexts")

    op.drop_unique_constraint("uq_assistant_memory_tenant_assistant", table_name="assistant_memories")
    op.drop_index("ix_assistant_memories_assistant_id", table_name="assistant_memories")
    op.drop_index("ix_assistant_memories_tenant_id", table_name="assistant_memories")
    op.drop_table("assistant_memories")

    op.drop_unique_constraint("uq_user_memory_tenant_user", table_name="user_memories")
    op.drop_index("ix_user_memories_tenant_id", table_name="user_memories")
    op.drop_table("user_memories")

    op.drop_column("assistants", "agent_profile")
