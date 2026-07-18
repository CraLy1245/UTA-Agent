import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from services.api.app.db.base import Base
from services.api.app.db.models import (
    CognitiveJob,
    CognitiveState,
    Conversation,
    MemoryDelta,
    MemoryItem,
    MemoryRevision,
    MemorySnapshot,
    Message,
    Turn,
)
from services.memory.cognitive import (
    CognitiveResult,
    apply_result,
    build_job_payload,
    claim_next_job,
    cognitive_event_hub,
    record_completed_turn,
    recover_unfinished_jobs,
)


@pytest.fixture()
def cognitive_db(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'cognitive.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield db
    engine.dispose()


def seed_completed_turns(db: Session, count: int = 20) -> list[Turn]:
    conversation = Conversation(id=str(uuid4()), title="cognitive test")
    db.add(conversation)
    turns: list[Turn] = []
    for number in range(1, count + 1):
        turn_id = str(uuid4())
        user_id = str(uuid4())
        turn = Turn(
            id=turn_id,
            conversation_id=conversation.id,
            user_message_id=user_id,
            status="completed",
            completed_number=number,
            completed_at=datetime.now(UTC),
        )
        db.add_all(
            [
                turn,
                Message(
                    id=user_id,
                    conversation_id=conversation.id,
                    turn_id=turn_id,
                    role="user",
                    content=f"question {number}",
                    sequence=number * 2 - 1,
                ),
                Message(
                    id=str(uuid4()),
                    conversation_id=conversation.id,
                    turn_id=turn_id,
                    role="assistant",
                    content=f"answer {number}",
                    sequence=number * 2,
                ),
            ]
        )
        turns.append(turn)
    db.add(
        CognitiveState(
            id="global",
            completed_turn_count=count,
            last_consolidated_turn=0,
            memory_version=0,
        )
    )
    db.commit()
    return turns


def test_only_recorded_successes_create_one_frozen_twenty_turn_job(cognitive_db: Session) -> None:
    state = CognitiveState(
        id="global", completed_turn_count=0, last_consolidated_turn=0, memory_version=0
    )
    cognitive_db.add(state)
    conversation = Conversation(id=str(uuid4()), title="counting")
    cognitive_db.add(conversation)
    for number in range(20):
        turn = Turn(
            id=str(uuid4()),
            conversation_id=conversation.id,
            user_message_id=str(uuid4()),
            status="completed",
        )
        cognitive_db.add(turn)
        job = record_completed_turn(cognitive_db, turn)
        assert turn.completed_number == number + 1
        assert job is None if number < 19 else job is not None
    cognitive_db.commit()
    jobs = list(cognitive_db.scalars(select(CognitiveJob)))
    assert [(job.start_turn_number, job.end_turn_number) for job in jobs] == [(1, 20)]
    assert cognitive_db.scalar(select(func.count()).select_from(CognitiveJob)) == 1


def test_job_payload_is_exactly_frozen_and_excludes_turn_twenty_one(
    cognitive_db: Session,
) -> None:
    turns = seed_completed_turns(cognitive_db, 21)
    job = CognitiveJob(
        id=str(uuid4()),
        job_type="memory_consolidation",
        start_turn_number=1,
        end_turn_number=20,
        status="running",
        memory_version_before=0,
        attempt_count=1,
    )
    cognitive_db.add(job)
    cognitive_db.commit()
    payload = build_job_payload(cognitive_db, job)
    assert len(payload["turns"]) == 20
    assert turns[20].id not in payload["valid_turn_ids"]
    assert payload["skill_index"] == []


def test_strict_result_rejects_markdown_extra_fields_and_skill_operations() -> None:
    valid = {
        "summary": "no durable changes",
        "memory_operations": [{"operation": "noop"}],
        "skill_operations": [],
        "consumed_delta_ids": [],
        "warnings": [],
    }
    CognitiveResult.model_validate(valid)
    with pytest.raises(ValidationError):
        CognitiveResult.model_validate({**valid, "unexpected": True})
    with pytest.raises(ValidationError):
        CognitiveResult.model_validate({**valid, "skill_operations": [{"operation": "add"}]})
    with pytest.raises(ValidationError):
        CognitiveResult.model_validate_json(f"```json\n{json.dumps(valid)}\n```")


def test_atomic_commit_creates_revision_snapshot_and_consumes_delta(
    cognitive_db: Session,
) -> None:
    turns = seed_completed_turns(cognitive_db)
    job = CognitiveJob(
        id=str(uuid4()),
        job_type="memory_consolidation",
        start_turn_number=1,
        end_turn_number=20,
        status="running",
        memory_version_before=0,
        attempt_count=1,
    )
    delta = MemoryDelta(
        id=str(uuid4()),
        revision_id=str(uuid4()),
        source_turn_id=turns[0].id,
        raw_content="Remember concise answers",
        normalized_content="Remember concise answers",
        delta_type="explicit_instruction",
        priority=95,
        status="pending",
        char_count=24,
    )
    cognitive_db.add_all([job, delta])
    cognitive_db.commit()
    payload = build_job_payload(cognitive_db, job)
    result = CognitiveResult.model_validate(
        {
            "summary": "created one preference",
            "memory_operations": [
                {
                    "operation": "add",
                    "title": "Response style",
                    "content": "Remember concise answers",
                    "category": "preference",
                    "source_turn_ids": [turns[0].id],
                }
            ],
            "skill_operations": [],
            "consumed_delta_ids": [delta.id],
            "warnings": [],
        }
    )
    counts = apply_result(cognitive_db, job, result, payload)
    assert counts["add"] == 1
    item = cognitive_db.scalar(select(MemoryItem))
    assert item is not None and item.content == "Remember concise answers"
    assert cognitive_db.get(MemoryRevision, item.current_revision_id) is not None
    assert cognitive_db.scalar(select(func.count()).select_from(MemorySnapshot)) == 1
    cognitive_db.refresh(delta)
    assert (delta.status, delta.consumed_by_job_id) == ("consumed", job.id)
    assert cognitive_db.get(CognitiveState, "global").last_consolidated_turn == 20


def test_locked_memory_and_over_budget_results_preserve_old_state(
    cognitive_db: Session,
) -> None:
    turns = seed_completed_turns(cognitive_db)
    revision_id = str(uuid4())
    item = MemoryItem(
        id=str(uuid4()),
        category="core",
        title="Locked",
        content="Do not replace",
        tags_json="[]",
        priority=100,
        status="active",
        locked=True,
        current_revision_id=revision_id,
        char_count=14,
    )
    cognitive_db.add(item)
    cognitive_db.flush()
    cognitive_db.add(
        MemoryRevision(
            id=revision_id,
            memory_item_id=item.id,
            operation="add",
            title=item.title,
            content=item.content,
            category=item.category,
            tags_json="[]",
            priority=100,
            status="active",
            locked=True,
            source_turn_ids_json="[]",
            created_by="user",
        )
    )
    job = CognitiveJob(
        id=str(uuid4()),
        job_type="memory_consolidation",
        start_turn_number=1,
        end_turn_number=20,
        status="running",
        memory_version_before=0,
        attempt_count=1,
    )
    cognitive_db.add(job)
    cognitive_db.commit()
    payload = build_job_payload(cognitive_db, job)
    result = CognitiveResult.model_validate(
        {
            "summary": "bad update",
            "memory_operations": [
                {
                    "operation": "update",
                    "memory_ids": [item.id],
                    "content": "replace",
                    "source_turn_ids": [turns[0].id],
                    "expected_revision_ids": {item.id: revision_id},
                }
            ],
            "skill_operations": [],
            "consumed_delta_ids": [],
            "warnings": [],
        }
    )
    with pytest.raises(ValueError, match="locked"):
        apply_result(cognitive_db, job, result, payload)
    cognitive_db.rollback()
    cognitive_db.refresh(item)
    assert item.content == "Do not replace"
    assert cognitive_db.get(CognitiveState, "global").memory_version == 0


def test_claim_and_recovery_are_durable(cognitive_db: Session) -> None:
    seed_completed_turns(cognitive_db)
    job = CognitiveJob(
        id=str(uuid4()),
        job_type="memory_consolidation",
        start_turn_number=1,
        end_turn_number=20,
        status="pending",
        memory_version_before=0,
        attempt_count=0,
    )
    cognitive_db.add(job)
    cognitive_db.commit()
    claimed = claim_next_job(cognitive_db)
    assert claimed is not None and claimed.status == "running" and claimed.attempt_count == 1
    claimed.claimed_at = datetime.now(UTC) - timedelta(minutes=10)
    cognitive_db.commit()
    assert recover_unfinished_jobs(cognitive_db, stale_after_seconds=300) == 1
    cognitive_db.commit()
    cognitive_db.refresh(claimed)
    assert claimed.status == "pending"


def test_memory_management_api_versions_without_deleting_history(client) -> None:
    created = client.post(
        "/api/memory/items",
        json={
            "title": "API memory",
            "content": "initial",
            "category": "preference",
            "tags": ["api"],
            "priority": 60,
        },
    )
    assert created.status_code == 201
    item = created.json()
    updated = client.patch(
        f"/api/memory/items/{item['id']}",
        json={"expected_revision_id": item["current_revision_id"], "content": "updated"},
    )
    assert updated.status_code == 200
    stale = client.patch(
        f"/api/memory/items/{item['id']}",
        json={"expected_revision_id": item["current_revision_id"], "content": "stale overwrite"},
    )
    assert stale.status_code == 409
    assert client.post(f"/api/memory/items/{item['id']}/lock").status_code == 200
    revisions = client.get(f"/api/memory/items/{item['id']}/revisions").json()
    assert len(revisions) == 3
    rolled_back = client.post(f"/api/memory/items/{item['id']}/rollback/{revisions[-1]['id']}")
    assert rolled_back.status_code == 200
    assert len(client.get(f"/api/memory/items/{item['id']}/revisions").json()) == 4
    assert client.post(f"/api/memory/items/{item['id']}/archive").status_code == 200


@pytest.mark.asyncio
async def test_cognitive_event_contract_has_no_fake_turn_or_conversation_ids() -> None:
    queue = cognitive_event_hub.subscribe()
    job = CognitiveJob(
        id=str(uuid4()),
        job_type="memory_consolidation",
        start_turn_number=1,
        end_turn_number=20,
        status="completed",
        memory_version_before=0,
        memory_version_after=1,
        attempt_count=1,
    )
    try:
        await cognitive_event_hub.publish("cognitive.job_completed", job)
        event = await queue.get()
    finally:
        cognitive_event_hub.unsubscribe(queue)
    assert event["event"] == "cognitive.job_completed"
    assert event["job_id"] == job.id
    assert event["data"]["end_turn_number"] == 20
    assert "turn_id" not in event and "conversation_id" not in event
