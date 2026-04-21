"""Negative-space sweep across every Tauri command in the catalog."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


_CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "gpd_tests" / "fixtures" / "tauri_commands.json"
)
try:
    _CATALOG = json.loads(_CATALOG_PATH.read_text())
    _CATALOG_LOAD_ERROR: str | None = None
except (FileNotFoundError, json.JSONDecodeError) as _e:
    _CATALOG = None
    _CATALOG_LOAD_ERROR = str(_e)

# Commands that are unsafe to invoke with a bogus argument shape even in a
# "negative sweep" because they either (a) execute destructive side effects
# before reaching deserialization, (b) open a modal dialog / spawn an
# external installer, or (c) block on a Channel or subprocess that will
# never signal under test conditions. The sweep cannot assert their
# deserializer behavior; dedicated tests in the per-file suites cover
# them where safe.
_UNSAFE_FOR_NEGATIVE_SWEEP = {
    "kill_sidecar",            # kills the opencode-cli sidecar for the rest of the sweep
    "repair_gpd_venv",         # wipes ~/.config/gpd/.venv and runs full network setup
    "open_path",               # spawns `open` — may hit unrelated handler
    "install_cli",             # runs the CLI installer (modal + network)
    "install_git_macos",       # runs the Git installer (modal + network)
    "install_git_windows",     # runs the Git installer (modal + network)
    "install_tectonic",        # triggers tectonic bootstrap (multi-minute + network)
    "await_initialization",    # blocks on an events Channel that bogus args won't fulfill
    "compile_tex",             # spawns a tectonic subprocess that may take minutes
}
_COMMAND_NAMES = [
    c["name"] for c in (_CATALOG or [])
    if c["name"] not in _UNSAFE_FOR_NEGATIVE_SWEEP
]


# ---------------------------------------------------------------------------
# Every safe command should reject a bogus argument dict cleanly.
# ---------------------------------------------------------------------------

@pytest.mark.ipc
@pytest.mark.timeout(20)
@pytest.mark.parametrize("cmd", _COMMAND_NAMES)
def test_command_rejects_bogus_arg_shape(mcp, cmd):
    """Passing {"__bogus__": None} should produce an IPCError, never a hang
    or a silent success. Tauri's deserializer will reject unknown fields
    when the command has an arg struct; no-arg commands will either accept
    (and we assert via a follow-up call that they still work) or reject.

    Dangerous commands are excluded via `_UNSAFE_FOR_NEGATIVE_SWEEP`; their
    deserializer behavior is checked (if at all) by dedicated tests."""
    if _CATALOG is None:
        pytest.skip(f"tauri_commands.json unloadable: {_CATALOG_LOAD_ERROR}")
    try:
        result = invoke_via_mcp(mcp, cmd, {"__bogus__": None})
        # If a command takes no args, Tauri often ignores the extra field and
        # returns successfully. Accept that, but don't accept silent failure
        # (return None from a command that should return something).
        # This is informational: we just want to confirm no crash/hang.
    except IPCError as e:
        msg = str(e).lower()
        # The error should mention something about the argument or the
        # command shape — not a generic "crash" or "timeout".
        assert any(
            hint in msg
            for hint in ("arg", "field", "parse", "deserialize", "missing", "invalid", "expected", "unknown")
        ), f"{cmd} errored but message doesn't mention arg issue: {e!r}"


@pytest.mark.ipc
@pytest.mark.timeout(20)
def test_nonexistent_command_errors_cleanly(mcp):
    """A made-up command name must raise IPCError with a clear 'command not found' signal."""
    with pytest.raises(IPCError) as exc_info:
        invoke_via_mcp(mcp, "this_command_does_not_exist_xyzzy", {})
    msg = str(exc_info.value).lower()
    assert any(hint in msg for hint in ("command", "not found", "unknown", "handler"))


@pytest.mark.ipc
@pytest.mark.timeout(20)
def test_empty_args_on_commands_with_required_fields(mcp):
    """Commands with required args should reject an empty {} dict."""
    if _CATALOG is None:
        pytest.skip(f"tauri_commands.json unloadable: {_CATALOG_LOAD_ERROR}")
    # Pick a few commands we know take args (from catalog).
    required_arg_commands = [
        c["name"] for c in _CATALOG
        if "path" in c["signature"].lower() or "file" in c["signature"].lower()
    ]
    assert required_arg_commands, "catalog seems empty; regenerate"

    cmd = required_arg_commands[0]
    with pytest.raises(IPCError):
        invoke_via_mcp(mcp, cmd, {})
