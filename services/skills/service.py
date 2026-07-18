from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from services.api.app.db.models import (
    Skill,
    SkillEvolutionEvent,
    SkillRevision,
    SkillUsage,
    Turn,
    TurnExecutionTrace,
)

MAX_ACTIVE_SKILLS = 50
MAX_SKILL_CHARS = 4_000
MAX_LOADED_SKILLS = 3
MAX_LOADED_CHARS = 8_000
CANDIDATE_INTERVAL = 10
MIN_CANDIDATE_USES = 5


@dataclass(frozen=True)
class SelectedSkill:
    skill_id: str
    revision_id: str
    name: str
    description: str
    content: str
    revision_status: str


class SkillEventHub:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, object]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: SkillEvolutionEvent) -> None:
        payload = {
            "event": event.event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "skill_id": event.skill_id,
            "revision_id": event.revision_id,
            "job_id": event.cognitive_job_id,
            "data": {"reason": event.reason, "evidence": event.evidence},
        }
        for queue in tuple(self._subscribers):
            await queue.put(payload)


skill_event_hub = SkillEventHub()


def _words(value: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_\-]{2,}|[\u4e00-\u9fff]{2,}", value)}


def _validate_content(content: str, *, base_content: str | None = None) -> str:
    content = content.strip()
    if not content:
        raise ValueError("Skill content cannot be empty")
    if len(content) > MAX_SKILL_CHARS:
        raise ValueError("Skill content exceeds 4000 characters")
    if "success_criteria:" not in content.lower():
        raise ValueError("Skill content must contain success_criteria")
    if base_content is not None:
        base_lower = base_content.lower()
        current_lower = content.lower()
        if "success_criteria:" in base_lower and "success_criteria:" not in current_lower:
            raise ValueError("Candidate cannot remove success criteria")
        for heading in ("safety_constraints:", "安全约束:", "安全约束："):
            if heading in base_lower and heading not in current_lower:
                raise ValueError("Candidate cannot remove safety constraints")
    return content


def _audit(
    db: Session,
    *,
    skill_id: str,
    event_type: str,
    idempotency_key: str,
    revision_id: str | None = None,
    job_id: str | None = None,
    reason: str | None = None,
    evidence: dict[str, object] | None = None,
) -> SkillEvolutionEvent:
    existing = db.scalar(
        select(SkillEvolutionEvent).where(SkillEvolutionEvent.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing
    event = SkillEvolutionEvent(
        id=str(uuid4()),
        skill_id=skill_id,
        revision_id=revision_id,
        cognitive_job_id=job_id,
        event_type=event_type,
        reason=reason,
        evidence_json=json.dumps(evidence or {}, ensure_ascii=False),
        idempotency_key=idempotency_key,
    )
    db.add(event)
    return event


def create_skill(
    db: Session,
    *,
    name: str,
    description: str,
    content: str,
    source_turn_ids: list[str],
    created_by: str,
    reason: str,
    idempotency_key: str,
    job_id: str | None = None,
    allow_single_source: bool = False,
) -> Skill:
    existing_revision = db.scalar(
        select(SkillRevision).where(SkillRevision.idempotency_key == idempotency_key)
    )
    if existing_revision is not None:
        existing = db.get(Skill, existing_revision.skill_id)
        if existing is None:
            raise RuntimeError("idempotent Skill revision has no Skill")
        return existing
    if db.scalar(select(Skill).where(func.lower(Skill.name) == name.strip().lower())):
        raise ValueError("Skill name already exists; update the existing Skill")
    active_count = int(
        db.scalar(select(func.count()).select_from(Skill).where(Skill.status == "active")) or 0
    )
    if active_count >= MAX_ACTIVE_SKILLS:
        raise ValueError("active Skill limit reached")
    if len(set(source_turn_ids)) < 3 and not allow_single_source:
        raise ValueError("automatic Skill creation requires at least three source turns")
    revision_id = str(uuid4())
    skill = Skill(
        id=str(uuid4()),
        name=name.strip(),
        description=description.strip(),
        content=_validate_content(content),
        status="active",
        locked=False,
        stable_revision_id=revision_id,
        created_by=created_by,
    )
    revision = SkillRevision(
        id=revision_id,
        skill_id=skill.id,
        operation="create",
        status="stable",
        name=skill.name,
        description=skill.description,
        content=skill.content,
        reason=reason,
        source_turn_ids_json=json.dumps(sorted(set(source_turn_ids))),
        cognitive_job_id=job_id,
        created_by=created_by,
        idempotency_key=idempotency_key,
    )
    db.add_all([skill, revision])
    db.flush()
    _audit(
        db,
        skill_id=skill.id,
        revision_id=revision.id,
        job_id=job_id,
        event_type="skill.created",
        reason=reason,
        evidence={"source_turn_ids": sorted(set(source_turn_ids))},
        idempotency_key=f"event:{idempotency_key}",
    )
    return skill


def update_stable_skill(
    db: Session,
    *,
    skill: Skill,
    name: str | None,
    description: str | None,
    content: str,
    expected_revision_id: str,
    source_turn_ids: list[str],
    created_by: str,
    reason: str,
    idempotency_key: str,
    job_id: str | None = None,
) -> Skill:
    existing_revision = db.scalar(
        select(SkillRevision).where(SkillRevision.idempotency_key == idempotency_key)
    )
    if existing_revision is not None:
        return skill
    if skill.locked:
        raise ValueError("locked Skill cannot be updated")
    if skill.stable_revision_id != expected_revision_id:
        raise ValueError("Skill revision conflict")
    old = db.get(SkillRevision, skill.stable_revision_id)
    if old is None:
        raise ValueError("stable Skill revision is missing")
    new_content = _validate_content(content, base_content=old.content)
    if (
        new_content == old.content
        and (name is None or name == old.name)
        and (description is None or description == old.description)
    ):
        raise ValueError("Skill update has no structural change")
    old.status = "superseded"
    revision = SkillRevision(
        id=str(uuid4()),
        skill_id=skill.id,
        previous_revision_id=old.id,
        operation="update",
        status="stable",
        name=(name or skill.name).strip(),
        description=(description or skill.description).strip(),
        content=new_content,
        reason=reason,
        source_turn_ids_json=json.dumps(sorted(set(source_turn_ids))),
        cognitive_job_id=job_id,
        created_by=created_by,
        idempotency_key=idempotency_key,
    )
    skill.name = revision.name
    skill.description = revision.description
    skill.content = revision.content
    skill.rollback_revision_id = old.id
    skill.stable_revision_id = revision.id
    db.add(revision)
    db.flush()
    _audit(
        db,
        skill_id=skill.id,
        revision_id=revision.id,
        job_id=job_id,
        event_type="skill.updated",
        reason=reason,
        evidence={"previous_revision_id": old.id},
        idempotency_key=f"event:{idempotency_key}",
    )
    return skill


def set_skill_lock(db: Session, skill: Skill, *, locked: bool, reason: str) -> None:
    skill.locked = locked
    if locked:
        skill.candidate_paused = True
    elif skill.candidate_revision_id is not None:
        skill.candidate_paused = False
    _audit(
        db,
        skill_id=skill.id,
        revision_id=skill.stable_revision_id,
        event_type="skill.locked" if locked else "skill.unlocked",
        reason=reason,
        idempotency_key=f"lock:{skill.id}:{locked}:{skill.stable_revision_id}",
    )


def archive_skill(db: Session, skill: Skill, *, reason: str) -> None:
    if skill.locked:
        raise ValueError("locked Skill cannot be archived")
    skill.status = "archived"
    stable = db.get(SkillRevision, skill.stable_revision_id)
    if stable is not None:
        stable.status = "archived"
    if skill.candidate_revision_id:
        candidate = db.get(SkillRevision, skill.candidate_revision_id)
        if candidate is not None:
            candidate.status = "archived"
        skill.candidate_revision_id = None
    skill.candidate_paused = False
    _audit(
        db,
        skill_id=skill.id,
        revision_id=skill.stable_revision_id,
        event_type="skill.archived",
        reason=reason,
        idempotency_key=f"archive:{skill.id}:{skill.stable_revision_id}",
    )


def restore_skill(db: Session, skill: Skill, *, reason: str) -> None:
    skill.status = "active"
    stable = db.get(SkillRevision, skill.stable_revision_id)
    if stable is not None:
        stable.status = "stable"
    _audit(
        db,
        skill_id=skill.id,
        revision_id=skill.stable_revision_id,
        event_type="skill.restored",
        reason=reason,
        idempotency_key=f"restore:{skill.id}:{skill.stable_revision_id}",
    )


def merge_skills(
    db: Session,
    *,
    target: Skill,
    source_skills: list[Skill],
    content: str,
    expected_revision_ids: dict[str, str],
    source_turn_ids: list[str],
    reason: str,
    idempotency_key: str,
    created_by: str,
    job_id: str | None = None,
) -> Skill:
    all_skills = [target, *source_skills]
    if len({skill.id for skill in all_skills}) < 2:
        raise ValueError("merge requires at least two distinct Skills")
    if any(skill.locked for skill in all_skills):
        raise ValueError("locked Skill cannot be merged")
    for skill in all_skills:
        if expected_revision_ids.get(skill.id) != skill.stable_revision_id:
            raise ValueError("Skill revision conflict")
    updated = update_stable_skill(
        db,
        skill=target,
        name=None,
        description=None,
        content=content,
        expected_revision_id=target.stable_revision_id,
        source_turn_ids=source_turn_ids,
        created_by=created_by,
        reason=reason,
        idempotency_key=idempotency_key,
        job_id=job_id,
    )
    revision = db.get(SkillRevision, updated.stable_revision_id)
    if revision is not None:
        revision.operation = "merge"
    for source in source_skills:
        source.status = "archived"
        source_revision = db.get(SkillRevision, source.stable_revision_id)
        if source_revision is not None:
            source_revision.status = "archived"
    _audit(
        db,
        skill_id=target.id,
        revision_id=target.stable_revision_id,
        job_id=job_id,
        event_type="skill.merged",
        reason=reason,
        evidence={"merged_skill_ids": [skill.id for skill in source_skills]},
        idempotency_key=f"merge-event:{idempotency_key}",
    )
    return target


def create_candidate(
    db: Session,
    *,
    skill: Skill,
    base_revision_id: str,
    content: str,
    source_turn_ids: list[str],
    reason: str,
    expected_improvement: str,
    idempotency_key: str,
    created_by: str = "worker",
    job_id: str | None = None,
) -> SkillRevision:
    existing = db.scalar(
        select(SkillRevision).where(SkillRevision.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing
    if skill.locked:
        raise ValueError("locked Skill cannot receive an automatic candidate")
    if skill.stable_revision_id != base_revision_id:
        raise ValueError("candidate base is not the current stable revision")
    if skill.candidate_revision_id is not None:
        raise ValueError("Skill already has a candidate")
    source_ids = sorted(set(source_turn_ids))
    if not source_ids:
        raise ValueError("candidate requires traceable source turns")
    traced = int(
        db.scalar(
            select(func.count())
            .select_from(SkillUsage)
            .where(
                SkillUsage.skill_id == skill.id,
                SkillUsage.turn_id.in_(source_ids),
            )
        )
        or 0
    )
    negative = int(
        db.scalar(
            select(func.count())
            .select_from(SkillUsage)
            .where(
                SkillUsage.skill_id == skill.id,
                SkillUsage.turn_id.in_(source_ids),
                SkillUsage.feedback == "unsatisfied",
            )
        )
        or 0
    )
    if traced == 0 or negative == 0:
        raise ValueError("candidate requires a traced negative feedback or objective failure")
    base = db.get(SkillRevision, base_revision_id)
    if base is None:
        raise ValueError("base revision does not exist")
    new_content = _validate_content(content, base_content=base.content)
    if new_content == base.content:
        raise ValueError("candidate must differ from the stable revision")
    revision = SkillRevision(
        id=str(uuid4()),
        skill_id=skill.id,
        previous_revision_id=base.id,
        operation="create_candidate_revision",
        status="candidate",
        name=base.name,
        description=base.description,
        content=new_content,
        reason=reason,
        expected_improvement=expected_improvement,
        source_turn_ids_json=json.dumps(source_ids),
        cognitive_job_id=job_id,
        created_by=created_by,
        idempotency_key=idempotency_key,
    )
    skill.candidate_revision_id = revision.id
    skill.candidate_paused = False
    db.add(revision)
    db.flush()
    _audit(
        db,
        skill_id=skill.id,
        revision_id=revision.id,
        job_id=job_id,
        event_type="skill.candidate_created",
        reason=reason,
        evidence={"base_revision_id": base.id, "source_turn_ids": source_ids},
        idempotency_key=f"event:{idempotency_key}",
    )
    return revision


def retrieve_skills(db: Session, *, query: str) -> list[SelectedSkill]:
    query_words = _words(query)
    ranked: list[tuple[float, Skill]] = []
    for skill in db.scalars(select(Skill).where(Skill.status == "active")):
        haystack = f"{skill.name} {skill.description} {skill.content}"
        overlap = len(query_words & _words(haystack))
        if overlap == 0:
            continue
        ranked.append((overlap * skill.selection_weight + skill.confidence_score, skill))
    selected: list[SelectedSkill] = []
    used_chars = 0
    for _, skill in sorted(ranked, key=lambda row: (-row[0], row[1].name, row[1].id)):
        revision_id = skill.stable_revision_id
        if skill.candidate_revision_id and not skill.candidate_paused and not skill.locked:
            completed = int(
                db.scalar(
                    select(func.count())
                    .select_from(SkillUsage)
                    .where(SkillUsage.skill_id == skill.id)
                )
                or 0
            )
            if (completed + 1) % CANDIDATE_INTERVAL == 0:
                revision_id = skill.candidate_revision_id
        revision = db.get(SkillRevision, revision_id)
        if revision is None:
            continue
        if used_chars + len(revision.content) > MAX_LOADED_CHARS:
            continue
        selected.append(
            SelectedSkill(
                skill_id=skill.id,
                revision_id=revision.id,
                name=revision.name,
                description=revision.description,
                content=revision.content,
                revision_status=revision.status,
            )
        )
        used_chars += len(revision.content)
        if len(selected) >= MAX_LOADED_SKILLS:
            break
    return selected


def skill_context(selected: list[SelectedSkill]) -> str | None:
    if not selected:
        return None
    sections = [
        f"[Skill {item.name} | revision {item.revision_id}]\n{item.content}" for item in selected
    ]
    return "Dynamic Skill Context (follow only when relevant):\n\n" + "\n\n".join(sections)


def record_skill_usage(
    db: Session,
    *,
    turn: Turn,
    trace: TurnExecutionTrace,
    selected: list[SelectedSkill],
) -> list[SkillEvolutionEvent]:
    objective = trace.objective_result
    objective_passed = not bool(objective.get("failed_tools", 0))
    events: list[SkillEvolutionEvent] = []
    for item in selected:
        existing = db.scalar(
            select(SkillUsage).where(
                SkillUsage.turn_id == turn.id,
                SkillUsage.skill_revision_id == item.revision_id,
            )
        )
        if existing is not None:
            continue
        db.add(
            SkillUsage(
                id=str(uuid4()),
                skill_id=item.skill_id,
                skill_revision_id=item.revision_id,
                turn_id=turn.id,
                result="completed",
                objective_passed=objective_passed,
                input_tokens=trace.input_tokens,
                output_tokens=trace.output_tokens,
            )
        )
        if item.revision_status == "candidate":
            events.append(
                _audit(
                    db,
                    skill_id=item.skill_id,
                    revision_id=item.revision_id,
                    event_type="skill.candidate_started",
                    reason="deterministic 10th eligible use completed",
                    evidence={"turn_id": turn.id},
                    idempotency_key=f"candidate-started:{item.revision_id}:{turn.id}",
                )
            )
    db.flush()
    for skill_id in {item.skill_id for item in selected}:
        recompute_skill_statistics(db, skill_id)
    return events


def recompute_skill_statistics(db: Session, skill_id: str) -> None:
    skill = db.get(Skill, skill_id)
    if skill is None:
        return
    usages = list(db.scalars(select(SkillUsage).where(SkillUsage.skill_id == skill_id)))
    skill.use_count = len(usages)
    skill.success_count = sum(usage.feedback == "satisfied" for usage in usages)
    skill.failure_count = sum(usage.feedback == "unsatisfied" for usage in usages)
    rated = skill.success_count + skill.failure_count
    skill.confidence_score = (skill.success_count + 1) / (rated + 2)


def _revision_metrics(db: Session, revision_id: str) -> dict[str, float | int]:
    usages = list(
        db.scalars(
            select(SkillUsage)
            .where(SkillUsage.skill_revision_id == revision_id)
            .order_by(SkillUsage.created_at, SkillUsage.id)
        )
    )
    rated = [usage for usage in usages if usage.feedback is not None]
    objective = [usage for usage in usages if usage.objective_passed is not None]
    return {
        "uses": len(usages),
        "rated": len(rated),
        "satisfaction_rate": (
            sum(usage.feedback == "satisfied" for usage in rated) / len(rated) if rated else 0.0
        ),
        "objective_rate": (
            sum(bool(usage.objective_passed) for usage in objective) / len(objective)
            if objective
            else 0.0
        ),
        "average_tokens": (
            sum(usage.input_tokens + usage.output_tokens for usage in usages) / len(usages)
            if usages
            else 0.0
        ),
    }


def _reject_candidate(db: Session, skill: Skill, reason: str, *, automatic: bool) -> None:
    if skill.candidate_revision_id is None:
        raise ValueError("Skill has no candidate")
    revision = db.get(SkillRevision, skill.candidate_revision_id)
    if revision is None:
        raise ValueError("candidate revision is missing")
    revision.status = "rejected"
    skill.candidate_revision_id = None
    skill.candidate_paused = False
    _audit(
        db,
        skill_id=skill.id,
        revision_id=revision.id,
        event_type="skill.candidate_rejected",
        reason=reason,
        evidence={"automatic": automatic, "metrics": _revision_metrics(db, revision.id)},
        idempotency_key=f"reject:{revision.id}:{'auto' if automatic else 'manual'}",
    )


def reject_candidate(db: Session, skill: Skill, *, reason: str, automatic: bool = False) -> None:
    _reject_candidate(db, skill, reason, automatic=automatic)


def promote_candidate(db: Session, skill: Skill, *, reason: str, automatic: bool) -> None:
    if skill.candidate_revision_id is None:
        raise ValueError("Skill has no candidate")
    candidate = db.get(SkillRevision, skill.candidate_revision_id)
    stable = db.get(SkillRevision, skill.stable_revision_id)
    if candidate is None or stable is None:
        raise ValueError("Skill revision is missing")
    stable.status = "superseded"
    candidate.status = "stable"
    candidate.promoted_at = datetime.now(UTC)
    skill.rollback_revision_id = stable.id
    skill.stable_revision_id = candidate.id
    skill.candidate_revision_id = None
    skill.candidate_paused = False
    skill.content = candidate.content
    skill.name = candidate.name
    skill.description = candidate.description
    skill.promotion_observation_remaining = 5
    skill.consecutive_failures = 0
    _audit(
        db,
        skill_id=skill.id,
        revision_id=candidate.id,
        event_type="skill.candidate_promoted",
        reason=reason,
        evidence={"automatic": automatic, "previous_stable_revision_id": stable.id},
        idempotency_key=f"promote:{candidate.id}",
    )


def rollback_skill(
    db: Session, skill: Skill, revision_id: str, *, reason: str, automatic: bool
) -> None:
    target = db.get(SkillRevision, revision_id)
    current = db.get(SkillRevision, skill.stable_revision_id)
    if target is None or target.skill_id != skill.id or current is None:
        raise ValueError("rollback revision does not belong to Skill")
    if skill.locked and automatic:
        raise ValueError("locked Skill cannot be auto-rolled back")
    current.status = "rejected_after_promotion" if automatic else "superseded"
    target.status = "stable"
    skill.stable_revision_id = target.id
    skill.content = target.content
    skill.name = target.name
    skill.description = target.description
    skill.rollback_revision_id = current.id
    skill.promotion_observation_remaining = 0
    skill.consecutive_failures = 0
    _audit(
        db,
        skill_id=skill.id,
        revision_id=target.id,
        event_type="skill.auto_rollback" if automatic else "skill.rolled_back",
        reason=reason,
        evidence={"replaced_revision_id": current.id},
        idempotency_key=f"rollback:{current.id}:{target.id}:{'auto' if automatic else 'manual'}",
    )


def evaluate_candidate(db: Session, skill: Skill) -> str:
    skill.last_evaluated_at = datetime.now(UTC)
    if skill.candidate_revision_id is None or skill.candidate_paused:
        return "inactive"
    candidate = db.get(SkillRevision, skill.candidate_revision_id)
    if candidate is None:
        return "missing"
    candidate_metrics = _revision_metrics(db, candidate.id)
    stable_metrics = _revision_metrics(db, skill.stable_revision_id)
    candidate_usages = list(
        db.scalars(
            select(SkillUsage)
            .where(SkillUsage.skill_revision_id == candidate.id)
            .order_by(SkillUsage.created_at.desc(), SkillUsage.id.desc())
        )
    )
    consecutive_failures = 0
    for usage in candidate_usages:
        if usage.feedback == "unsatisfied" or usage.objective_passed is False:
            consecutive_failures += 1
        else:
            break
    skill.consecutive_failures = consecutive_failures
    candidate_tokens = float(candidate_metrics["average_tokens"])
    stable_tokens = float(stable_metrics["average_tokens"])

    def score(metrics: dict[str, float | int], baseline_tokens: float) -> float:
        average_tokens = float(metrics["average_tokens"])
        token_efficiency = (
            min(1.0, baseline_tokens / average_tokens)
            if baseline_tokens > 0 and average_tokens > 0
            else 1.0
        )
        task_completion = 1.0 if int(metrics["uses"]) else 0.0
        return round(
            float(metrics["satisfaction_rate"]) * 0.60
            + task_completion * 0.20
            + float(metrics["objective_rate"]) * 0.15
            + token_efficiency * 0.05,
            6,
        )

    evidence = {
        "candidate": candidate_metrics,
        "stable": stable_metrics,
        "weights": {
            "user_satisfaction": 0.60,
            "task_completion": 0.20,
            "objective_validation": 0.15,
            "token_efficiency": 0.05,
        },
        "candidate_score": score(candidate_metrics, stable_tokens),
        "stable_score": score(stable_metrics, stable_tokens),
    }
    _audit(
        db,
        skill_id=skill.id,
        revision_id=candidate.id,
        event_type="skill.candidate_evaluated",
        reason="deterministic candidate evaluation",
        evidence=evidence,
        idempotency_key=f"evaluate:{candidate.id}:{candidate_metrics['uses']}:{candidate_metrics['rated']}",
    )
    if consecutive_failures >= 2:
        _reject_candidate(db, skill, "candidate reached two consecutive failures", automatic=True)
        return "rejected"
    if int(candidate_metrics["uses"]) < MIN_CANDIDATE_USES:
        return "collecting"
    candidate_rate = float(candidate_metrics["satisfaction_rate"])
    stable_rate = float(stable_metrics["satisfaction_rate"])
    candidate_objective = float(candidate_metrics["objective_rate"])
    stable_objective = float(stable_metrics["objective_rate"])
    enough_feedback = int(candidate_metrics["rated"]) >= MIN_CANDIDATE_USES
    token_ok = stable_tokens == 0 or candidate_tokens <= stable_tokens * 1.5
    if (
        enough_feedback
        and candidate_rate >= stable_rate + 0.10
        and candidate_objective >= stable_objective
        and token_ok
    ):
        promote_candidate(
            db,
            skill,
            reason="candidate passed minimum use, quality, objective, and token thresholds",
            automatic=True,
        )
        return "promoted"
    return "collecting"


def apply_quality_feedback(db: Session, *, turn_id: str, rating: str) -> list[str]:
    usages = list(db.scalars(select(SkillUsage).where(SkillUsage.turn_id == turn_id)))
    affected: list[str] = []
    for usage in usages:
        usage.feedback = rating
        affected.append(usage.skill_id)
    db.flush()
    for skill_id in sorted(set(affected)):
        skill = db.get(Skill, skill_id)
        if skill is None:
            continue
        recompute_skill_statistics(db, skill_id)
        if skill.promotion_observation_remaining > 0:
            skill.promotion_observation_remaining -= 1
            trace = db.scalar(
                select(TurnExecutionTrace).where(TurnExecutionTrace.turn_id == turn_id)
            )
            if (
                trace is not None
                and trace.objective_result.get("severe_failure") is True
                and skill.rollback_revision_id is not None
            ):
                rollback_skill(
                    db,
                    skill,
                    skill.rollback_revision_id,
                    reason="severe objective failure during promotion observation",
                    automatic=True,
                )
                continue
            recent = list(
                db.scalars(
                    select(SkillUsage)
                    .where(SkillUsage.skill_revision_id == skill.stable_revision_id)
                    .order_by(SkillUsage.created_at.desc(), SkillUsage.id.desc())
                    .limit(2)
                )
            )
            if (
                len(recent) == 2
                and all(usage.feedback == "unsatisfied" for usage in recent)
                and skill.rollback_revision_id is not None
            ):
                rollback_skill(
                    db,
                    skill,
                    skill.rollback_revision_id,
                    reason="two consecutive unsatisfied ratings during promotion observation",
                    automatic=True,
                )
                continue
        evaluate_candidate(db, skill)
    return sorted(set(affected))
