from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from services.agent.model_provider import ProviderStreamEvent
from services.api.app.db.models import MemoryDelta
from services.api.app.db.session import SessionLocal
from services.memory.realtime_delta import explicit_instruction_priority


class MemoryAwareProvider:
    def __init__(self) -> None:
        self.memory_messages: list[str] = []

    async def stream(
        self, messages: list[dict[str, object]], tools: list[dict[str, object]] | None = None
    ) -> AsyncIterator[ProviderStreamEvent]:
        self.memory_messages = [
            str(message.get("content", ""))
            for message in messages
            if "Current real-time memory instructions" in str(message.get("content", ""))
        ]
        yield ProviderStreamEvent(delta="记忆上下文已检查")
        yield ProviderStreamEvent(input_tokens=20, output_tokens=5)


def _clear_delta() -> None:
    with SessionLocal() as db:
        db.execute(delete(MemoryDelta))
        db.commit()


@pytest.fixture(autouse=True)
def isolated_memory_delta() -> Iterator[None]:
    _clear_delta()
    yield
    _clear_delta()


def _complete(client: TestClient, monkeypatch, conversation_id: str, content: str):
    provider = MemoryAwareProvider()
    monkeypatch.setattr("services.agent.runtime._provider_for", lambda _: provider)
    turn = client.post(
        f"/api/conversations/{conversation_id}/turns", json={"content": content}
    ).json()
    events = []
    with client.websocket_connect(f"/api/ws/turns/{turn['id']}") as websocket:
        while True:
            event = websocket.receive_json()
            events.append(event)
            assert event["event"] != "error", event["data"]
            if event["event"] == "assistant.completed":
                break
    return turn, events, provider


def test_explicit_instruction_is_injected_only_from_the_next_turn(
    client: TestClient, monkeypatch
) -> None:
    conversation = client.post("/api/conversations", json={"title": "实时记忆"}).json()

    first, first_events, first_provider = _complete(
        client, monkeypatch, conversation["id"], "以后不要使用 CLI"
    )
    assert first_provider.memory_messages == []
    delta_event = next(
        event for event in first_events if event["event"] == "memory.delta_created"
    )
    revision_id = delta_event["data"]["memory_delta"]["revision_id"]
    assert delta_event["data"]["memory_delta"]["status"] == "pending"
    assert client.get(f"/api/turns/{first['id']}/execution-trace").json()[
        "memory_revision_ids"
    ] == []

    second, _, second_provider = _complete(
        client, monkeypatch, conversation["id"], "请说明你会采用什么交互方式"
    )
    assert len(second_provider.memory_messages) == 1
    assert "以后不要使用 CLI" in second_provider.memory_messages[0]
    assert client.get(f"/api/turns/{second['id']}/execution-trace").json()[
        "memory_revision_ids"
    ] == [revision_id]

    memory = client.get("/api/memory").json()
    assert memory[0]["raw_content"] == "以后不要使用 CLI"
    assert memory[0]["char_count"] == len("以后不要使用 CLI")
    status = client.get("/api/memory/status").json()
    assert status["active_delta_char_count"] == len("以后不要使用 CLI")
    assert status["delta_char_limit"] == 2_000


def test_capacity_preserves_overflow_and_prefers_recent_correction(client: TestClient) -> None:
    conversation = client.post("/api/conversations", json={"title": "容量"}).json()
    older = "我喜欢" + "甲" * 1_880
    correction = "不是旧规则而是新规则，以后不要忽略" + "乙" * 180
    for content in (older, correction):
        response = client.post(
            f"/api/conversations/{conversation['id']}/turns", json={"content": content}
        )
        assert response.status_code == 201

    items = client.get("/api/memory").json()
    by_content = {item["raw_content"]: item for item in items}
    assert by_content[correction]["status"] == "pending"
    assert by_content[older]["status"] == "deferred_capacity"
    status = client.get("/api/memory/status").json()
    assert status["active_delta_char_count"] <= 2_000
    assert status["deferred_delta_char_count"] == len(older)
    assert status["deferred_count"] == 1


def test_later_created_instruction_does_not_leak_into_an_earlier_pending_turn(
    client: TestClient, monkeypatch
) -> None:
    conversation = client.post("/api/conversations", json={"title": "因果顺序"}).json()
    older_memory = "我喜欢" + "蓝" * 1_880
    client.post(
        f"/api/conversations/{conversation['id']}/turns",
        json={"content": older_memory},
    )
    older_delta = client.get("/api/memory").json()[0]
    earlier = client.post(
        f"/api/conversations/{conversation['id']}/turns",
        json={"content": "先创建但稍后执行的问题"},
    ).json()
    client.post(
        f"/api/conversations/{conversation['id']}/turns",
        json={"content": "不是旧规则而是新规则，以后不要使用红色" + "红" * 180},
    )
    provider = MemoryAwareProvider()
    monkeypatch.setattr("services.agent.runtime._provider_for", lambda _: provider)

    with client.websocket_connect(f"/api/ws/turns/{earlier['id']}") as websocket:
        while True:
            event = websocket.receive_json()
            assert event["event"] != "error", event["data"]
            if event["event"] == "assistant.completed":
                break

    assert len(provider.memory_messages) == 1
    assert older_memory in provider.memory_messages[0]
    assert "以后不要使用红色" not in provider.memory_messages[0]
    assert client.get(f"/api/turns/{earlier['id']}/execution-trace").json()[
        "memory_revision_ids"
    ] == [older_delta["revision_id"]]


def test_duplicate_instruction_is_merged_without_double_counting(client: TestClient) -> None:
    conversation = client.post("/api/conversations", json={"title": "重复"}).json()
    for _ in range(2):
        response = client.post(
            f"/api/conversations/{conversation['id']}/turns",
            json={"content": "请记住，我喜欢可回滚方案"},
        )
        assert response.status_code == 201

    items = client.get("/api/memory").json()
    assert {item["status"] for item in items} == {"pending", "duplicate_merged"}
    assert client.get("/api/memory/status").json()["active_delta_char_count"] == len(
        "请记住，我喜欢可回滚方案"
    )


def test_trigger_detection_is_deterministic() -> None:
    assert explicit_instruction_priority("普通的一次性问题") is None
    assert explicit_instruction_priority("我此前明确要求以后不要使用什么交互方式？") is None
    assert explicit_instruction_priority("我喜欢简洁界面") == 90
    assert explicit_instruction_priority("请记住这条规则") == 96
    assert explicit_instruction_priority("不是蓝色而是绿色") == 100
