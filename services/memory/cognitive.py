from __future__ import annotations

import asyncio
import json
import re
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.agent.model_provider import OpenAICompatibleProvider, ProviderConfig
from services.api.app.core.config import get_settings
from services.api.app.db.models import (
    CognitiveJob,
    CognitiveState,
    FeedbackEvent,
    MemoryDelta,
    MemoryItem,
    MemoryRevision,
    Message,
    ModelSetting,
    ToolExecution,
    Turn,
    TurnExecutionTrace,
)
from services.api.app.db.session import SessionLocal
from services.memory.formal import (
    FORMAL_MEMORY_CHAR_LIMIT,
    create_revision,
    create_snapshot,
    formal_char_count,
)
from services.memory.realtime_delta import ACTIVE_STATUSES

JOB_TYPE = "memory_consolidation"
WINDOW_SIZE = 20
RETRY_DELAYS = (10, 30)


class MemoryConflictError(RuntimeError):
    pass


class CognitiveEventHub:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, object]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: str, job: CognitiveJob) -> None:
        payload = {
            "event": event,
            "job_id": job.id,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "status": job.status,
                "start_turn_number": job.start_turn_number,
                "end_turn_number": job.end_turn_number,
                "attempt_count": job.attempt_count,
                "error_message": job.error_message,
                "memory_version_after": job.memory_version_after,
            },
        }
        for queue in tuple(self._subscribers):
            if not queue.full():
                queue.put_nowait(payload)


cognitive_event_hub = CognitiveEventHub()


class MemoryOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    memory_ids: list[str] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=18_000)
    category: str | None = Field(default=None, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=20)
    priority: int = Field(default=50, ge=0, le=100)
    source_turn_ids: list[str] = Field(default_factory=list)
    expected_revision_ids: dict[str, str] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("operation")
    @classmethod
    def valid_operation(cls, value: str) -> str:
        if value not in {"add", "update", "merge", "archive", "noop"}:
            raise ValueError("unsupported memory operation")
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> MemoryOperation:
        if self.operation == "add" and (
            not self.content or not self.title or not self.source_turn_ids
        ):
            raise ValueError("add requires title, content and sources")
        if self.operation == "update" and (len(self.memory_ids) != 1 or not self.content):
            raise ValueError("update requires one id and content")
        if self.operation == "merge" and (len(self.memory_ids) < 2 or not self.content):
            raise ValueError("merge requires at least two ids and content")
        if self.operation == "archive" and len(self.memory_ids) != 1:
            raise ValueError("archive requires one id")
        return self


class CognitiveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=2000)
    memory_operations: list[MemoryOperation] = Field(max_length=200)
    skill_operations: list[dict[str, object]] = Field(default_factory=list, max_length=0)
    consumed_delta_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def state(db: Session) -> CognitiveState:
    value = db.get(CognitiveState, "global")
    if value is None:
        value = CognitiveState(
            id="global", completed_turn_count=0, last_consolidated_turn=0, memory_version=0
        )
        db.add(value)
        db.flush()
    return value


def record_completed_turn(db: Session, turn: Turn) -> CognitiveJob | None:
    current = state(db)
    if turn.completed_number is None:
        current.completed_turn_count += 1
        turn.completed_number = current.completed_turn_count
    return enqueue_due_job(db)


def enqueue_due_job(db: Session) -> CognitiveJob | None:
    current = state(db)
    start = current.last_consolidated_turn + 1
    end = start + WINDOW_SIZE - 1
    if current.completed_turn_count < end:
        return None
    existing = db.scalar(
        select(CognitiveJob).where(
            CognitiveJob.job_type == JOB_TYPE,
            CognitiveJob.start_turn_number == start,
            CognitiveJob.end_turn_number == end,
        )
    )
    if existing is not None:
        return None
    job = CognitiveJob(
        id=str(uuid4()),
        job_type=JOB_TYPE,
        start_turn_number=start,
        end_turn_number=end,
        status="pending",
        memory_version_before=current.memory_version,
        attempt_count=0,
        created_at=datetime.now(UTC),
    )
    db.add(job)
    db.flush()
    return job


def recover_unfinished_jobs(db: Session, *, stale_after_seconds: int = 300) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    jobs = list(
        db.scalars(
            select(CognitiveJob).where(
                CognitiveJob.status.in_(("running", "validating", "committing"))
            )
        )
    )
    recovered = 0
    for job in jobs:
        claimed = job.claimed_at
        if claimed is not None and claimed.tzinfo is None:
            claimed = claimed.replace(tzinfo=UTC)
        if claimed is None or claimed < cutoff:
            job.status = "pending"
            job.claimed_at = None
            job.next_attempt_at = None
            recovered += 1
    return recovered


def claim_next_job(db: Session) -> CognitiveJob | None:
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    now = datetime.now(UTC)
    job = db.scalar(
        select(CognitiveJob)
        .where(CognitiveJob.status == "pending")
        .order_by(CognitiveJob.created_at, CognitiveJob.id)
    )
    if job is None:
        db.rollback()
        return None
    next_at = job.next_attempt_at
    if next_at is not None and next_at.tzinfo is None:
        next_at = next_at.replace(tzinfo=UTC)
    if next_at is not None and next_at > now:
        db.rollback()
        return None
    job.status = "running"
    job.attempt_count += 1
    job.claimed_at = now
    job.started_at = job.started_at or now
    db.commit()
    return job


def build_job_payload(db: Session, job: CognitiveJob) -> dict[str, object]:
    turns = list(
        db.scalars(
            select(Turn)
            .where(Turn.completed_number.between(job.start_turn_number, job.end_turn_number))
            .order_by(Turn.completed_number)
        )
    )
    if len(turns) != WINDOW_SIZE:
        raise ValueError("job range does not contain exactly 20 completed turns")
    turn_data = []
    valid_turn_ids = {turn.id for turn in turns}
    for turn in turns:
        messages = list(
            db.scalars(select(Message).where(Message.turn_id == turn.id).order_by(Message.sequence))
        )
        tools = list(
            db.scalars(
                select(ToolExecution)
                .where(ToolExecution.turn_id == turn.id)
                .order_by(ToolExecution.call_sequence)
            )
        )
        trace = db.scalar(select(TurnExecutionTrace).where(TurnExecutionTrace.turn_id == turn.id))
        feedback = list(db.scalars(select(FeedbackEvent).where(FeedbackEvent.turn_id == turn.id)))
        turn_data.append(
            {
                "turn_id": turn.id,
                "turn_number": turn.completed_number,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "tools": [{"name": t.tool_name, "status": t.status} for t in tools],
                "feedback": [{"rating": f.rating, "comment": f.comment} for f in feedback],
                "trace": {
                    "memory_revision_ids": trace.memory_revision_ids,
                    "model": trace.model_id,
                    "usage": trace.normalized_usage,
                }
                if trace
                else None,
            }
        )
    items = list(
        db.scalars(
            select(MemoryItem)
            .where(MemoryItem.status == "active")
            .order_by(MemoryItem.priority.desc())
        )
    )
    deltas = list(
        db.scalars(
            select(MemoryDelta)
            .where(MemoryDelta.status.in_(ACTIVE_STATUSES))
            .order_by(MemoryDelta.priority.desc())
        )
    )
    return {
        "job": {"id": job.id, "start": job.start_turn_number, "end": job.end_turn_number},
        "formal_memory": [
            {
                "id": i.id,
                "revision_id": i.current_revision_id,
                "title": i.title,
                "content": i.content,
                "category": i.category,
                "tags": i.tags,
                "priority": i.priority,
                "locked": i.locked,
            }
            for i in items
        ],
        "realtime_delta": [
            {
                "id": d.id,
                "content": d.raw_content,
                "source_turn_id": d.source_turn_id,
                "priority": d.priority,
            }
            for d in deltas
        ],
        "turns": turn_data,
        "valid_turn_ids": sorted(valid_turn_ids),
        "skill_index": [],
    }


async def request_cognitive_result(payload: dict[str, object]) -> CognitiveResult:
    with SessionLocal() as db:
        setting = db.get(ModelSetting, "memory") or db.get(ModelSetting, "main")
        if setting is None or not setting.enabled:
            raise RuntimeError("memory model is unavailable")
        secret = get_settings().openai_api_key
        if secret is None or not secret.get_secret_value():
            raise RuntimeError("memory model API key is not configured")
        provider = OpenAICompatibleProvider(
            ProviderConfig(
                base_url=setting.base_url,
                api_key=secret.get_secret_value(),
                model=setting.model,
                timeout_seconds=setting.timeout_seconds,
                max_output_tokens=setting.max_output_tokens,
                temperature=setting.temperature,
            )
        )
    system = (
        "You consolidate agent memory. Return ONE strict JSON object only. Never emit markdown. "
        "Use only add/update/merge/archive/noop. Never modify locked memory. Every new fact needs "
        "source_turn_ids from the supplied exact 20 turns. Keep active formal memory <=18000 "
        "characters. Consume only supplied delta ids. skill_operations MUST be []. "
        "The exact required top-level keys are summary, memory_operations, skill_operations, "
        "consumed_delta_ids, warnings. summary is always required. consumed_delta_ids belongs only "
        "at the top level; never put delta_ids inside a memory operation. For add, title, content, "
        "category and source_turn_ids are required. For update/merge/archive include memory_ids "
        "and expected_revision_ids copied exactly from formal_memory. Example shape: "
        '{"summary":"Consolidated preferences","memory_operations":[{"operation":"add",'
        '"memory_ids":[],"title":"Interaction preference","content":"Use the GUI",'
        '"category":"preference","tags":["interaction"],"priority":90,'
        '"source_turn_ids":["an-exact-supplied-turn-id"],"expected_revision_ids":{},'
        '"reason":"Repeated explicit instruction"}],"skill_operations":[],'
        '"consumed_delta_ids":["an-exact-supplied-delta-id"],"warnings":[]}.'
    )
    chunks: list[str] = []
    async for event in provider.stream(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
    ):
        if event.delta:
            chunks.append(event.delta)
    raw = "".join(chunks).strip()
    try:
        return CognitiveResult.model_validate_json(raw)
    except ValidationError as exc:
        raise ValueError(f"model output failed strict validation: {exc}") from exc


def apply_result(
    db: Session, job: CognitiveJob, result: CognitiveResult, payload: dict[str, object]
) -> dict[str, int]:
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    current_job = db.get(CognitiveJob, job.id)
    if current_job is None or current_job.status not in {"running", "validating"}:
        raise RuntimeError("job is no longer claimable")
    current_job.status = "validating"
    valid_turn_ids = set(payload["valid_turn_ids"])
    valid_delta_ids = {d["id"] for d in payload["realtime_delta"]}  # type: ignore[index]
    if not set(result.consumed_delta_ids).issubset(valid_delta_ids):
        raise ValueError("unknown consumed delta id")
    if len(result.consumed_delta_ids) != len(set(result.consumed_delta_ids)):
        raise ValueError("consumed delta ids must be unique")
    proposed_contents = [
        operation.content for operation in result.memory_operations if operation.content
    ]
    existing_contents = [
        str(item["content"]) for item in payload["formal_memory"]  # type: ignore[index]
    ]
    delta_by_id = {
        str(delta["id"]): str(delta["content"])
        for delta in payload["realtime_delta"]  # type: ignore[index]
    }
    searchable_contents = existing_contents + proposed_contents
    for delta_id in result.consumed_delta_ids:
        if not any(delta_by_id[delta_id] in content for content in searchable_contents):
            raise ValueError("consumed explicit delta must be preserved verbatim")
    counts = {name: 0 for name in ("add", "update", "merge", "archive", "noop")}
    for operation in result.memory_operations:
        counts[operation.operation] += 1
        if operation.source_turn_ids and not set(operation.source_turn_ids).issubset(
            valid_turn_ids
        ):
            raise ValueError("memory operation references an unknown turn")
        items = [db.get(MemoryItem, item_id) for item_id in operation.memory_ids]
        if any(item is None for item in items):
            raise ValueError("memory operation references an unknown item")
        concrete = [item for item in items if item is not None]
        for item in concrete:
            expected = operation.expected_revision_ids.get(item.id)
            if operation.operation in {"update", "merge", "archive"} and not expected:
                raise ValueError("memory operation requires expected revision ids")
            if expected != item.current_revision_id:
                raise MemoryConflictError("memory revision conflict")
            if item.locked and operation.operation in {"update", "merge", "archive"}:
                raise ValueError("locked memory cannot be changed")
        if operation.operation == "add":
            revision_id = str(uuid4())
            item = MemoryItem(
                id=str(uuid4()),
                category=operation.category or "general",
                title=operation.title or "Memory",
                content=operation.content or "",
                tags_json=json.dumps(operation.tags),
                priority=operation.priority,
                status="active",
                locked=False,
                current_revision_id=revision_id,
                char_count=len(operation.content or ""),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(item)
            db.flush()
            db.add(
                MemoryRevision(
                    id=revision_id,
                    memory_item_id=item.id,
                    previous_revision_id=None,
                    operation="add",
                    title=item.title,
                    content=item.content,
                    category=item.category,
                    tags_json=item.tags_json,
                    priority=item.priority,
                    status=item.status,
                    locked=item.locked,
                    source_turn_ids_json=json.dumps(operation.source_turn_ids),
                    cognitive_job_id=job.id,
                    created_by="cognitive_worker",
                    reason=operation.reason,
                )
            )
        elif operation.operation == "update":
            item = concrete[0]
            item.content = operation.content or item.content
            item.title = operation.title or item.title
            item.category = operation.category or item.category
            item.tags_json = json.dumps(operation.tags) if operation.tags else item.tags_json
            item.priority = operation.priority
            create_revision(
                db,
                item,
                operation="update",
                source_turn_ids=operation.source_turn_ids,
                created_by="cognitive_worker",
                reason=operation.reason,
                job_id=job.id,
            )
        elif operation.operation == "merge":
            target = concrete[0]
            target.content = operation.content or target.content
            target.title = operation.title or target.title
            target.category = operation.category or target.category
            target.tags_json = json.dumps(operation.tags)
            target.priority = operation.priority
            create_revision(
                db,
                target,
                operation="merge",
                source_turn_ids=operation.source_turn_ids,
                created_by="cognitive_worker",
                reason=operation.reason,
                job_id=job.id,
            )
            for merged in concrete[1:]:
                merged.status = "superseded"
                create_revision(
                    db,
                    merged,
                    operation="merge_archive",
                    source_turn_ids=operation.source_turn_ids,
                    created_by="cognitive_worker",
                    reason=f"Merged into {target.id}",
                    job_id=job.id,
                )
        elif operation.operation == "archive":
            item = concrete[0]
            item.status = "archived"
            create_revision(
                db,
                item,
                operation="archive",
                source_turn_ids=operation.source_turn_ids,
                created_by="cognitive_worker",
                reason=operation.reason,
                job_id=job.id,
            )
    db.flush()
    if formal_char_count(db) > FORMAL_MEMORY_CHAR_LIMIT:
        raise ValueError("projected formal memory exceeds 18000 characters")
    for delta_id in result.consumed_delta_ids:
        delta = db.get(MemoryDelta, delta_id)
        if delta is None or delta.status not in ACTIVE_STATUSES:
            raise ValueError("delta is not consumable")
        delta.status = "consumed"
        delta.consumed_by_job_id = job.id
    current = state(db)
    current.memory_version += 1
    current.last_consolidated_turn = current_job.end_turn_number
    current_job.status = "committing"
    current_job.memory_version_after = current.memory_version
    create_snapshot(db, version=current.memory_version, job_id=job.id)
    current_job.status = "completed"
    current_job.completed_at = datetime.now(UTC)
    current_job.error_message = None
    current_job.result_json = json.dumps(
        {"summary": result.summary, "counts": counts, "warnings": result.warnings}
    )
    enqueue_due_job(db)
    db.commit()
    return counts


def mark_failure(job_id: str, error: Exception) -> None:
    with SessionLocal() as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        job = db.get(CognitiveJob, job_id)
        if job is None:
            db.rollback()
            return
        safe_error = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[REDACTED]", str(error))
        job.error_message = safe_error[:1000]
        if isinstance(error, MemoryConflictError):
            job.status = "conflict"
            job.completed_at = datetime.now(UTC)
            db.commit()
            return
        if job.attempt_count <= len(RETRY_DELAYS):
            job.status = "pending"
            job.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=RETRY_DELAYS[job.attempt_count - 1]
            )
        else:
            job.status = "failed"
            job.completed_at = datetime.now(UTC)
        db.commit()


class CognitiveWorker:
    def __init__(self) -> None:
        self._stop: asyncio.Event | None = None

    async def run_once(self) -> bool:
        with SessionLocal() as db:
            job = claim_next_job(db)
        if job is None:
            return False
        await cognitive_event_hub.publish("cognitive.job_started", job)
        try:
            with SessionLocal() as db:
                payload = build_job_payload(db, job)
            result = await request_cognitive_result(payload)
            with SessionLocal() as db:
                apply_result(db, job, result, payload)
                completed = db.get(CognitiveJob, job.id)
                if completed is not None:
                    await cognitive_event_hub.publish("cognitive.job_completed", completed)
        except Exception as exc:
            mark_failure(job.id, exc)
            with SessionLocal() as db:
                failed = db.get(CognitiveJob, job.id)
                if failed is not None:
                    await cognitive_event_hub.publish("cognitive.job_failed", failed)
        return True

    async def run(self) -> None:
        self._stop = asyncio.Event()
        while not self._stop.is_set():
            worked = await self.run_once()
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=1 if worked else 3)

    def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()


cognitive_worker = CognitiveWorker()
