from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from services.agent.model_provider import OpenAICompatibleProvider, ProviderConfig
from services.api.app.core.config import get_settings
from services.api.app.core.security import redact_text
from services.api.app.db.models import (
    CognitiveJob,
    CognitiveState,
    FeedbackEvent,
    MemoryDelta,
    MemoryItem,
    MemoryRevision,
    Message,
    ModelSetting,
    Skill,
    SkillEvolutionEvent,
    SkillUsage,
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
from services.skills.service import (
    archive_skill,
    create_candidate,
    create_skill,
    merge_skills,
    skill_event_hub,
    update_stable_skill,
)

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


class SkillOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    skill_ids: list[str] = Field(default_factory=list)
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=4_000)
    base_revision_id: str | None = None
    expected_revision_ids: dict[str, str] = Field(default_factory=dict)
    source_turn_ids: list[str] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=1000)
    expected_improvement: str | None = Field(default=None, max_length=1000)

    @field_validator("operation")
    @classmethod
    def valid_operation(cls, value: str) -> str:
        allowed = {"add", "update", "merge", "archive", "create_candidate_revision", "noop"}
        if value not in allowed:
            raise ValueError("unsupported Skill operation")
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> SkillOperation:
        if self.operation == "add" and (
            not self.name or not self.description or not self.content or not self.source_turn_ids
        ):
            raise ValueError("Skill add requires name, description, content and sources")
        if self.operation == "update" and (len(self.skill_ids) != 1 or not self.content):
            raise ValueError("Skill update requires one id and content")
        if self.operation == "merge" and (len(self.skill_ids) < 2 or not self.content):
            raise ValueError("Skill merge requires two ids and content")
        if self.operation == "archive" and len(self.skill_ids) != 1:
            raise ValueError("Skill archive requires one id")
        if self.operation == "create_candidate_revision" and (
            len(self.skill_ids) != 1
            or not self.base_revision_id
            or not self.content
            or not self.reason
            or not self.expected_improvement
            or not self.source_turn_ids
        ):
            raise ValueError(
                "candidate requires Skill, base, content, reason, improvement, sources"
            )
        return self


class CognitiveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=2000)
    memory_operations: list[MemoryOperation] = Field(max_length=200)
    skill_operations: list[SkillOperation] = Field(default_factory=list, max_length=100)
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
        .where(
            CognitiveJob.status.in_(("pending", "conflict")),
            or_(CognitiveJob.next_attempt_at.is_(None), CognitiveJob.next_attempt_at <= now),
        )
        .order_by(CognitiveJob.created_at, CognitiveJob.id)
    )
    if job is None:
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
                    "skill_revision_ids": trace.skill_revision_ids,
                    "model": trace.model_id,
                    "usage": trace.normalized_usage,
                    "objective_result": trace.objective_result,
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
    skills = list(
        db.scalars(select(Skill).where(Skill.status == "active").order_by(Skill.updated_at.desc()))
    )
    negative_skill_ids = {
        usage.skill_id
        for usage in db.scalars(
            select(SkillUsage).where(
                SkillUsage.turn_id.in_(valid_turn_ids),
                SkillUsage.feedback == "unsatisfied",
            )
        )
    }
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
        "skill_index": [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "use_count": skill.use_count,
                "success_count": skill.success_count,
                "failure_count": skill.failure_count,
                "locked": skill.locked,
                "stable_revision_id": skill.stable_revision_id,
                "candidate_revision_id": skill.candidate_revision_id,
                "updated_at": skill.updated_at.isoformat(),
            }
            for skill in skills
        ],
        "skill_documents": [
            {
                "id": skill.id,
                "stable_revision_id": skill.stable_revision_id,
                "content": skill.content,
            }
            for skill in skills
            if skill.id in negative_skill_ids
        ],
    }


def cognitive_system_prompt() -> str:
    return (
        "You consolidate agent memory. Return ONE strict JSON object only. Never emit markdown. "
        "Use only add/update/merge/archive/noop. Never modify locked memory. Every new fact needs "
        "source_turn_ids from the supplied exact 20 turns. Keep active formal memory <=18000 "
        "characters. Consume only supplied delta ids. Skill changes must use skill_operations. "
        "Prefer updating or merging an existing general Skill. Add a new Skill only after three "
        "traceable similar turns or an explicit request to save a Skill. "
        "Never modify locked Skills. "
        "Never replace a stable Skill directly because of negative feedback: use "
        "create_candidate_revision with its current stable_revision_id, traceable negative source "
        "turns, reason, and expected_improvement. Candidate content must retain "
        "success_criteria and safety constraints. "
        "The exact required top-level keys are summary, memory_operations, skill_operations, "
        "consumed_delta_ids, warnings. summary is always required. consumed_delta_ids belongs only "
        "at the top level; never put delta_ids inside a memory operation. "
        "A memory operation may contain ONLY operation, memory_ids, title, content, category, "
        "tags, priority, source_turn_ids, expected_revision_ids, reason. For add, title, content, "
        "category "
        "and source_turn_ids are required. For update/merge/archive include memory_ids and "
        "expected_revision_ids copied exactly from formal_memory. "
        "A Skill operation may contain ONLY operation, skill_ids, name, description, content, "
        "base_revision_id, expected_revision_ids, source_turn_ids, reason, expected_improvement. "
        "Never put category, tags, priority, success, success_name, feedback, or "
        "feedback_adaptation in a Skill operation. Do not invent any field. Skill operation must "
        "be "
        "exactly one of add, update, merge, archive, create_candidate_revision, noop. "
        "Skill add requires name, description, content, and source_turn_ids. Skill update requires "
        "one skill_id and content. Skill merge requires at least two skill_ids and content. Skill "
        "archive requires one skill_id. create_candidate_revision requires one skill_id, "
        "base_revision_id, content, reason, expected_improvement, and source_turn_ids. If no valid "
        "Skill change is justified, return an empty skill_operations list. "
        "Valid memory example: "
        '{"summary":"Consolidated preferences","memory_operations":[{"operation":"add",'
        '"memory_ids":[],"title":"Interaction preference","content":"Use the GUI",'
        '"category":"preference","tags":["interaction"],"priority":90,'
        '"source_turn_ids":["an-exact-supplied-turn-id"],"expected_revision_ids":{},'
        '"reason":"Repeated explicit instruction"}],"skill_operations":[],'
        '"consumed_delta_ids":["an-exact-supplied-delta-id"],"warnings":[]}. '
        "Valid Skill add example: "
        '{"operation":"add","skill_ids":[],"name":"Evidence check",'
        '"description":"Verify claims before answering","content":"steps:\\n- verify sources\\n'
        'success_criteria:\\n- claims are traceable","base_revision_id":null,'
        '"expected_revision_ids":{},"source_turn_ids":["an-exact-supplied-turn-id"],'
        '"reason":"Repeated successful workflow","expected_improvement":null}. '
        "Valid candidate example: "
        '{"operation":"create_candidate_revision","skill_ids":["an-existing-skill-id"],'
        '"name":null,"description":null,"content":"steps:\\n- revised step\\n'
        'success_criteria:\\n- issue is resolved","base_revision_id":"the-stable-revision-id",'
        '"expected_revision_ids":{"an-existing-skill-id":"the-current-revision-id"},'
        '"source_turn_ids":["an-exact-negative-feedback-turn-id"],'
        '"reason":"Traceable negative feedback","expected_improvement":"Avoid the failure"}.'
    )


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
    system = cognitive_system_prompt()
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


def _explicit_skill_request(payload: dict[str, object], source_turn_ids: set[str]) -> bool:
    markers = ("保存为 skill", "保存成 skill", "记为 skill", "save as a skill")
    for turn in payload["turns"]:  # type: ignore[assignment]
        if str(turn["turn_id"]) not in source_turn_ids:
            continue
        for message in turn["messages"]:
            if message["role"] == "user" and any(
                marker in str(message["content"]).casefold() for marker in markers
            ):
                return True
    return False


def _apply_skill_operations(
    db: Session,
    *,
    job: CognitiveJob,
    operations: list[SkillOperation],
    payload: dict[str, object],
    valid_turn_ids: set[str],
) -> dict[str, int]:
    counts = {
        name: 0
        for name in ("add", "update", "merge", "archive", "create_candidate_revision", "noop")
    }
    for index, operation in enumerate(operations):
        counts[operation.operation] += 1
        source_ids = set(operation.source_turn_ids)
        if not source_ids.issubset(valid_turn_ids):
            raise ValueError("Skill operation references an unknown turn")
        skills = [db.get(Skill, skill_id) for skill_id in operation.skill_ids]
        if any(skill is None for skill in skills):
            raise ValueError("Skill operation references an unknown Skill")
        concrete = [skill for skill in skills if skill is not None]
        operation_key = f"worker:{job.id}:{index}:{operation.operation}"
        if operation.operation == "add":
            create_skill(
                db,
                name=operation.name or "",
                description=operation.description or "",
                content=operation.content or "",
                source_turn_ids=operation.source_turn_ids,
                created_by="cognitive_worker",
                reason=operation.reason or "Reusable pattern found",
                idempotency_key=operation_key,
                job_id=job.id,
                allow_single_source=_explicit_skill_request(payload, source_ids),
            )
        elif operation.operation == "update":
            skill = concrete[0]
            expected = operation.expected_revision_ids.get(skill.id)
            if expected is None:
                raise ValueError("Skill update requires expected revision id")
            update_stable_skill(
                db,
                skill=skill,
                name=operation.name,
                description=operation.description,
                content=operation.content or "",
                expected_revision_id=expected,
                source_turn_ids=operation.source_turn_ids,
                created_by="cognitive_worker",
                reason=operation.reason or "Worker update",
                idempotency_key=operation_key,
                job_id=job.id,
            )
        elif operation.operation == "merge":
            merge_skills(
                db,
                target=concrete[0],
                source_skills=concrete[1:],
                content=operation.content or "",
                expected_revision_ids=operation.expected_revision_ids,
                source_turn_ids=operation.source_turn_ids,
                reason=operation.reason or "Worker merge",
                idempotency_key=operation_key,
                created_by="cognitive_worker",
                job_id=job.id,
            )
        elif operation.operation == "archive":
            skill = concrete[0]
            expected = operation.expected_revision_ids.get(skill.id)
            if expected != skill.stable_revision_id:
                raise ValueError("Skill revision conflict")
            archive_skill(db, skill, reason=operation.reason or "Worker archive")
        elif operation.operation == "create_candidate_revision":
            skill = concrete[0]
            create_candidate(
                db,
                skill=skill,
                base_revision_id=operation.base_revision_id or "",
                content=operation.content or "",
                source_turn_ids=operation.source_turn_ids,
                reason=operation.reason or "Negative feedback",
                expected_improvement=operation.expected_improvement or "Improve quality",
                idempotency_key=operation_key,
                job_id=job.id,
            )
    return counts


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
        str(item["content"])
        for item in payload["formal_memory"]  # type: ignore[index]
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
    skill_counts = _apply_skill_operations(
        db,
        job=current_job,
        operations=result.skill_operations,
        payload=payload,
        valid_turn_ids=valid_turn_ids,
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
        {
            "summary": result.summary,
            "counts": counts,
            "skill_counts": skill_counts,
            "warnings": result.warnings,
        }
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
        safe_error = redact_text(str(error))
        job.error_message = safe_error[:1000]
        if isinstance(error, MemoryConflictError):
            job.status = "conflict"
            if job.attempt_count <= len(RETRY_DELAYS):
                job.next_attempt_at = datetime.now(UTC) + timedelta(
                    seconds=RETRY_DELAYS[job.attempt_count - 1]
                )
                job.completed_at = None
            else:
                job.status = "failed"
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
                skill_events = list(
                    db.scalars(
                        select(SkillEvolutionEvent)
                        .where(SkillEvolutionEvent.cognitive_job_id == job.id)
                        .order_by(SkillEvolutionEvent.created_at, SkillEvolutionEvent.id)
                    )
                )
                for skill_event in skill_events:
                    await skill_event_hub.publish(skill_event)
        except Exception as exc:
            mark_failure(job.id, exc)
            logging.getLogger("survival.worker").error(
                "cognitive job failed: %s",
                redact_text(str(exc))[:1000],
                extra={"job_id": job.id},
            )
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
