from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).parents[2]
SIDECAR = (
    ROOT
    / "apps"
    / "desktop"
    / "src-tauri"
    / "resources"
    / "sidecar"
    / "survival-agent-api.exe"
)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def request(
    port: int,
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    token: str | None = None,
) -> tuple[int, object | None]:
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Survival-Shutdown-Token"] = token
    call = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(call, timeout=2) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except urllib.error.HTTPError as error:
        return error.code, None


def start(root: Path) -> tuple[subprocess.Popen[bytes], int, str]:
    port = free_port()
    token = uuid.uuid4().hex
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment.pop("SURVIVAL_AGENT_OPENAI_API_KEY", None)
    environment["SURVIVAL_AGENT_DESKTOP_SHUTDOWN_TOKEN"] = token
    process = subprocess.Popen(
        [
            str(SIDECAR),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--data-root",
            str(root),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(200):
        if process.poll() is not None:
            raise AssertionError(f"Sidecar exited before health check: {process.returncode}")
        try:
            if request(port, "/api/health")[0] == 200:
                return process, port, token
        except OSError:
            pass
        time.sleep(0.05)
    process.kill()
    raise AssertionError("Sidecar health check timed out")


def stop(process: subprocess.Popen[bytes], port: int, token: str) -> None:
    assert request(port, "/api/desktop/shutdown", method="POST")[0] == 404
    assert request(port, "/api/desktop/shutdown", method="POST", token=token)[0] == 204
    assert process.wait(timeout=10) == 0


def main() -> None:
    if not SIDECAR.is_file():
        raise AssertionError(f"Sidecar not built: {SIDECAR}")
    temp = Path(tempfile.mkdtemp(prefix="survival-agent-phase9-"))
    try:
        data_root = temp / "SurvivalAgent"
        process, port, token = start(data_root)
        status, model_setting = request(port, "/api/model-settings/main")
        assert status == 200 and isinstance(model_setting, dict)
        assert model_setting["base_url"] == "https://api.a6api.com/v1"
        assert model_setting["model"] == "gpt-5.6-sol"
        status, conversation = request(
            port,
            "/api/conversations",
            method="POST",
            payload={"title": "Phase 9 persistence"},
        )
        assert status == 201 and isinstance(conversation, dict)
        conversation_id = conversation["id"]
        stop(process, port, token)

        assert all(
            (data_root / name).is_dir() for name in ("data", "logs", "workspace", "backups")
        )
        with closing(sqlite3.connect(data_root / "data" / "survival_agent.db")) as database:
            assert database.execute("SELECT version_num FROM alembic_version").fetchone() == (
                "20260719_0008",
            )

        reopened, port, token = start(data_root)
        status, detail = request(port, f"/api/conversations/{conversation_id}")
        assert status == 200 and isinstance(detail, dict)
        assert detail["title"] == "Phase 9 persistence"
        stop(reopened, port, token)
    finally:
        for attempt in range(20):
            try:
                shutil.rmtree(temp)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.1)
    print("PHASE9_SIDECAR_OK")


if __name__ == "__main__":
    main()
