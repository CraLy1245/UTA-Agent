"""set desktop-ready OpenAI-compatible defaults

Revision ID: 20260719_0008
Revises: 20260718_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0008"
down_revision: str | None = "20260718_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Preserve user customization: only replace the original built-in defaults.
    op.execute(
        sa.text(
            """UPDATE model_settings
               SET base_url = :new_base, model = :new_model
               WHERE base_url = :old_base AND model = :old_model"""
        ).bindparams(
            new_base="https://api.a6api.com/v1",
            new_model="gpt-5.6-sol",
            old_base="https://api.openai.com/v1",
            old_model="gpt-5.6",
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """UPDATE model_settings
               SET base_url = :old_base, model = :old_model
               WHERE base_url = :new_base AND model = :new_model"""
        ).bindparams(
            old_base="https://api.openai.com/v1",
            old_model="gpt-5.6",
            new_base="https://api.a6api.com/v1",
            new_model="gpt-5.6-sol",
        )
    )
