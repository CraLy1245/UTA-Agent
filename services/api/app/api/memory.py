from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.app.db.models import MemoryDelta
from services.api.app.db.session import get_db
from services.api.app.schemas.memory import MemoryDeltaRead, MemoryStatusRead
from services.memory.realtime_delta import REALTIME_DELTA_CHAR_LIMIT

router = APIRouter(prefix="/memory", tags=["memory"])
SessionDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[MemoryDeltaRead])
def list_memory_delta(
    db: SessionDep,
    status: Literal[
        "pending", "deferred_capacity", "duplicate_merged", "consumed"
    ]
    | None = None,
    query: str | None = Query(default=None, max_length=200),
) -> list[MemoryDelta]:
    statement = select(MemoryDelta)
    if status is not None:
        statement = statement.where(MemoryDelta.status == status)
    if query and query.strip():
        statement = statement.where(MemoryDelta.raw_content.contains(query.strip()))
    return list(
        db.scalars(
            statement.order_by(MemoryDelta.created_at.desc(), MemoryDelta.id.desc())
        )
    )


@router.get("/status", response_model=MemoryStatusRead)
def get_memory_status(db: SessionDep) -> MemoryStatusRead:
    active_chars = int(
        db.scalar(
            select(func.coalesce(func.sum(MemoryDelta.char_count), 0)).where(
                MemoryDelta.status == "pending"
            )
        )
        or 0
    )
    deferred_chars = int(
        db.scalar(
            select(func.coalesce(func.sum(MemoryDelta.char_count), 0)).where(
                MemoryDelta.status == "deferred_capacity"
            )
        )
        or 0
    )
    pending_count = int(
        db.scalar(
            select(func.count()).select_from(MemoryDelta).where(
                MemoryDelta.status == "pending"
            )
        )
        or 0
    )
    deferred_count = int(
        db.scalar(
            select(func.count()).select_from(MemoryDelta).where(
                MemoryDelta.status == "deferred_capacity"
            )
        )
        or 0
    )
    return MemoryStatusRead(
        active_delta_char_count=active_chars,
        delta_char_limit=REALTIME_DELTA_CHAR_LIMIT,
        deferred_delta_char_count=deferred_chars,
        pending_count=pending_count,
        deferred_count=deferred_count,
        formal_memory_char_count=0,
        formal_memory_char_limit=18_000,
        current_memory_version=None,
    )
