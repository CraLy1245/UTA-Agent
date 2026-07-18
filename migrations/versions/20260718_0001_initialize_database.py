"""Initialize database metadata.

Revision ID: 20260718_0001
Revises:
Create Date: 2026-07-18 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_metadata",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(
        sa.text("INSERT INTO app_metadata (key, value) VALUES (:key, :value)").bindparams(
            key="schema_version", value="20260718_0001"
        )
    )


def downgrade() -> None:
    op.drop_table("app_metadata")
