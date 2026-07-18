"""Add the token survival ledger, feedback events, and execution traces.

Revision ID: 20260718_0004
Revises: 20260718_0003
Create Date: 2026-07-18 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0004"
down_revision: str | None = "20260718_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READ_ACCOUNT_ID = "00000000-0000-4000-8000-000000000004"
OUTPUT_ACCOUNT_ID = "00000000-0000-4000-8000-000000000005"


def upgrade() -> None:
    token_accounts = op.create_table(
        "token_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("balance_units", sa.BigInteger(), nullable=False),
        sa.Column("initial_balance_units", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_type"),
    )
    op.bulk_insert(
        token_accounts,
        [
            {
                "id": READ_ACCOUNT_ID,
                "account_type": "read",
                "balance_units": 100_000_000_000,
                "initial_balance_units": 100_000_000_000,
            },
            {
                "id": OUTPUT_ACCOUNT_ID,
                "account_type": "output",
                "balance_units": 10_000_000_000,
                "initial_balance_units": 10_000_000_000,
            },
        ],
    )
    op.create_table(
        "feedback_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("rating", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_events_turn_id", "feedback_events", ["turn_id"])
    op.create_table(
        "token_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=True),
        sa.Column("feedback_event_id", sa.String(length=36), nullable=True),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("amount_units", sa.BigInteger(), nullable=False),
        sa.Column("balance_before", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=250), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["feedback_event_id"], ["feedback_events.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_token_transactions_account_type", "token_transactions", ["account_type"]
    )
    op.create_index(
        "ix_token_transactions_feedback_event_id",
        "token_transactions",
        ["feedback_event_id"],
    )
    op.create_index(
        "ix_token_transactions_transaction_type",
        "token_transactions",
        ["transaction_type"],
    )
    op.create_index("ix_token_transactions_turn_id", "token_transactions", ["turn_id"])
    op.create_table(
        "turn_execution_traces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=36), nullable=False),
        sa.Column("model_id", sa.String(length=200), nullable=False),
        sa.Column("memory_revision_ids_json", sa.Text(), nullable=False),
        sa.Column("skill_revision_ids_json", sa.Text(), nullable=False),
        sa.Column("tool_names_json", sa.Text(), nullable=False),
        sa.Column("provider_raw_usage_json", sa.Text(), nullable=False),
        sa.Column("normalized_usage_json", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("latency_ms", sa.BigInteger(), nullable=False),
        sa.Column("completion_status", sa.String(length=32), nullable=False),
        sa.Column("objective_result_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("turn_id"),
    )
    op.create_index(
        "ix_turn_execution_traces_completion_status",
        "turn_execution_traces",
        ["completion_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_turn_execution_traces_completion_status",
        table_name="turn_execution_traces",
    )
    op.drop_table("turn_execution_traces")
    op.drop_index("ix_token_transactions_turn_id", table_name="token_transactions")
    op.drop_index(
        "ix_token_transactions_transaction_type", table_name="token_transactions"
    )
    op.drop_index(
        "ix_token_transactions_feedback_event_id", table_name="token_transactions"
    )
    op.drop_index("ix_token_transactions_account_type", table_name="token_transactions")
    op.drop_table("token_transactions")
    op.drop_index("ix_feedback_events_turn_id", table_name="feedback_events")
    op.drop_table("feedback_events")
    op.drop_table("token_accounts")
