"""Add durable real-time memory deltas.

Revision ID: 20260718_0005
Revises: 20260718_0004
Create Date: 2026-07-18 22:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0005"
down_revision: str | None = "20260718_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_delta",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("revision_id", sa.String(length=36), nullable=False),
        sa.Column("source_turn_id", sa.String(length=36), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("normalized_content", sa.Text(), nullable=False),
        sa.Column("delta_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("consumed_by_job_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id"),
    )
    op.create_index("ix_memory_delta_source_turn_id", "memory_delta", ["source_turn_id"])
    op.create_index("ix_memory_delta_normalized_content", "memory_delta", ["normalized_content"])
    op.create_index("ix_memory_delta_status", "memory_delta", ["status"])


def downgrade() -> None:
    op.drop_index("ix_memory_delta_status", table_name="memory_delta")
    op.drop_index("ix_memory_delta_normalized_content", table_name="memory_delta")
    op.drop_index("ix_memory_delta_source_turn_id", table_name="memory_delta")
    op.drop_table("memory_delta")
