"""Add durable tool execution records.

Revision ID: 20260718_0003
Revises: 20260718_0002
Create Date: 2026-07-18 20:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0003"
down_revision: str | None = "20260718_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("provider_call_id", sa.String(length=200), nullable=False),
        sa.Column("call_sequence", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("turn_id", "provider_call_id", name="uq_tool_execution_turn_call"),
    )
    op.create_index("ix_tool_executions_conversation_id", "tool_executions", ["conversation_id"])
    op.create_index("ix_tool_executions_turn_id", "tool_executions", ["turn_id"])
    op.create_index("ix_tool_executions_status", "tool_executions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tool_executions_status", table_name="tool_executions")
    op.drop_index("ix_tool_executions_turn_id", table_name="tool_executions")
    op.drop_index("ix_tool_executions_conversation_id", table_name="tool_executions")
    op.drop_table("tool_executions")
