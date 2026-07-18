from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from services.api.app.core.config import get_settings

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolStatus(BaseModel):
    enabled: bool
    workspace_path: str
    available_tools: list[str]


@router.get("/status", response_model=ToolStatus)
def get_tool_status() -> ToolStatus:
    settings = get_settings()
    return ToolStatus(
        enabled=settings.tools_enabled,
        workspace_path=str(Path(settings.workspace_path).expanduser().resolve(strict=False)),
        available_tools=["list_directory", "read_file", "write_file"]
        if settings.tools_enabled
        else [],
    )
