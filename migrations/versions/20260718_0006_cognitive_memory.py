"""Add durable cognitive consolidation and versioned formal memory."""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0006"
down_revision: str | None = "20260718_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("turns", sa.Column("completed_number", sa.Integer(), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id FROM turns WHERE status='completed' ORDER BY completed_at, created_at, id"
        )
    ).fetchall()
    for number, row in enumerate(rows, 1):
        connection.execute(
            sa.text("UPDATE turns SET completed_number=:n WHERE id=:id"),
            {"n": number, "id": row[0]},
        )
    with op.batch_alter_table("turns") as batch:
        batch.create_unique_constraint("uq_turns_completed_number", ["completed_number"])
        batch.create_index("ix_turns_completed_number", ["completed_number"])

    op.create_table(
        "cognitive_state",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("completed_turn_count", sa.Integer(), nullable=False),
        sa.Column("last_consolidated_turn", sa.Integer(), nullable=False),
        sa.Column("memory_version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    connection.execute(
        sa.text("INSERT INTO cognitive_state VALUES ('global', :count, 0, 0, CURRENT_TIMESTAMP)"),
        {"count": len(rows)},
    )
    op.create_table(
        "cognitive_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_type", sa.String(40), nullable=False),
        sa.Column("start_turn_number", sa.Integer(), nullable=False),
        sa.Column("end_turn_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("memory_version_before", sa.Integer(), nullable=False),
        sa.Column("memory_version_after", sa.Integer()),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("result_json", sa.Text()),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "job_type", "start_turn_number", "end_turn_number", name="uq_cognitive_job_range"
        ),
    )
    op.create_index("ix_cognitive_jobs_status", "cognitive_jobs", ["status"])
    op.create_table(
        "memory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("current_revision_id", sa.String(36), nullable=False, unique=True),
        sa.Column("char_count", sa.Integer(), nullable=False),
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
    op.create_index("ix_memory_items_category", "memory_items", ["category"])
    op.create_index("ix_memory_items_status", "memory_items", ["status"])
    op.create_table(
        "memory_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "memory_item_id",
            sa.String(36),
            sa.ForeignKey("memory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_revision_id", sa.String(36)),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("tags_json", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("source_turn_ids_json", sa.Text(), nullable=False),
        sa.Column("cognitive_job_id", sa.String(36)),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_memory_revisions_memory_item_id", "memory_revisions", ["memory_item_id"])
    op.create_index(
        "ix_memory_revisions_cognitive_job_id", "memory_revisions", ["cognitive_job_id"]
    )
    op.create_table(
        "memory_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("cognitive_job_id", sa.String(36), unique=True),
        sa.Column("revision_ids_json", sa.Text(), nullable=False),
        sa.Column("formal_char_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.execute(
        "CREATE VIRTUAL TABLE memory_items_fts USING fts5("
        "title, content, tags, content='memory_items', content_rowid='rowid')"
    )
    op.execute(
        "CREATE TRIGGER memory_items_ai AFTER INSERT ON memory_items BEGIN "
        "INSERT INTO memory_items_fts(rowid,title,content,tags) "
        "VALUES(new.rowid,new.title,new.content,new.tags_json); END"
    )
    op.execute(
        "CREATE TRIGGER memory_items_ad AFTER DELETE ON memory_items BEGIN "
        "INSERT INTO memory_items_fts(memory_items_fts,rowid,title,content,tags) "
        "VALUES('delete',old.rowid,old.title,old.content,old.tags_json); END"
    )
    op.execute(
        "CREATE TRIGGER memory_items_au AFTER UPDATE ON memory_items BEGIN "
        "INSERT INTO memory_items_fts(memory_items_fts,rowid,title,content,tags) "
        "VALUES('delete',old.rowid,old.title,old.content,old.tags_json); "
        "INSERT INTO memory_items_fts(rowid,title,content,tags) "
        "VALUES(new.rowid,new.title,new.content,new.tags_json); END"
    )
    if len(rows) >= 20:
        connection.execute(
            sa.text(
                "INSERT INTO cognitive_jobs "
                "(id,job_type,start_turn_number,end_turn_number,status,"
                "memory_version_before,attempt_count) "
                "VALUES (:id,'memory_consolidation',1,20,'pending',0,0)"
            ),
            {"id": str(uuid4())},
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS memory_items_au")
    op.execute("DROP TRIGGER IF EXISTS memory_items_ad")
    op.execute("DROP TRIGGER IF EXISTS memory_items_ai")
    op.execute("DROP TABLE IF EXISTS memory_items_fts")
    op.drop_table("memory_snapshots")
    op.drop_table("memory_revisions")
    op.drop_table("memory_items")
    op.drop_table("cognitive_jobs")
    op.drop_table("cognitive_state")
    op.drop_index("ix_turns_completed_number", table_name="turns")
    with op.batch_alter_table("turns") as batch:
        batch.drop_column("completed_number")
