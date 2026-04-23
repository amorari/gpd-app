"""Contract tests for project_fs.rs commands. Run against live GPD debug build."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


@pytest.mark.ipc
def test_create_project_directory_happy_path(mcp):
    """create_project_directory creates a new folder under the parent and
    returns its absolute path as a string."""
    with tempfile.TemporaryDirectory() as parent:
        name = "gpd-contract-happy"
        result = invoke_via_mcp(
            mcp,
            "create_project_directory",
            {"parent": parent, "name": name},
        )
        assert isinstance(result, str)
        created = Path(result)
        try:
            assert created.is_dir()
            assert created.name == name
            assert created.parent == Path(parent).resolve() or created.parent == Path(parent)
        finally:
            if created.exists():
                created.rmdir()


@pytest.mark.ipc
def test_create_project_directory_rejects_invalid(mcp):
    """An empty project name must be rejected with an IPC error (the Rust
    command returns Err for empty/whitespace names)."""
    with tempfile.TemporaryDirectory() as parent:
        with pytest.raises(IPCError):
            invoke_via_mcp(
                mcp,
                "create_project_directory",
                {"parent": parent, "name": "   "},
            )


@pytest.mark.ipc
def test_check_project_accessible_happy_path(mcp):
    """check_project_accessible returns the literal string "ok" for a
    readable directory the main process can access."""
    with tempfile.TemporaryDirectory() as d:
        result = invoke_via_mcp(
            mcp,
            "check_project_accessible",
            {"path": d},
        )
        assert result == "ok"


@pytest.mark.ipc
def test_check_project_accessible_rejects_invalid(mcp):
    """A path that doesn't exist returns the sentinel string "missing" — it
    is a well-formed Ok value, not an Err. To force the IPCError path we
    omit the required `path` argument, which Tauri rejects during
    deserialization."""
    with pytest.raises(IPCError):
        invoke_via_mcp(mcp, "check_project_accessible", {})
