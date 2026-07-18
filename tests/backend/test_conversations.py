import asyncio
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from services.agent.model_provider import ProviderStreamEvent, ProviderToolCallDelta
from services.agent.tool_runtime import WorkspaceToolRuntime


class FakeProvider:
    async def stream(
        self, _: list[dict[str, object]], tools: list[dict[str, object]] | None = None
    ) -> AsyncIterator[ProviderStreamEvent]:
        assert tools
        yield ProviderStreamEvent(delta="真实")
        yield ProviderStreamEvent(delta="流式回答")
        yield ProviderStreamEvent(input_tokens=11, output_tokens=4)


class SlowProvider:
    async def stream(
        self, _: list[dict[str, object]], tools: list[dict[str, object]] | None = None
    ) -> AsyncIterator[ProviderStreamEvent]:
        yield ProviderStreamEvent(delta="开始")
        await asyncio.sleep(0.2)
        yield ProviderStreamEvent(delta="不应保存")


class ToolLoopProvider:
    def __init__(self, path: str = "notes/phase3.txt") -> None:
        self.calls = 0
        self.path = path
        self.received_tool_result: str | None = None

    async def stream(
        self, messages: list[dict[str, object]], tools: list[dict[str, object]] | None = None
    ) -> AsyncIterator[ProviderStreamEvent]:
        assert tools
        self.calls += 1
        if self.calls == 1:
            arguments = (
                '{"path":"../outside.txt"}'
                if self.path.startswith("..")
                else '{"path":"notes/phase3.txt","content":"persisted","overwrite":false}'
            )
            name = "read_file" if self.path.startswith("..") else "write_file"
            yield ProviderStreamEvent(
                tool_calls=(
                    ProviderToolCallDelta(index=0, id="call-1", name=name),
                    ProviderToolCallDelta(index=0, arguments=arguments),
                )
            )
            yield ProviderStreamEvent(input_tokens=10, output_tokens=2)
            return
        self.received_tool_result = str(messages[-1]["content"])
        yield ProviderStreamEvent(delta="工具执行完成")
        yield ProviderStreamEvent(input_tokens=20, output_tokens=3)


def _create_turn(client: TestClient) -> tuple[str, str]:
    conversation = client.post("/api/conversations", json={"title": "新对话"}).json()
    turn = client.post(
        f"/api/conversations/{conversation['id']}/turns", json={"content": "请回答"}
    ).json()
    return conversation["id"], turn["id"]


def test_conversation_crud_persists_messages(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("services.agent.runtime._provider_for", lambda _: FakeProvider())
    conversation_id, turn_id = _create_turn(client)

    with client.websocket_connect(f"/api/ws/turns/{turn_id}") as websocket:
        events = []
        while True:
            event = websocket.receive_json()
            events.append(event["event"])
            if event["event"] == "assistant.completed":
                break

    assert events == [
        "turn.started",
        "assistant.delta",
        "assistant.delta",
        "usage.updated",
        "balance.updated",
        "assistant.completed",
    ]
    detail = client.get(f"/api/conversations/{conversation_id}").json()
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][-1]["content"] == "真实流式回答"
    assert client.get(f"/api/turns/{turn_id}").json()["status"] == "completed"


def test_cancelled_turn_does_not_persist_assistant_message(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("services.agent.runtime._provider_for", lambda _: SlowProvider())
    conversation_id, turn_id = _create_turn(client)

    with client.websocket_connect(f"/api/ws/turns/{turn_id}") as websocket:
        assert websocket.receive_json()["event"] == "turn.started"
        assert websocket.receive_json()["event"] == "assistant.delta"
        response = client.post(f"/api/turns/{turn_id}/cancel")
        assert response.status_code == 200
        assert websocket.receive_json()["event"] == "assistant.cancelled"

    detail = client.get(f"/api/conversations/{conversation_id}").json()
    assert [message["role"] for message in detail["messages"]] == ["user"]
    assert client.get(f"/api/turns/{turn_id}").json()["status"] == "cancelled"


def test_missing_api_key_fails_safely_and_can_regenerate(client: TestClient) -> None:
    _, turn_id = _create_turn(client)
    with client.websocket_connect(f"/api/ws/turns/{turn_id}") as websocket:
        event = websocket.receive_json()
    assert event["event"] == "error"
    assert "OPENAI_API_KEY" in event["data"]["message"]
    assert client.get(f"/api/turns/{turn_id}").json()["status"] == "failed"

    regenerated = client.post(f"/api/turns/{turn_id}/regenerate")
    assert regenerated.status_code == 201
    assert regenerated.json()["status"] == "pending"


def test_model_setting_never_accepts_or_returns_api_key(client: TestClient) -> None:
    response = client.put(
        "/api/model-settings/main",
        json={
            "base_url": "https://provider.example/v1",
            "model": "compatible-model",
            "timeout_seconds": 60,
            "max_output_tokens": 2048,
            "temperature": None,
            "enabled": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["base_url"] == "https://provider.example/v1"
    assert payload["api_key_env"] == "OPENAI_API_KEY"
    assert "api_key" not in payload


def test_tool_loop_persists_events_and_returns_result_to_model(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    provider = ToolLoopProvider()
    monkeypatch.setattr("services.agent.runtime._provider_for", lambda _: provider)
    monkeypatch.setattr(
        "services.agent.runtime._tool_runtime", lambda: WorkspaceToolRuntime(tmp_path)
    )
    conversation_id, turn_id = _create_turn(client)

    with client.websocket_connect(f"/api/ws/turns/{turn_id}") as websocket:
        events = []
        while True:
            event = websocket.receive_json()
            events.append(event["event"])
            if event["event"] == "assistant.completed":
                break

    assert events == [
        "turn.started",
        "tool.started",
        "tool.completed",
        "assistant.delta",
        "usage.updated",
        "balance.updated",
        "assistant.completed",
    ]
    assert (tmp_path / "notes/phase3.txt").read_text(encoding="utf-8") == "persisted"
    assert provider.received_tool_result is not None
    assert '"ok":true' in provider.received_tool_result
    detail = client.get(f"/api/conversations/{conversation_id}").json()
    assert detail["tool_executions"][0]["status"] == "completed"
    turn = client.get(f"/api/turns/{turn_id}").json()
    assert turn["input_tokens"] == 30
    assert turn["output_tokens"] == 5


def test_path_escape_is_persisted_as_tool_failure_but_model_can_finish(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    provider = ToolLoopProvider(path="../outside.txt")
    monkeypatch.setattr("services.agent.runtime._provider_for", lambda _: provider)
    monkeypatch.setattr(
        "services.agent.runtime._tool_runtime", lambda: WorkspaceToolRuntime(tmp_path)
    )
    conversation_id, turn_id = _create_turn(client)

    with client.websocket_connect(f"/api/ws/turns/{turn_id}") as websocket:
        events = []
        while True:
            event = websocket.receive_json()
            events.append(event["event"])
            if event["event"] == "assistant.completed":
                break

    assert "tool.failed" in events
    assert provider.received_tool_result is not None
    assert '"ok":false' in provider.received_tool_result
    detail = client.get(f"/api/conversations/{conversation_id}").json()
    execution = detail["tool_executions"][0]
    assert execution["status"] == "failed"
    assert "inside the configured workspace" in execution["error_message"]
