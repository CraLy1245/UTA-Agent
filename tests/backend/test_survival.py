from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from services.agent.model_provider import ProviderStreamEvent


class BalanceAwareProvider:
    def __init__(self, input_tokens: int = 1_000, output_tokens: int = 300) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.saw_balance = False

    async def stream(
        self, messages: list[dict[str, object]], tools: list[dict[str, object]] | None = None
    ) -> AsyncIterator[ProviderStreamEvent]:
        self.saw_balance = any(
            "Runtime survival balance" in str(message.get("content", "")) for message in messages
        )
        yield ProviderStreamEvent(delta="余额已读取")
        yield ProviderStreamEvent(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            raw_usage={
                "prompt_tokens": self.input_tokens,
                "completion_tokens": self.output_tokens,
                "prompt_tokens_details": {"cached_tokens": self.input_tokens // 2},
                "completion_tokens_details": {"reasoning_tokens": self.output_tokens // 2},
            },
        )


class MissingUsageProvider:
    async def stream(
        self, messages: list[dict[str, object]], tools: list[dict[str, object]] | None = None
    ) -> AsyncIterator[ProviderStreamEvent]:
        yield ProviderStreamEvent(delta="Provider 未返回 usage，但回答仍安全完成")


def _balances(client: TestClient) -> dict[str, int]:
    payload = client.get("/api/survival/status").json()
    return {account["account_type"]: account["balance_units"] for account in payload["accounts"]}


def _complete_turn(
    client: TestClient, monkeypatch, provider: BalanceAwareProvider
) -> tuple[str, str]:
    monkeypatch.setattr("services.agent.runtime._provider_for", lambda _: provider)
    conversation = client.post("/api/conversations", json={"title": "生存测试"}).json()
    turn = client.post(
        f"/api/conversations/{conversation['id']}/turns",
        json={"content": "请读取余额后回答"},
    ).json()
    with client.websocket_connect(f"/api/ws/turns/{turn['id']}") as websocket:
        while True:
            event = websocket.receive_json()
            assert event["event"] != "error", event["data"]
            if event["event"] == "assistant.completed":
                break
    return conversation["id"], turn["id"]


def test_completed_turn_debits_units_and_persists_immutable_trace(
    client: TestClient, monkeypatch
) -> None:
    before = _balances(client)
    provider = BalanceAwareProvider()
    conversation_id, turn_id = _complete_turn(client, monkeypatch, provider)
    after = _balances(client)

    assert provider.saw_balance is True
    assert after["read"] == before["read"] - 100_000
    assert after["output"] == before["output"] - 30_000
    trace = client.get(f"/api/turns/{turn_id}/execution-trace").json()
    assert trace["input_tokens"] == 1_000
    assert trace["output_tokens"] == 300
    assert trace["normalized_usage"]["usage_complete"] is True
    assert trace["provider_raw_usage"][0]["prompt_tokens_details"]["cached_tokens"] == 500
    assert trace["memory_revision_ids"] == []
    assert trace["skill_revision_ids"] == []

    status = client.get("/api/survival/status", params={"conversation_id": conversation_id}).json()
    assert status["latest_turn"]["read_change_units"] == -100_000


def test_satisfied_reward_is_exactly_108_percent_and_idempotent(
    client: TestClient, monkeypatch
) -> None:
    conversation_id, turn_id = _complete_turn(client, monkeypatch, BalanceAwareProvider())
    after_debit = _balances(client)

    first = client.post(
        f"/api/turns/{turn_id}/feedback",
        json={"rating": "satisfied", "comment": "符合预期"},
    )
    assert first.status_code == 200
    assert first.json()["quality_feedback"]["rating"] == "satisfied"
    assert first.json()["survival_reward"]["granted_now"] is True
    reward_amounts = {
        item["account_type"]: item["amount_units"]
        for item in first.json()["survival_reward"]["transactions"]
    }
    assert reward_amounts == {"read": 108_000, "output": 32_400}
    after_first = _balances(client)
    assert after_first["read"] == after_debit["read"] + 108_000
    assert after_first["output"] == after_debit["output"] + 32_400

    repeated = client.post(f"/api/turns/{turn_id}/feedback", json={"rating": "satisfied"})
    assert repeated.status_code == 200
    assert repeated.json()["survival_reward"]["granted_now"] is False
    assert _balances(client) == after_first

    changed = client.post(
        f"/api/turns/{turn_id}/feedback",
        json={"rating": "unsatisfied", "comment": "后来发现不完整"},
    )
    assert changed.status_code == 200
    assert changed.json()["survival_reward"]["transactions"] == []
    assert _balances(client) == after_first
    feedback_history = client.get(f"/api/conversations/{conversation_id}").json()["feedback_events"]
    assert [event["rating"] for event in feedback_history] == [
        "satisfied",
        "satisfied",
        "unsatisfied",
    ]
    assert feedback_history[-1]["comment"] == "后来发现不完整"

    transactions = client.get("/api/survival/transactions", params={"limit": 20}).json()
    turn_transactions = [item for item in transactions if item["turn_id"] == turn_id]
    debit_transactions = [
        item for item in turn_transactions if item["transaction_type"] == "usage_debit"
    ]
    assert len(debit_transactions) == 2
    assert (
        len([item for item in turn_transactions if item["transaction_type"] == "survival_reward"])
        == 2
    )


def test_unsatisfied_feedback_never_rewards_tokens(client: TestClient, monkeypatch) -> None:
    _, turn_id = _complete_turn(client, monkeypatch, BalanceAwareProvider(11, 4))
    before_feedback = _balances(client)

    response = client.post(
        f"/api/turns/{turn_id}/feedback",
        json={"rating": "unsatisfied", "comment": "没有满足要求"},
    )

    assert response.status_code == 200
    assert response.json()["quality_feedback"]["comment"] == "没有满足要求"
    assert response.json()["survival_reward"] == {
        "granted_now": False,
        "transactions": [],
    }
    assert _balances(client) == before_feedback


def test_missing_usage_completes_with_zero_debit_and_auditable_trace(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr("services.agent.runtime._provider_for", lambda _: MissingUsageProvider())
    conversation = client.post("/api/conversations", json={"title": "缺失 Usage"}).json()
    turn = client.post(
        f"/api/conversations/{conversation['id']}/turns", json={"content": "请回答"}
    ).json()
    before = _balances(client)

    with client.websocket_connect(f"/api/ws/turns/{turn['id']}") as websocket:
        while True:
            event = websocket.receive_json()
            assert event["event"] != "error", event["data"]
            if event["event"] == "assistant.completed":
                break

    assert _balances(client) == before
    trace = client.get(f"/api/turns/{turn['id']}/execution-trace").json()
    assert trace["input_tokens"] == 0
    assert trace["output_tokens"] == 0
    assert trace["normalized_usage"]["usage_complete"] is False
    assert trace["provider_raw_usage"] == []
