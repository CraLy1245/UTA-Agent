import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from services.agent.model_provider import ProviderStreamEvent
from services.api.app.db.models import (
    Conversation,
    Skill,
    SkillEvolutionEvent,
    SkillRevision,
    SkillUsage,
    Turn,
    TurnExecutionTrace,
)
from services.api.app.db.session import SessionLocal
from services.skills.service import (
    apply_quality_feedback,
    create_candidate,
    create_skill,
    evaluate_candidate,
    promote_candidate,
    retrieve_skills,
)


class SkillAwareProvider:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def stream(self, messages, tools=None):
        self.messages = messages
        yield ProviderStreamEvent(delta="Skill 已执行")
        yield ProviderStreamEvent(input_tokens=12, output_tokens=3)


def _content(label: str) -> str:
    return (
        f"name:{label}\n"
        f"description:{label} workflow\n"
        "applicable_scenarios:\n- phase7-unique repository task\n"
        "safety_constraints:\n- keep workspace boundaries\n"
        "steps:\n- inspect evidence\n- verify result\n"
        "success_criteria:\n- result is evidence-backed"
    )


def _skill(db, label: str = "phase7-skill") -> Skill:
    item = create_skill(
        db,
        name=f"{label}-{uuid4().hex[:6]}",
        description="phase7-unique repository workflow",
        content=_content(label),
        source_turn_ids=[],
        created_by="user",
        reason="test",
        idempotency_key=f"test-create:{uuid4()}",
        allow_single_source=True,
    )
    db.commit()
    return item


def _usage(
    db,
    skill: Skill,
    revision_id: str,
    *,
    feedback: str | None,
    objective: bool = True,
    tokens: int = 100,
) -> SkillUsage:
    conversation = Conversation(id=str(uuid4()), title="Skill test")
    turn = Turn(
        id=str(uuid4()),
        conversation_id=conversation.id,
        user_message_id=str(uuid4()),
        status="completed",
        input_tokens=tokens // 2,
        output_tokens=tokens // 2,
    )
    trace = TurnExecutionTrace(
        id=str(uuid4()),
        turn_id=turn.id,
        model_id="test-model",
        memory_revision_ids_json="[]",
        skill_revision_ids_json=json.dumps([revision_id]),
        tool_names_json="[]",
        provider_raw_usage_json="[]",
        normalized_usage_json="{}",
        input_tokens=tokens // 2,
        output_tokens=tokens // 2,
        latency_ms=1,
        completion_status="completed",
        objective_result_json=json.dumps({"failed_tools": 0 if objective else 1}),
    )
    usage = SkillUsage(
        id=str(uuid4()),
        skill_id=skill.id,
        skill_revision_id=revision_id,
        turn_id=turn.id,
        result="completed",
        feedback=feedback,
        objective_passed=objective,
        input_tokens=tokens // 2,
        output_tokens=tokens // 2,
    )
    db.add(conversation)
    db.flush()
    db.add(turn)
    db.flush()
    db.add(trace)
    db.flush()
    db.add(usage)
    db.flush()
    return usage


def _candidate(db, skill: Skill) -> SkillRevision:
    negative = _usage(db, skill, skill.stable_revision_id, feedback="unsatisfied")
    candidate = create_candidate(
        db,
        skill=skill,
        base_revision_id=skill.stable_revision_id,
        content=_content("improved-phase7-skill") + "\n- incorporate feedback",
        source_turn_ids=[negative.turn_id],
        reason="traceable negative feedback",
        expected_improvement="more reliable verification",
        idempotency_key=f"candidate:{uuid4()}",
    )
    db.commit()
    return candidate


def test_automatic_creation_requires_reuse_threshold_and_user_creation_is_versioned() -> None:
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="three source turns"):
            create_skill(
                db,
                name=f"fragment-{uuid4()}",
                description="one-off",
                content=_content("fragment"),
                source_turn_ids=[str(uuid4())],
                created_by="cognitive_worker",
                reason="one occurrence",
                idempotency_key=f"fragment:{uuid4()}",
            )
        db.rollback()
        skill = _skill(db)
        revision = db.get(SkillRevision, skill.stable_revision_id)
        assert revision is not None and revision.status == "stable"
        assert revision.content == skill.content
        assert db.scalar(
            select(SkillEvolutionEvent).where(SkillEvolutionEvent.skill_id == skill.id)
        )


def test_locked_skill_rejects_candidate_and_candidate_preserves_safety() -> None:
    with SessionLocal() as db:
        skill = _skill(db, "locked")
        negative = _usage(db, skill, skill.stable_revision_id, feedback="unsatisfied")
        skill.locked = True
        db.commit()
        with pytest.raises(ValueError, match="locked"):
            create_candidate(
                db,
                skill=skill,
                base_revision_id=skill.stable_revision_id,
                content=_content("candidate"),
                source_turn_ids=[negative.turn_id],
                reason="negative",
                expected_improvement="quality",
                idempotency_key=f"locked-candidate:{uuid4()}",
            )
        skill.locked = False
        with pytest.raises(ValueError, match="safety constraints"):
            create_candidate(
                db,
                skill=skill,
                base_revision_id=skill.stable_revision_id,
                content="steps:\n- shortcut\nsuccess_criteria:\n- done",
                source_turn_ids=[negative.turn_id],
                reason="negative",
                expected_improvement="quality",
                idempotency_key=f"unsafe-candidate:{uuid4()}",
            )


def test_deterministic_nine_to_one_route_is_replayable() -> None:
    with SessionLocal() as db:
        skill = _skill(db, "router")
        candidate = _candidate(db, skill)
        for _ in range(8):
            _usage(db, skill, skill.stable_revision_id, feedback="satisfied")
        db.commit()
        selected = retrieve_skills(db, query=f"{skill.name} repository task")
        matching = next(item for item in selected if item.skill_id == skill.id)
        assert matching.revision_id == candidate.id
        assert matching.revision_status == "candidate"
        assert retrieve_skills(db, query="unrelated astronomy") == []


def test_candidate_promotes_only_after_five_better_uses() -> None:
    with SessionLocal() as db:
        skill = _skill(db, "promotion")
        candidate = _candidate(db, skill)
        for rating in ("satisfied", "unsatisfied", "satisfied", "unsatisfied", "satisfied"):
            _usage(db, skill, skill.stable_revision_id, feedback=rating, tokens=120)
        for _ in range(4):
            _usage(db, skill, candidate.id, feedback="satisfied", tokens=130)
        db.commit()
        assert evaluate_candidate(db, skill) == "collecting"
        _usage(db, skill, candidate.id, feedback="satisfied", tokens=130)
        db.flush()
        assert evaluate_candidate(db, skill) == "promoted"
        db.commit()
        assert skill.stable_revision_id == candidate.id
        assert skill.candidate_revision_id is None
        assert skill.promotion_observation_remaining == 5


def test_candidate_rejects_after_two_failures_and_feedback_modification_recomputes() -> None:
    with SessionLocal() as db:
        skill = _skill(db, "rejection")
        candidate = _candidate(db, skill)
        first = _usage(db, skill, candidate.id, feedback="unsatisfied", objective=False)
        second = _usage(db, skill, candidate.id, feedback="unsatisfied", objective=False)
        db.commit()
        assert evaluate_candidate(db, skill) == "rejected"
        db.commit()
        assert skill.candidate_revision_id is None
        assert db.get(SkillRevision, candidate.id).status == "rejected"

        first.feedback = None
        second.feedback = None
        db.commit()
        apply_quality_feedback(db, turn_id=first.turn_id, rating="satisfied")
        apply_quality_feedback(db, turn_id=first.turn_id, rating="unsatisfied")
        db.commit()
        assert first.feedback == "unsatisfied"
        assert skill.success_count == 0
        assert skill.failure_count == 2


def test_promoted_revision_auto_rolls_back_after_two_unsatisfied_uses() -> None:
    with SessionLocal() as db:
        skill = _skill(db, "rollback")
        old_stable = skill.stable_revision_id
        candidate = _candidate(db, skill)
        promote_candidate(db, skill, reason="manual test promotion", automatic=False)
        first = _usage(db, skill, candidate.id, feedback=None)
        second = _usage(db, skill, candidate.id, feedback=None)
        db.commit()
        apply_quality_feedback(db, turn_id=first.turn_id, rating="unsatisfied")
        apply_quality_feedback(db, turn_id=second.turn_id, rating="unsatisfied")
        db.commit()
        assert skill.stable_revision_id == old_stable
        assert db.get(SkillRevision, candidate.id).status == "rejected_after_promotion"


def test_skill_api_persists_edit_lock_archive_restore_and_history(client) -> None:
    created = client.post(
        "/api/skills",
        json={
            "name": f"api-skill-{uuid4().hex[:6]}",
            "description": "phase7 API workflow",
            "content": _content("api"),
            "reason": "user requested reusable Skill",
        },
    )
    assert created.status_code == 201
    skill = created.json()
    updated = client.patch(
        f"/api/skills/{skill['id']}",
        json={
            "expected_revision_id": skill["stable_revision_id"],
            "content": _content("api-updated"),
            "reason": "improve workflow",
        },
    )
    assert updated.status_code == 200
    assert client.post(f"/api/skills/{skill['id']}/lock").json()["locked"] is True
    blocked = client.post(f"/api/skills/{skill['id']}/archive")
    assert blocked.status_code == 422
    assert client.post(f"/api/skills/{skill['id']}/unlock").status_code == 200
    assert client.post(f"/api/skills/{skill['id']}/archive").json()["status"] == "archived"
    assert client.post(f"/api/skills/{skill['id']}/restore").json()["status"] == "active"
    evolution = client.get(f"/api/skills/{skill['id']}/evolution")
    assert evolution.status_code == 200
    assert len(evolution.json()["revisions"]) == 2
    assert len(evolution.json()["events"]) >= 6


def test_completed_turn_trace_records_exact_loaded_revision(client, monkeypatch) -> None:
    unique = f"trace-keyword-{uuid4().hex[:8]}"
    created = client.post(
        "/api/skills",
        json={
            "name": unique,
            "description": f"Handle {unique} repository requests",
            "content": _content(unique),
            "reason": "trace acceptance",
        },
    ).json()
    provider = SkillAwareProvider()
    monkeypatch.setattr("services.agent.runtime._provider_for", lambda _: provider)
    conversation = client.post("/api/conversations", json={"title": "Skill trace"}).json()
    turn = client.post(
        f"/api/conversations/{conversation['id']}/turns",
        json={"content": f"Please execute {unique} repository task"},
    ).json()
    with client.websocket_connect(f"/api/ws/turns/{turn['id']}") as websocket:
        while websocket.receive_json()["event"] != "assistant.completed":
            pass
    trace = client.get(f"/api/turns/{turn['id']}/execution-trace").json()
    assert created["stable_revision_id"] in trace["skill_revision_ids"]
    assert len(trace["skill_revision_ids"]) <= 3
    assert any(
        created["stable_revision_id"] in str(message.get("content"))
        for message in provider.messages
    )
    evolution = client.get(f"/api/skills/{created['id']}/evolution").json()
    assert evolution["usages"][0]["turn_id"] == turn["id"]
