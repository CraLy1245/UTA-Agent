import os
from pathlib import Path

from services.desktop_sidecar import configure_environment, ensure_user_directories


def test_desktop_directories_and_environment(monkeypatch, tmp_path: Path) -> None:
    for name in (
        "SURVIVAL_AGENT_ENVIRONMENT",
        "SURVIVAL_AGENT_DATABASE_URL",
        "SURVIVAL_AGENT_WORKSPACE_PATH",
        "SURVIVAL_AGENT_LOG_DIRECTORY",
        "SURVIVAL_AGENT_CORS_ORIGINS",
    ):
        monkeypatch.delenv(name, raising=False)

    directories = configure_environment(tmp_path / "SurvivalAgent")

    assert set(directories) == {"data", "logs", "workspace", "backups"}
    assert all(path.is_dir() for path in directories.values())
    expected_database = (tmp_path / "SurvivalAgent" / "data" / "survival_agent.db").as_posix()
    assert expected_database in os.environ["SURVIVAL_AGENT_DATABASE_URL"]
    assert os.environ["SURVIVAL_AGENT_ENVIRONMENT"] == "desktop"


def test_ensure_user_directories_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "SurvivalAgent"
    assert ensure_user_directories(root) == ensure_user_directories(root)
