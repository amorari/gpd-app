"""Unit tests for the session-start build-skew detector (task #91).

The detector lives in the top-level ``conftest.py`` and is exercised via the
``_check_build_skew`` standalone helper so we don't have to spin pytest up
recursively. Three cases matter:

1. **Stale binary**: the sentinel command returns "Command not found" /
   "unknown" — the detector MUST call ``pytest.exit(...)`` with a rebuild
   hint so the operator fixes the root cause before wasting 5+ minutes on
   per-command regressions.
2. **Fresh binary**: the sentinel command returns a different IPCError
   (e.g. arg-shape validation) — the command IS registered, so the
   detector must NOT call ``pytest.exit``.
3. **GPD not running**: MCP ping raises — the detector must return
   silently so downstream fixtures that actually need MCP can produce
   the appropriate skip or failure.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gpd_tests.helpers.ipc import IPCError


def _load_root_conftest():
    """Import the tests-gui top-level conftest.py as a normal module.

    We can't simply ``import conftest`` because that name is ambiguous in a
    nested-conftest layout; pytest manages conftests specially. Load the
    file explicitly so we can call ``_check_build_skew`` directly.
    """
    root = Path(__file__).resolve().parents[1] / "conftest.py"
    spec = importlib.util.spec_from_file_location("tests_gui_root_conftest", root)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("tests_gui_root_conftest", mod)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
def test_sentinel_matches_task_91_choice():
    """The sentinel name is load-bearing: changing it silently would
    re-introduce the stale-binary symptom the detector exists to prevent.
    Lock it in with a test.
    """
    conftest = _load_root_conftest()
    assert conftest._BUILD_SKEW_SENTINEL == "check_project_accessible"


@pytest.mark.unit
def test_stale_binary_triggers_pytest_exit():
    """`Command X not found` in the IPCError message → pytest.exit fires."""
    conftest = _load_root_conftest()

    mcp = MagicMock()
    mcp.ping.return_value = None

    def _factory():
        return mcp

    # Patch invoke_via_mcp where the SUT looks it up (inside the helper
    # module it imports). We patch the module attribute so both the lookup
    # site and the identity check (`except IPCError`) see the same class.
    import gpd_tests.helpers.ipc as ipc_mod

    original = ipc_mod.invoke_via_mcp
    try:
        def _raise_not_found(*_a, **_kw):
            raise IPCError("Command check_project_accessible not found")

        ipc_mod.invoke_via_mcp = _raise_not_found  # type: ignore[assignment]

        from _pytest.outcomes import Exit as _PytestExit

        with pytest.raises(_PytestExit) as excinfo:
            conftest._check_build_skew(_factory)
        # pytest.exit raises a pytest-internal Exit exception whose str()
        # carries the message. Spot-check the actionable content.
        msg = str(excinfo.value)
        assert "Build-skew detected" in msg
        assert "check_project_accessible" in msg
        assert "bun run tauri build --debug" in msg
    finally:
        ipc_mod.invoke_via_mcp = original  # type: ignore[assignment]


@pytest.mark.unit
def test_fresh_binary_does_not_trigger_pytest_exit():
    """Any IPCError other than 'not found'/'unknown' means the command is
    registered (arg-validation failure, etc.) → binary is fresh → no exit.
    """
    conftest = _load_root_conftest()

    mcp = MagicMock()
    mcp.ping.return_value = None

    def _factory():
        return mcp

    import gpd_tests.helpers.ipc as ipc_mod

    original = ipc_mod.invoke_via_mcp
    try:
        def _raise_arg_shape(*_a, **_kw):
            # Realistic shape: Tauri's own arg-validation message when a
            # required field is missing. Crucially, does NOT say "not found".
            raise IPCError("invalid args `path` for command `check_project_accessible`: missing field `path`")

        ipc_mod.invoke_via_mcp = _raise_arg_shape  # type: ignore[assignment]

        # Should return None without raising pytest.exit.
        result = conftest._check_build_skew(_factory)
        assert result is None
    finally:
        ipc_mod.invoke_via_mcp = original  # type: ignore[assignment]


@pytest.mark.unit
def test_gpd_not_running_returns_silently():
    """MCP ping raises (no socket / no GPD) → detector is a no-op.

    The contract is explicit: a session-start probe must not fail when GPD
    simply isn't up. Downstream fixtures that actually need MCP will handle
    the skip.
    """
    conftest = _load_root_conftest()

    def _factory():
        raise FileNotFoundError("tauri-mcp.sock not found")

    # Must not raise — not pytest.exit, not FileNotFoundError, not anything.
    result = conftest._check_build_skew(_factory)
    assert result is None


@pytest.mark.unit
def test_ping_failure_returns_silently():
    """Factory succeeds but ping() blows up (auth rejected, timeout, etc.)
    → still a graceful no-op.
    """
    conftest = _load_root_conftest()

    mcp = MagicMock()
    mcp.ping.side_effect = RuntimeError("unauthenticated")

    def _factory():
        return mcp

    result = conftest._check_build_skew(_factory)
    assert result is None


@pytest.mark.unit
def test_unknown_command_phrasing_also_triggers_exit():
    """Tauri error wording drifts between versions ('not found' vs 'unknown').
    Both should be treated as a stale binary to stay resilient.
    """
    conftest = _load_root_conftest()

    mcp = MagicMock()
    mcp.ping.return_value = None

    def _factory():
        return mcp

    import gpd_tests.helpers.ipc as ipc_mod

    original = ipc_mod.invoke_via_mcp
    try:
        def _raise_unknown(*_a, **_kw):
            raise IPCError("unknown command: check_project_accessible")

        ipc_mod.invoke_via_mcp = _raise_unknown  # type: ignore[assignment]

        from _pytest.outcomes import Exit as _PytestExit

        with pytest.raises(_PytestExit) as excinfo:
            conftest._check_build_skew(_factory)
        assert "Build-skew detected" in str(excinfo.value)
    finally:
        ipc_mod.invoke_via_mcp = original  # type: ignore[assignment]
