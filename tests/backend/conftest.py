import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DATABASE = Path("data/test_survival_agent.db")
os.environ["SURVIVAL_AGENT_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield
    from services.api.app.db.session import engine

    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        Path(f"{TEST_DATABASE}{suffix}").unlink(missing_ok=True)


@pytest.fixture()
def client(migrated_database: None) -> Iterator[TestClient]:
    from services.api.app.main import app

    with TestClient(app) as test_client:
        yield test_client
