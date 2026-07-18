from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ToolExecutionError(RuntimeError):
    """A local tool failure safe to return to the model and frontend."""


class WorkspaceBoundaryError(ToolExecutionError):
    pass


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: dict[str, Any]

    def model_content(self) -> str:
        return json.dumps(
            {"ok": self.ok, **self.data}, ensure_ascii=False, separators=(",", ":")
        )


class WorkspaceToolRuntime:
    def __init__(
        self,
        workspace_root: str | Path,
        *,
        max_read_bytes: int = 1_000_000,
        max_list_entries: int = 500,
    ) -> None:
        root = Path(workspace_root).expanduser().resolve(strict=False)
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve(strict=True)
        self.max_read_bytes = max_read_bytes
        self.max_list_entries = max_list_entries

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": (
                        "List files and directories inside the configured local workspace. "
                        "The path must be relative to the workspace; use an empty string "
                        "for its root."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Workspace-relative directory path.",
                            }
                        },
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": (
                        "Read a UTF-8 text file inside the configured local workspace. "
                        "Absolute paths and parent traversal are not allowed."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Workspace-relative file path.",
                            }
                        },
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": (
                        "Atomically write a UTF-8 text file inside the configured local workspace. "
                        "Set overwrite=true only when replacing an existing file is intended."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Workspace-relative file path.",
                            },
                            "content": {"type": "string", "description": "Complete file content."},
                            "overwrite": {
                                "type": "boolean",
                                "description": "Whether an existing file may be replaced.",
                            },
                        },
                        "required": ["path", "content", "overwrite"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        try:
            if name == "list_directory":
                return ToolResult(ok=True, data=self._list_directory(arguments))
            if name == "read_file":
                return ToolResult(ok=True, data=self._read_file(arguments))
            if name == "write_file":
                return ToolResult(ok=True, data=self._write_file(arguments))
            raise ToolExecutionError(f"Unknown tool: {name}")
        except ToolExecutionError as exc:
            return ToolResult(ok=False, data={"error": str(exc)})

    def _resolve(self, raw_path: object, *, allow_root: bool) -> tuple[Path, str]:
        if not isinstance(raw_path, str):
            raise ToolExecutionError("path must be a string")
        if "\x00" in raw_path:
            raise WorkspaceBoundaryError("path contains an invalid null byte")
        relative = Path(raw_path)
        if relative.is_absolute() or any(part == ".." for part in relative.parts):
            raise WorkspaceBoundaryError("path must stay inside the configured workspace")
        if any(":" in part for part in relative.parts):
            raise WorkspaceBoundaryError(
                "Windows drive and alternate data stream paths are blocked"
            )
        if any(self._is_windows_reserved(part) for part in relative.parts):
            raise WorkspaceBoundaryError("reserved device paths are blocked")
        normalized = relative.as_posix().strip("/")
        if not normalized and not allow_root:
            raise ToolExecutionError("path must identify a file")
        target = (self.root / relative).resolve(strict=False)
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceBoundaryError(
                "path must stay inside the configured workspace"
            ) from exc
        return target, normalized

    def _list_directory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_keys(arguments, {"path"})
        target, normalized = self._resolve(arguments["path"], allow_root=True)
        if not target.exists():
            raise ToolExecutionError("directory does not exist")
        if not target.is_dir():
            raise ToolExecutionError("path is not a directory")
        entries: list[dict[str, Any]] = []
        children = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        truncated = len(children) > self.max_list_entries
        for entry in children[: self.max_list_entries]:
            relative_path = entry.relative_to(self.root).as_posix()
            item: dict[str, Any] = {
                "name": entry.name,
                "path": relative_path,
                "type": "directory" if entry.is_dir() else "file",
            }
            if entry.is_file():
                item["size_bytes"] = entry.stat().st_size
            entries.append(item)
        return {"path": normalized, "entries": entries, "truncated": truncated}

    def _read_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_keys(arguments, {"path"})
        target, normalized = self._resolve(arguments["path"], allow_root=False)
        if not target.exists():
            raise ToolExecutionError("file does not exist")
        if not target.is_file():
            raise ToolExecutionError("path is not a file")
        size = target.stat().st_size
        if size > self.max_read_bytes:
            raise ToolExecutionError(f"file exceeds the {self.max_read_bytes} byte read limit")
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolExecutionError("file is not valid UTF-8 text") from exc
        return {"path": normalized, "content": content, "size_bytes": size}

    def _write_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_keys(arguments, {"path", "content", "overwrite"})
        content = arguments["content"]
        overwrite = arguments["overwrite"]
        if not isinstance(content, str):
            raise ToolExecutionError("content must be a string")
        if not isinstance(overwrite, bool):
            raise ToolExecutionError("overwrite must be a boolean")
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_read_bytes:
            raise ToolExecutionError(f"content exceeds the {self.max_read_bytes} byte write limit")
        target, normalized = self._resolve(arguments["path"], allow_root=False)
        existed = target.exists()
        if target.exists() and target.is_dir():
            raise ToolExecutionError("path is a directory")
        if target.exists() and not overwrite:
            raise ToolExecutionError("file already exists; set overwrite=true to replace it")
        target.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = target.parent.resolve(strict=True)
        try:
            resolved_parent.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceBoundaryError(
                "path must stay inside the configured workspace"
            ) from exc
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=resolved_parent, prefix=".survival-agent-", delete=False
            ) as temporary:
                temporary.write(encoded)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = temporary.name
            os.replace(temporary_path, target)
            temporary_path = None
        finally:
            if temporary_path is not None:
                Path(temporary_path).unlink(missing_ok=True)
        return {"path": normalized, "size_bytes": len(encoded), "overwritten": existed}

    @staticmethod
    def _require_keys(arguments: dict[str, Any], expected: set[str]) -> None:
        if set(arguments) != expected:
            raise ToolExecutionError(
                f"arguments must contain exactly: {', '.join(sorted(expected))}"
            )

    @staticmethod
    def _is_windows_reserved(part: str) -> bool:
        if part.endswith((" ", ".")):
            return True
        stem = part.split(".", 1)[0].upper()
        return stem in {"CON", "PRN", "AUX", "NUL"} or (
            len(stem) == 4
            and stem[:3] in {"COM", "LPT"}
            and stem[3] in "123456789"
        )
