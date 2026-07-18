from pathlib import Path

from services.agent.tool_runtime import WorkspaceToolRuntime


def test_workspace_tools_list_read_and_write(tmp_path: Path) -> None:
    tools = WorkspaceToolRuntime(tmp_path)

    written = tools.execute(
        "write_file", {"path": "notes/result.txt", "content": "hello", "overwrite": False}
    )
    listed = tools.execute("list_directory", {"path": "notes"})
    read = tools.execute("read_file", {"path": "notes/result.txt"})

    assert written.ok is True
    assert written.data["overwritten"] is False
    assert listed.data["entries"] == [
        {"name": "result.txt", "path": "notes/result.txt", "type": "file", "size_bytes": 5}
    ]
    assert read.data == {"path": "notes/result.txt", "content": "hello", "size_bytes": 5}


def test_workspace_tools_block_escape_and_unsafe_overwrite(tmp_path: Path) -> None:
    tools = WorkspaceToolRuntime(tmp_path)
    (tmp_path / "existing.txt").write_text("safe", encoding="utf-8")

    traversal = tools.execute("read_file", {"path": "../outside.txt"})
    absolute = tools.execute("read_file", {"path": str((tmp_path / "existing.txt").resolve())})
    overwrite = tools.execute(
        "write_file", {"path": "existing.txt", "content": "changed", "overwrite": False}
    )

    assert traversal.ok is False
    assert absolute.ok is False
    assert overwrite.ok is False
    assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "safe"


def test_workspace_write_can_explicitly_replace_file(tmp_path: Path) -> None:
    tools = WorkspaceToolRuntime(tmp_path)
    (tmp_path / "existing.txt").write_text("old", encoding="utf-8")

    result = tools.execute(
        "write_file", {"path": "existing.txt", "content": "new", "overwrite": True}
    )

    assert result.ok is True
    assert result.data["overwritten"] is True
    assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "new"
