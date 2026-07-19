from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


def default_data_root() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is not available")
    return Path(appdata) / "SurvivalAgent"


def ensure_user_directories(root: Path) -> dict[str, Path]:
    directories = {
        name: root / name for name in ("data", "logs", "workspace", "backups")
    }
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    return directories


def configure_environment(root: Path) -> dict[str, Path]:
    directories = ensure_user_directories(root)
    database_path = (directories["data"] / "survival_agent.db").resolve()
    os.environ["SURVIVAL_AGENT_ENVIRONMENT"] = "desktop"
    os.environ["SURVIVAL_AGENT_DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    os.environ["SURVIVAL_AGENT_WORKSPACE_PATH"] = str(directories["workspace"].resolve())
    os.environ["SURVIVAL_AGENT_LOG_DIRECTORY"] = str(directories["logs"].resolve())
    os.environ["SURVIVAL_AGENT_CORS_ORIGINS"] = (
        '["tauri://localhost","http://tauri.localhost","https://tauri.localhost"]'
    )
    return directories


def bundle_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root) if frozen_root else Path(__file__).resolve().parents[1]


def migrate_database() -> None:
    from alembic import command
    from alembic.config import Config

    root = bundle_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Survival Agent desktop API sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--data-root", type=Path, default=None)
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    root = (args.data_root or default_data_root()).resolve()
    configure_environment(root)
    migrate_database()

    import uvicorn
    from fastapi import Header, HTTPException, Response

    from services.api.app.main import app

    shutdown_token = os.environ.pop("SURVIVAL_AGENT_DESKTOP_SHUTDOWN_TOKEN", "")
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=args.host,
            port=args.port,
            log_level="warning",
            access_log=False,
        )
    )

    @app.post("/api/desktop/shutdown", include_in_schema=False)
    async def desktop_shutdown(
        x_survival_shutdown_token: str | None = Header(default=None),
    ) -> Response:
        if not shutdown_token or x_survival_shutdown_token != shutdown_token:
            raise HTTPException(status_code=404, detail="Not found")
        asyncio.get_running_loop().call_soon(setattr, server, "should_exit", True)
        return Response(status_code=204)

    server.run()


if __name__ == "__main__":
    run()
