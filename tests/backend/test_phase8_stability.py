import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from services.api.app.core.logging import ContextDefaults, RedactingFormatter
from services.api.app.core.security import REDACTED, redact_text, redact_value
from services.api.app.db.models import CognitiveJob
from services.api.app.db.session import build_engine
from services.memory.cognitive import claim_next_job, recover_unfinished_jobs


@pytest.fixture(scope="module")
def stability_sessions(tmp_path_factory: pytest.TempPathFactory):
    directory = tmp_path_factory.mktemp("phase8-migrated")
    database = directory / "stability.db"
    url = f"sqlite:///{database.as_posix()}"
    environment = {**os.environ, "SURVIVAL_AGENT_DATABASE_URL": url}
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        check=True,
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
    )
    engine = build_engine(url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory, database
    engine.dispose()


def _job(*, status: str = "pending", start: int = 1001) -> CognitiveJob:
    return CognitiveJob(
        id=str(uuid4()),
        job_type="memory_consolidation",
        start_turn_number=start,
        end_turn_number=start + 19,
        status=status,
        memory_version_before=0,
        attempt_count=0,
        created_at=datetime.now(UTC),
    )


def test_redaction_covers_exact_keys_headers_and_nested_export_values() -> None:
    secret = "vendor-secret-value-123"
    original = {
        "message": f"Authorization: Bearer {secret} and sk-phase8secret123456",
        "nested": {"api_key": secret, "safe": "keep"},
    }
    sanitized = redact_value(original, secrets=(secret,))
    serialized = json.dumps(sanitized)
    assert secret not in serialized
    assert "sk-phase8secret123456" not in serialized
    assert sanitized["nested"]["api_key"] == REDACTED
    assert sanitized["nested"]["safe"] == "keep"


def test_log_formatter_never_writes_credentials() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextDefaults())
    handler.setFormatter(
        RedactingFormatter(
            "%(levelname)s conversation_id=%(conversation_id)s turn_id=%(turn_id)s "
            "job_id=%(job_id)s %(message)s"
        )
    )
    logger = logging.getLogger("phase8-redaction-test")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.info("Authorization=Bearer sk-phase8logsecret123456")
    output = stream.getvalue()
    assert "sk-phase8logsecret123456" not in output
    assert REDACTED in output
    assert "conversation_id=-" in output


def test_two_workers_cannot_claim_the_same_durable_job(stability_sessions) -> None:
    factory, _ = stability_sessions
    job = _job(start=2001)
    with factory() as db:
        db.add(job)
        db.commit()

    def claim() -> str | None:
        with factory() as db:
            claimed = claim_next_job(db)
            return claimed.id if claimed else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: claim(), range(2)))
    assert results.count(job.id) == 1


def test_delayed_retry_does_not_block_another_ready_job(stability_sessions) -> None:
    factory, _ = stability_sessions
    delayed = _job(status="conflict", start=3001)
    delayed.next_attempt_at = datetime.now(UTC) + timedelta(hours=1)
    ready = _job(start=3021)
    ready.created_at = delayed.created_at + timedelta(seconds=1)
    with factory() as db:
        db.add_all([delayed, ready])
        db.commit()
        claimed = claim_next_job(db)
        assert claimed is not None and claimed.id == ready.id


def test_restart_reclaims_all_previous_process_claims(stability_sessions) -> None:
    factory, _ = stability_sessions
    job = _job(status="running", start=4001)
    job.claimed_at = datetime.now(UTC)
    with factory() as db:
        db.add(job)
        db.commit()
        assert recover_unfinished_jobs(db, stale_after_seconds=0) >= 1
        db.commit()
    with factory() as reopened:
        recovered = reopened.get(CognitiveJob, job.id)
        assert recovered is not None
        assert recovered.status == "pending"
        assert recovered.claimed_at is None


def test_committed_data_survives_engine_disposal(stability_sessions) -> None:
    factory, database = stability_sessions
    job = _job(start=5001)
    with factory() as db:
        db.add(job)
        db.commit()
    reopened_engine = build_engine(f"sqlite:///{database.as_posix()}")
    try:
        with Session(reopened_engine) as reopened:
            persisted_id = reopened.scalar(
                select(CognitiveJob.id).where(CognitiveJob.id == job.id)
            )
            integrity = reopened.connection().exec_driver_sql("PRAGMA integrity_check").scalar_one()
            assert persisted_id == job.id
            assert integrity == "ok"
    finally:
        reopened_engine.dispose()


def test_export_is_consistent_and_redacts_credentials(client) -> None:
    exposed = "sk-phase8exportsecret123456"
    created = client.post("/api/conversations", json={"title": f"secret {exposed}"})
    assert created.status_code == 201
    response = client.get("/api/data/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]
    assert exposed not in response.text
    payload = response.json()
    assert payload["format"] == "survival-agent-export"
    assert "api_key_env" not in json.dumps(payload["tables"]["model_settings"])
    assert any(REDACTED in row["title"] for row in payload["tables"]["conversations"])


def test_redact_text_preserves_safe_provider_errors() -> None:
    assert redact_text("Provider request timed out") == "Provider request timed out"


def test_complete_phase8_e2e_flow_runs_in_a_fresh_process(tmp_path: Path) -> None:
    database = tmp_path / "phase8-e2e.db"
    environment = {
        **os.environ,
        "SURVIVAL_AGENT_DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "SURVIVAL_AGENT_LOG_DIRECTORY": str(tmp_path / "logs"),
    }
    result = subprocess.run(
        ["uv", "run", "python", "tests/e2e/phase8_backend_flow.py"],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PHASE8_E2E_OK" in result.stdout
