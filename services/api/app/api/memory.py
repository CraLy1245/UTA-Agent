import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.app.db.models import CognitiveState, MemoryDelta, MemoryItem, MemoryRevision
from services.api.app.db.session import get_db
from services.api.app.schemas.memory import (
    MemoryDeltaRead,
    MemoryItemCreate,
    MemoryItemRead,
    MemoryItemUpdate,
    MemoryRevisionRead,
    MemoryStatusRead,
)
from services.memory.formal import (
    FORMAL_MEMORY_CHAR_LIMIT,
    create_revision,
    create_snapshot,
    formal_char_count,
)
from services.memory.realtime_delta import REALTIME_DELTA_CHAR_LIMIT

router = APIRouter(prefix="/memory", tags=["memory"])
SessionDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[MemoryDeltaRead])
def list_memory_delta(
    db: SessionDep,
    status: Literal["pending", "deferred_capacity", "duplicate_merged", "consumed"] | None = None,
    query: str | None = Query(default=None, max_length=200),
) -> list[MemoryDelta]:
    statement = select(MemoryDelta)
    if status is not None:
        statement = statement.where(MemoryDelta.status == status)
    if query and query.strip():
        statement = statement.where(MemoryDelta.raw_content.contains(query.strip()))
    return list(
        db.scalars(statement.order_by(MemoryDelta.created_at.desc(), MemoryDelta.id.desc()))
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
            select(func.count()).select_from(MemoryDelta).where(MemoryDelta.status == "pending")
        )
        or 0
    )
    deferred_count = int(
        db.scalar(
            select(func.count())
            .select_from(MemoryDelta)
            .where(MemoryDelta.status == "deferred_capacity")
        )
        or 0
    )
    return MemoryStatusRead(
        active_delta_char_count=active_chars,
        delta_char_limit=REALTIME_DELTA_CHAR_LIMIT,
        deferred_delta_char_count=deferred_chars,
        pending_count=pending_count,
        deferred_count=deferred_count,
        formal_memory_char_count=formal_char_count(db),
        formal_memory_char_limit=FORMAL_MEMORY_CHAR_LIMIT,
        current_memory_version=(
            db.get(CognitiveState, "global").memory_version
            if db.get(CognitiveState, "global")
            else 0
        ),
    )


@router.get("/items", response_model=list[MemoryItemRead])
def list_memory_items(
    db: SessionDep,
    status: str | None = None,
    category: str | None = None,
    query: str | None = Query(default=None, max_length=200),
) -> list[MemoryItem]:
    statement = select(MemoryItem)
    if status:
        statement = statement.where(MemoryItem.status == status)
    if category:
        statement = statement.where(MemoryItem.category == category)
    if query and query.strip():
        statement = statement.where(
            MemoryItem.title.contains(query.strip()) | MemoryItem.content.contains(query.strip())
        )
    return list(
        db.scalars(
            statement.order_by(
                MemoryItem.locked.desc(), MemoryItem.priority.desc(), MemoryItem.updated_at.desc()
            )
        )
    )


def _item(db: Session, item_id: str) -> MemoryItem:
    item = db.get(MemoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Memory item not found")
    return item


def _snapshot_manual(db: Session) -> None:
    state = db.get(CognitiveState, "global")
    if state is None:
        state = CognitiveState(
            id="global", completed_turn_count=0, last_consolidated_turn=0, memory_version=0
        )
        db.add(state)
        db.flush()
    state.memory_version += 1
    create_snapshot(db, version=state.memory_version, job_id=None)


@router.post("/items", response_model=MemoryItemRead, status_code=201)
def create_memory_item(payload: MemoryItemCreate, db: SessionDep) -> MemoryItem:
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    if formal_char_count(db) + len(payload.content) > FORMAL_MEMORY_CHAR_LIMIT:
        raise HTTPException(status_code=409, detail="Formal memory would exceed 18000 characters")
    revision_id = str(uuid4())
    now = datetime.now(UTC)
    item = MemoryItem(
        id=str(uuid4()),
        category=payload.category,
        title=payload.title,
        content=payload.content,
        tags_json=json.dumps(payload.tags),
        priority=payload.priority,
        status="active",
        locked=False,
        current_revision_id=revision_id,
        char_count=len(payload.content),
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.flush()
    db.add(
        MemoryRevision(
            id=revision_id,
            memory_item_id=item.id,
            previous_revision_id=None,
            operation="manual_add",
            title=item.title,
            content=item.content,
            category=item.category,
            tags_json=item.tags_json,
            priority=item.priority,
            status=item.status,
            locked=item.locked,
            source_turn_ids_json="[]",
            created_by="user",
            reason="Manual memory creation",
        )
    )
    _snapshot_manual(db)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=MemoryItemRead)
def update_memory_item(item_id: str, payload: MemoryItemUpdate, db: SessionDep) -> MemoryItem:
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    item = _item(db, item_id)
    if item.current_revision_id != payload.expected_revision_id:
        raise HTTPException(status_code=409, detail="Memory revision conflict")
    projected = (
        formal_char_count(db)
        - (item.char_count if item.status == "active" else 0)
        + len(payload.content or item.content)
    )
    if projected > FORMAL_MEMORY_CHAR_LIMIT:
        raise HTTPException(status_code=409, detail="Formal memory would exceed 18000 characters")
    for name in ("title", "content", "category", "priority"):
        value = getattr(payload, name)
        if value is not None:
            setattr(item, name, value)
    if payload.tags is not None:
        item.tags_json = json.dumps(payload.tags)
    create_revision(
        db,
        item,
        operation="manual_update",
        source_turn_ids=[],
        created_by="user",
        reason="Manual edit",
    )
    _snapshot_manual(db)
    db.commit()
    db.refresh(item)
    return item


def _state_change(
    item_id: str,
    operation: str,
    db: Session,
    *,
    locked: bool | None = None,
    status: str | None = None,
) -> MemoryItem:
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    item = _item(db, item_id)
    if (
        status == "active"
        and item.status != "active"
        and formal_char_count(db) + item.char_count > FORMAL_MEMORY_CHAR_LIMIT
    ):
        raise HTTPException(
            status_code=409, detail="Formal memory would exceed 18000 characters"
        )
    if locked is not None:
        item.locked = locked
    if status is not None:
        item.status = status
    create_revision(
        db,
        item,
        operation=operation,
        source_turn_ids=[],
        created_by="user",
        reason=f"Manual {operation}",
    )
    _snapshot_manual(db)
    db.commit()
    db.refresh(item)
    return item


@router.post("/items/{item_id}/lock", response_model=MemoryItemRead)
def lock_memory_item(item_id: str, db: SessionDep) -> MemoryItem:
    return _state_change(item_id, "lock", db, locked=True)


@router.post("/items/{item_id}/unlock", response_model=MemoryItemRead)
def unlock_memory_item(item_id: str, db: SessionDep) -> MemoryItem:
    return _state_change(item_id, "unlock", db, locked=False)


@router.post("/items/{item_id}/archive", response_model=MemoryItemRead)
def archive_memory_item(item_id: str, db: SessionDep) -> MemoryItem:
    return _state_change(item_id, "archive", db, status="archived")


@router.post("/items/{item_id}/restore", response_model=MemoryItemRead)
def restore_memory_item(item_id: str, db: SessionDep) -> MemoryItem:
    return _state_change(item_id, "restore", db, status="active")


@router.get("/items/{item_id}/revisions", response_model=list[MemoryRevisionRead])
def list_memory_revisions(item_id: str, db: SessionDep) -> list[MemoryRevision]:
    _item(db, item_id)
    return list(
        db.scalars(
            select(MemoryRevision)
            .where(MemoryRevision.memory_item_id == item_id)
            .order_by(MemoryRevision.created_at.desc(), MemoryRevision.id.desc())
        )
    )


@router.post("/items/{item_id}/rollback/{revision_id}", response_model=MemoryItemRead)
def rollback_memory_item(item_id: str, revision_id: str, db: SessionDep) -> MemoryItem:
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    item = _item(db, item_id)
    revision = db.get(MemoryRevision, revision_id)
    if revision is None or revision.memory_item_id != item.id:
        raise HTTPException(status_code=404, detail="Memory revision not found")
    projected = (
        formal_char_count(db)
        - (item.char_count if item.status == "active" else 0)
        + (len(revision.content) if revision.status == "active" else 0)
    )
    if projected > FORMAL_MEMORY_CHAR_LIMIT:
        raise HTTPException(status_code=409, detail="Formal memory would exceed 18000 characters")
    item.title = revision.title
    item.content = revision.content
    item.category = revision.category
    item.tags_json = revision.tags_json
    item.priority = revision.priority
    item.status = revision.status
    item.locked = revision.locked
    create_revision(
        db,
        item,
        operation="rollback",
        source_turn_ids=revision.source_turn_ids,
        created_by="user",
        reason=f"Rollback to {revision.id}",
    )
    _snapshot_manual(db)
    db.commit()
    db.refresh(item)
    return item
