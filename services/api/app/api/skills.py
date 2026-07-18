from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.api.app.db.models import Skill, SkillEvolutionEvent, SkillRevision, SkillUsage
from services.api.app.db.session import get_db
from services.api.app.schemas.skills import (
    CandidateAction,
    SkillCreate,
    SkillEvolutionEventRead,
    SkillEvolutionRead,
    SkillRead,
    SkillRevisionRead,
    SkillUpdate,
)
from services.skills.service import (
    archive_skill,
    create_skill,
    promote_candidate,
    reject_candidate,
    restore_skill,
    rollback_skill,
    set_skill_lock,
    skill_event_hub,
    update_stable_skill,
)

router = APIRouter(prefix="/skills", tags=["skills"])
SessionDep = Annotated[Session, Depends(get_db)]


def _skill(db: SessionDep, skill_id: str) -> Skill:
    item = db.get(Skill, skill_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return item


async def _commit_and_publish(db: SessionDep, skill_id: str) -> None:
    event = db.scalar(
        select(SkillEvolutionEvent)
        .where(SkillEvolutionEvent.skill_id == skill_id)
        .order_by(SkillEvolutionEvent.created_at.desc(), SkillEvolutionEvent.id.desc())
        .limit(1)
    )
    db.commit()
    if event is not None:
        db.refresh(event)
        await skill_event_hub.publish(event)


@router.get("", response_model=list[SkillRead])
def list_skills(
    db: SessionDep,
    query: str | None = None,
    skill_status: str | None = Query(default=None, alias="status"),
) -> list[Skill]:
    statement = select(Skill).order_by(Skill.updated_at.desc(), Skill.name)
    if skill_status:
        statement = statement.where(Skill.status == skill_status)
    items = list(db.scalars(statement))
    if query:
        needle = query.casefold()
        items = [
            item
            for item in items
            if needle in f"{item.name} {item.description} {item.content}".casefold()
        ]
    return items


@router.post("", response_model=SkillRead, status_code=status.HTTP_201_CREATED)
async def create_skill_api(payload: SkillCreate, db: SessionDep) -> Skill:
    try:
        item = create_skill(
            db,
            name=payload.name,
            description=payload.description,
            content=payload.content,
            source_turn_ids=payload.source_turn_ids,
            created_by="user",
            reason=payload.reason,
            idempotency_key=f"manual-create:{uuid4()}",
            allow_single_source=True,
        )
        await _commit_and_publish(db, item.id)
        db.refresh(item)
        return item
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/evolution-events", response_model=list[SkillEvolutionEventRead])
def list_evolution_events(
    db: SessionDep, limit: int = Query(default=100, ge=1, le=500)
) -> list[SkillEvolutionEvent]:
    return list(
        db.scalars(
            select(SkillEvolutionEvent)
            .order_by(SkillEvolutionEvent.created_at.desc(), SkillEvolutionEvent.id.desc())
            .limit(limit)
        )
    )


@router.get("/{skill_id}", response_model=SkillRead)
def get_skill(skill_id: str, db: SessionDep) -> Skill:
    return _skill(db, skill_id)


@router.patch("/{skill_id}", response_model=SkillRead)
async def update_skill(skill_id: str, payload: SkillUpdate, db: SessionDep) -> Skill:
    item = _skill(db, skill_id)
    try:
        update_stable_skill(
            db,
            skill=item,
            name=payload.name,
            description=payload.description,
            content=payload.content,
            expected_revision_id=payload.expected_revision_id,
            source_turn_ids=[],
            created_by="user",
            reason=payload.reason,
            idempotency_key=f"manual-update:{skill_id}:{uuid4()}",
        )
        await _commit_and_publish(db, item.id)
        db.refresh(item)
        return item
    except ValueError as exc:
        db.rollback()
        code = 409 if "conflict" in str(exc).lower() else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/{skill_id}/lock", response_model=SkillRead)
async def lock_skill(skill_id: str, db: SessionDep) -> Skill:
    item = _skill(db, skill_id)
    set_skill_lock(db, item, locked=True, reason="Locked by user")
    await _commit_and_publish(db, item.id)
    db.refresh(item)
    return item


@router.post("/{skill_id}/unlock", response_model=SkillRead)
async def unlock_skill(skill_id: str, db: SessionDep) -> Skill:
    item = _skill(db, skill_id)
    set_skill_lock(db, item, locked=False, reason="Unlocked by user")
    await _commit_and_publish(db, item.id)
    db.refresh(item)
    return item


@router.post("/{skill_id}/archive", response_model=SkillRead)
async def archive_skill_api(skill_id: str, db: SessionDep) -> Skill:
    item = _skill(db, skill_id)
    try:
        archive_skill(db, item, reason="Archived by user")
        await _commit_and_publish(db, item.id)
        db.refresh(item)
        return item
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{skill_id}/restore", response_model=SkillRead)
async def restore_skill_api(skill_id: str, db: SessionDep) -> Skill:
    item = _skill(db, skill_id)
    restore_skill(db, item, reason="Restored by user")
    await _commit_and_publish(db, item.id)
    db.refresh(item)
    return item


@router.get("/{skill_id}/revisions", response_model=list[SkillRevisionRead])
def list_skill_revisions(skill_id: str, db: SessionDep) -> list[SkillRevision]:
    _skill(db, skill_id)
    return list(
        db.scalars(
            select(SkillRevision)
            .where(SkillRevision.skill_id == skill_id)
            .order_by(SkillRevision.created_at.desc(), SkillRevision.id.desc())
        )
    )


@router.get("/{skill_id}/evolution", response_model=SkillEvolutionRead)
def get_skill_evolution(skill_id: str, db: SessionDep) -> SkillEvolutionRead:
    item = _skill(db, skill_id)
    revisions = list(
        db.scalars(
            select(SkillRevision)
            .where(SkillRevision.skill_id == skill_id)
            .order_by(SkillRevision.created_at.desc(), SkillRevision.id.desc())
        )
    )
    usages = list(
        db.scalars(
            select(SkillUsage)
            .where(SkillUsage.skill_id == skill_id)
            .order_by(SkillUsage.created_at.desc(), SkillUsage.id.desc())
        )
    )
    events = list(
        db.scalars(
            select(SkillEvolutionEvent)
            .where(SkillEvolutionEvent.skill_id == skill_id)
            .order_by(SkillEvolutionEvent.created_at.desc(), SkillEvolutionEvent.id.desc())
        )
    )
    return SkillEvolutionRead(skill=item, revisions=revisions, usages=usages, events=events)


@router.post("/{skill_id}/candidate/{revision_id}/promote", response_model=SkillRead)
async def promote_candidate_api(
    skill_id: str, revision_id: str, payload: CandidateAction, db: SessionDep
) -> Skill:
    item = _skill(db, skill_id)
    if item.candidate_revision_id != revision_id:
        raise HTTPException(status_code=409, detail="Revision is not the active candidate")
    promote_candidate(db, item, reason=payload.reason, automatic=False)
    await _commit_and_publish(db, item.id)
    db.refresh(item)
    return item


@router.post("/{skill_id}/candidate/{revision_id}/reject", response_model=SkillRead)
async def reject_candidate_api(
    skill_id: str, revision_id: str, payload: CandidateAction, db: SessionDep
) -> Skill:
    item = _skill(db, skill_id)
    if item.candidate_revision_id != revision_id:
        raise HTTPException(status_code=409, detail="Revision is not the active candidate")
    reject_candidate(db, item, reason=payload.reason)
    await _commit_and_publish(db, item.id)
    db.refresh(item)
    return item


@router.post("/{skill_id}/candidate/{revision_id}/pause", response_model=SkillRead)
async def pause_candidate_api(
    skill_id: str, revision_id: str, payload: CandidateAction, db: SessionDep
) -> Skill:
    item = _skill(db, skill_id)
    if item.candidate_revision_id != revision_id:
        raise HTTPException(status_code=409, detail="Revision is not the active candidate")
    item.candidate_paused = True
    from services.skills.service import _audit

    _audit(
        db,
        skill_id=item.id,
        revision_id=revision_id,
        event_type="skill.candidate_paused",
        reason=payload.reason,
        idempotency_key=f"pause:{revision_id}",
    )
    await _commit_and_publish(db, item.id)
    db.refresh(item)
    return item


@router.post("/{skill_id}/rollback/{revision_id}", response_model=SkillRead)
async def rollback_skill_api(
    skill_id: str, revision_id: str, payload: CandidateAction, db: SessionDep
) -> Skill:
    item = _skill(db, skill_id)
    rollback_skill(db, item, revision_id, reason=payload.reason, automatic=False)
    await _commit_and_publish(db, item.id)
    db.refresh(item)
    return item
