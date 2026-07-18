from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app.core.config import get_settings
from services.api.app.core.security import redact_value
from services.api.app.db.models import (
    CognitiveJob,
    CognitiveState,
    Conversation,
    FeedbackEvent,
    MemoryDelta,
    MemoryItem,
    MemoryRevision,
    MemorySnapshot,
    Message,
    ModelSetting,
    Skill,
    SkillEvolutionEvent,
    SkillRevision,
    SkillUsage,
    TokenAccount,
    TokenTransaction,
    ToolExecution,
    Turn,
    TurnExecutionTrace,
)
from services.api.app.db.session import SessionLocal

router = APIRouter(prefix="/data", tags=["data"])

EXPORT_MODELS = (
    Conversation,
    Turn,
    Message,
    ToolExecution,
    FeedbackEvent,
    TokenAccount,
    TokenTransaction,
    TurnExecutionTrace,
    MemoryDelta,
    CognitiveState,
    MemoryItem,
    MemoryRevision,
    MemorySnapshot,
    CognitiveJob,
    Skill,
    SkillRevision,
    SkillUsage,
    SkillEvolutionEvent,
    ModelSetting,
)
EXCLUDED_COLUMNS = {"model_settings": {"api_key_env"}}


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return aware.astimezone(UTC).isoformat()
    return value


def _current_secret() -> tuple[str, ...]:
    secret = get_settings().openai_api_key
    if secret is None:
        return ()
    value = secret.get_secret_value()
    return (value,) if value else ()


def build_export(db: Session) -> dict[str, Any]:
    tables: dict[str, list[dict[str, Any]]] = {}
    secrets = _current_secret()
    for model in EXPORT_MODELS:
        table_name = model.__tablename__
        excluded = EXCLUDED_COLUMNS.get(table_name, set())
        rows: list[dict[str, Any]] = []
        for item in db.scalars(select(model)):
            row = {
                column.name: _json_value(getattr(item, column.name))
                for column in model.__table__.columns
                if column.name not in excluded
            }
            rows.append(redact_value(row, secrets=secrets))
        tables[table_name] = rows
    return {
        "format": "survival-agent-export",
        "format_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "database": "sqlite",
        "tables": tables,
    }


@router.get("/export")
def export_data() -> Response:
    # A read transaction gives every exported table one consistent WAL snapshot.
    with SessionLocal() as db:
        db.connection().exec_driver_sql("BEGIN")
        payload = build_export(db)
        db.rollback()
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="survival-agent-{stamp}.json"',
            "X-Content-Type-Options": "nosniff",
        },
    )
