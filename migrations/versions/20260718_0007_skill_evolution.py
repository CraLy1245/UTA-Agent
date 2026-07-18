"""Add durable, versioned Skill evolution and deterministic competition."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0007"
down_revision: str | None = "20260718_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("selection_weight", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("exploration_rate", sa.Float(), nullable=False),
        sa.Column("stable_revision_id", sa.String(36), nullable=False, unique=True),
        sa.Column("candidate_revision_id", sa.String(36), unique=True),
        sa.Column("rollback_revision_id", sa.String(36)),
        sa.Column("candidate_paused", sa.Boolean(), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("promotion_observation_remaining", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_skills_name", "skills", ["name"])
    op.create_index("ix_skills_status", "skills", ["status"])

    op.create_table(
        "skill_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "skill_id",
            sa.String(36),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_revision_id", sa.String(36)),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("expected_improvement", sa.Text()),
        sa.Column("source_turn_ids_json", sa.Text(), nullable=False),
        sa.Column("cognitive_job_id", sa.String(36)),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(250), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("promoted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_skill_revisions_skill_id", "skill_revisions", ["skill_id"])
    op.create_index("ix_skill_revisions_status", "skill_revisions", ["status"])
    op.create_index("ix_skill_revisions_cognitive_job_id", "skill_revisions", ["cognitive_job_id"])

    op.create_table(
        "skill_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "skill_id",
            sa.String(36),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "skill_revision_id",
            sa.String(36),
            sa.ForeignKey("skill_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "turn_id",
            sa.String(36),
            sa.ForeignKey("turns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("feedback", sa.String(20)),
        sa.Column("objective_passed", sa.Boolean()),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("turn_id", "skill_revision_id", name="uq_skill_usage_turn_revision"),
    )
    op.create_index("ix_skill_usage_skill_id", "skill_usage", ["skill_id"])
    op.create_index("ix_skill_usage_skill_revision_id", "skill_usage", ["skill_revision_id"])
    op.create_index("ix_skill_usage_turn_id", "skill_usage", ["turn_id"])

    op.create_table(
        "skill_evolution_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "skill_id",
            sa.String(36),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "revision_id",
            sa.String(36),
            sa.ForeignKey("skill_revisions.id", ondelete="SET NULL"),
        ),
        sa.Column("cognitive_job_id", sa.String(36)),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(250), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_skill_evolution_events_skill_id", "skill_evolution_events", ["skill_id"])
    op.create_index(
        "ix_skill_evolution_events_revision_id", "skill_evolution_events", ["revision_id"]
    )
    op.create_index(
        "ix_skill_evolution_events_cognitive_job_id",
        "skill_evolution_events",
        ["cognitive_job_id"],
    )
    op.create_index(
        "ix_skill_evolution_events_event_type", "skill_evolution_events", ["event_type"]
    )


def downgrade() -> None:
    op.drop_table("skill_evolution_events")
    op.drop_table("skill_usage")
    op.drop_table("skill_revisions")
    op.drop_table("skills")
