from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient


def migrate() -> None:
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        check=True,
        cwd=Path(__file__).parents[2],
        env=os.environ,
        capture_output=True,
        text=True,
    )


def main() -> None:
    migrate()
    from services.agent import runtime
    from services.agent.model_provider import ProviderStreamEvent
    from services.api.app.main import app
    from services.memory import cognitive

    class FlowProvider:
        saw_consolidated_memory = False

        async def stream(
            self,
            messages: list[dict[str, object]],
            tools: list[dict[str, object]] | None = None,
        ) -> AsyncIterator[ProviderStreamEvent]:
            serialized = json.dumps(messages, ensure_ascii=False)
            if "请记住以后回答保持简短" in serialized and "第22回合" in serialized:
                self.saw_consolidated_memory = True
            yield ProviderStreamEvent(delta="完成")
            yield ProviderStreamEvent(input_tokens=10, output_tokens=2)

    provider = FlowProvider()
    runtime._provider_for = lambda _: provider

    async def cognitive_result(payload: dict[str, object]) -> cognitive.CognitiveResult:
        delta = payload["realtime_delta"][0]  # type: ignore[index]
        source = payload["turns"][0]["turn_id"]  # type: ignore[index]
        return cognitive.CognitiveResult.model_validate(
            {
                "summary": "E2E consolidated explicit preference",
                "memory_operations": [
                    {
                        "operation": "add",
                        "title": "回答风格",
                        "content": delta["content"],
                        "category": "preference",
                        "priority": 90,
                        "source_turn_ids": [source],
                    }
                ],
                "skill_operations": [],
                "consumed_delta_ids": [delta["id"]],
                "warnings": [],
            }
        )

    cognitive.request_cognitive_result = cognitive_result

    with TestClient(app) as client:
        conversation = client.post("/api/conversations", json={"title": "Phase 8 E2E"}).json()
        for number in range(1, 22):
            content = "请记住以后回答保持简短" if number == 1 else f"第{number}回合"
            turn = client.post(
                f"/api/conversations/{conversation['id']}/turns", json={"content": content}
            ).json()
            with client.websocket_connect(f"/api/ws/turns/{turn['id']}") as websocket:
                while websocket.receive_json()["event"] != "assistant.completed":
                    pass

        # The 21st foreground turn completes whether the 1-20 Worker is pending or running.
        for _ in range(50):
            jobs = client.get("/api/cognitive-jobs").json()
            if jobs and jobs[0]["status"] == "completed":
                break
            client.post("/api/cognitive-jobs/run")
            time.sleep(0.05)
        else:
            raise AssertionError("cognitive job did not complete")

        turn22 = client.post(
            f"/api/conversations/{conversation['id']}/turns", json={"content": "第22回合"}
        ).json()
        with client.websocket_connect(f"/api/ws/turns/{turn22['id']}") as websocket:
            while websocket.receive_json()["event"] != "assistant.completed":
                pass
        assert provider.saw_consolidated_memory

        before = client.get("/api/survival/status").json()["accounts"]
        feedback = client.post(
            f"/api/turns/{turn22['id']}/feedback",
            json={"rating": "satisfied", "comment": "E2E passed"},
        ).json()
        assert feedback["survival_reward"]["granted_now"] is True
        assert client.post(
            f"/api/turns/{turn22['id']}/feedback",
            json={"rating": "satisfied", "comment": "duplicate"},
        ).json()["survival_reward"]["granted_now"] is False
        after = client.get("/api/survival/status").json()["accounts"]
        assert before != after
        exported = client.get("/api/data/export")
        assert exported.status_code == 200
        assert len(exported.json()["tables"]["turns"]) == 22

    # A new application lifespan simulates closing and reopening the local application.
    with TestClient(app) as reopened:
        detail = reopened.get(f"/api/conversations/{conversation['id']}")
        assert detail.status_code == 200
        assert len(detail.json()["messages"]) == 44
        memory = reopened.get("/api/memory/items").json()
        assert any(item["content"] == "请记住以后回答保持简短" for item in memory)
        assert reopened.get("/api/cognitive-jobs").json()[0]["status"] == "completed"

    print("PHASE8_E2E_OK")


if __name__ == "__main__":
    if "SURVIVAL_AGENT_DATABASE_URL" not in os.environ:
        sys.exit("SURVIVAL_AGENT_DATABASE_URL is required")
    main()
