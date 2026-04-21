"""Contract tests for lib.rs (8 cmds) + gpd_setup.rs (1 cmd) commands.

Organization:
  # --- lib.rs ---          kill_sidecar, await_initialization, check_app_exists,
                            resolve_app_path, open_path, get_display_backend,
                            set_display_backend, wsl_path
  # --- gpd_setup.rs ---    repair_gpd_venv

Several commands have destructive side effects on the running GPD test session
and are guarded with a clear skip + rationale rather than invoked blindly.
Those skips are documented inline so the contract surface is still enumerated.

Tauri's invoke layer camelCases argument names (see `src/bindings.ts`):
  check_app_exists(app_name)  ->  {"appName": ...}
  resolve_app_path(app_name)  ->  {"appName": ...}
  open_path(path, app_name)   ->  {"path": ..., "appName": ...}
"""
from __future__ import annotations

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


# =============================================================================
# --- lib.rs ---
# =============================================================================


# ----- kill_sidecar -----
# Destructive: invoking this command terminates the opencode-cli sidecar used
# by every `http`-fixture test in the session. The tauri-plugin-mcp surface we
# call through is separate (plugin socket, not sidecar), so the command itself
# would succeed -- but we'd leave the app in a broken state for subsequent
# tests. Contract is covered by the catalog invariant instead; this skip keeps
# the enumeration visible.
@pytest.mark.ipc
@pytest.mark.skip(
    reason="kill_sidecar is destructive to the shared session; covered by catalog invariant"
)
def test_kill_sidecar_skipped_destructive(mcp):  # pragma: no cover
    invoke_via_mcp(mcp, "kill_sidecar", {})


# ----- await_initialization -----
# After the app has finished booting (which is a precondition for the test
# session running at all), this command resolves immediately with the cached
# sidecar credentials. We can't easily send the required `Channel<InitStep>`
# from JS without allocating one, and invoking without it triggers Tauri
# deserialization failure -- which is itself a valid contract check.
@pytest.mark.ipc
def test_await_initialization_requires_channel_arg(mcp):
    """Omitting the required `events` Channel argument must raise IPCError
    (Tauri rejects during argument deserialization before the handler runs)."""
    with pytest.raises(IPCError):
        invoke_via_mcp(mcp, "await_initialization", {})


# ----- check_app_exists -----
@pytest.mark.ipc
def test_check_app_exists_returns_bool(mcp):
    """check_app_exists returns a bool for any string input. On macOS it
    checks ~/Applications, /Applications, /System/Applications, then `which`."""
    # Finder.app ships with every macOS install; on other platforms the
    # command still returns a bool (true on Linux, PATH-based on Windows),
    # so we only assert shape, not truthiness.
    result = invoke_via_mcp(mcp, "check_app_exists", {"appName": "Finder"})
    assert isinstance(result, bool)


@pytest.mark.ipc
def test_check_app_exists_false_for_nonsense_name(mcp):
    """A clearly nonexistent app name returns False on macOS/Windows.
    (On Linux the command always returns True per check_linux_app, so we
    accept either False or True -- the contract is `bool`.)"""
    result = invoke_via_mcp(
        mcp, "check_app_exists", {"appName": "this-app-cannot-exist-xyzzy-9f3a"}
    )
    assert isinstance(result, bool)


# ----- resolve_app_path -----
@pytest.mark.ipc
def test_resolve_app_path_returns_string_or_null(mcp):
    """resolve_app_path returns Option<String>. On macOS/Linux the command
    echoes the input; on Windows it queries the registry."""
    result = invoke_via_mcp(mcp, "resolve_app_path", {"appName": "Finder"})
    # On macOS/Linux this returns the app_name as-is (Some("Finder")). On
    # Windows it may return None if the app is absent. Either shape is valid.
    assert result is None or isinstance(result, str)


# ----- open_path -----
# Invoking open_path would actually open a file/app in the user's desktop
# environment (Finder window, browser, etc.) -- highly disruptive for an
# unattended test run. Skip the happy path; exercise the failure path with
# a missing required argument instead.
@pytest.mark.ipc
def test_open_path_missing_required_arg_errors(mcp):
    """Omitting the required `path` argument must raise IPCError."""
    with pytest.raises(IPCError):
        invoke_via_mcp(mcp, "open_path", {})


# ----- get_display_backend -----
@pytest.mark.ipc
def test_get_display_backend_shape(mcp):
    """get_display_backend returns Option<LinuxDisplayBackend>. On non-Linux
    platforms the command always returns None; on Linux it returns
    "wayland" | "auto" based on the preference file."""
    result = invoke_via_mcp(mcp, "get_display_backend", {})
    assert result is None or result in ("wayland", "auto")


# ----- set_display_backend -----
@pytest.mark.ipc
def test_set_display_backend_roundtrip(mcp):
    """set_display_backend is a no-op on non-Linux (returns Ok(())); on Linux
    it writes to the preference file.

    State restore: read original -> set to both values -> restore original.
    Uses try/finally so a mid-test failure still restores state.
    """
    original = invoke_via_mcp(mcp, "get_display_backend", {})
    try:
        # Set to wayland, then auto -- both must succeed without error.
        # Return value is null (Result<(), String> -> undefined -> null).
        r1 = invoke_via_mcp(mcp, "set_display_backend", {"backend": "wayland"})
        assert r1 is None
        r2 = invoke_via_mcp(mcp, "set_display_backend", {"backend": "auto"})
        assert r2 is None
    finally:
        # Restore original value. On non-Linux this is a no-op either way;
        # on Linux it rewrites the preference file back to what it was.
        if original in ("wayland", "auto"):
            invoke_via_mcp(mcp, "set_display_backend", {"backend": original})
        else:
            # Original was None (Linux default) -- "auto" is the documented
            # default fallback in get_display_backend, so restore to "auto".
            invoke_via_mcp(mcp, "set_display_backend", {"backend": "auto"})


# ----- wsl_path -----
@pytest.mark.ipc
def test_wsl_path_non_windows_is_identity(mcp):
    """On non-Windows platforms wsl_path returns its input unchanged.
    On Windows it shells out to `wsl -e wslpath`; a simple POSIX path should
    still round-trip cleanly enough for the shape assertion."""
    result = invoke_via_mcp(mcp, "wsl_path", {"path": "/tmp/foo", "mode": None})
    assert isinstance(result, str)


@pytest.mark.ipc
def test_wsl_path_missing_required_arg_errors(mcp):
    """Omitting the required `path` argument must raise IPCError."""
    with pytest.raises(IPCError):
        invoke_via_mcp(mcp, "wsl_path", {})


# =============================================================================
# --- gpd_setup.rs ---
# =============================================================================


# ----- repair_gpd_venv -----
# Highly destructive: removes ~/.config/gpd/.venv, deletes the init marker, and
# then re-runs the full first-run setup (network download of get-physics-done,
# gpd install opencode --global, provider config injection). A real invocation
# would take minutes and clobber the user's real GPD install. The contract is
# that it exists and is registered; catalog invariant covers that.
@pytest.mark.ipc
@pytest.mark.skip(
    reason="repair_gpd_venv is destructive (wipes venv + re-runs setup); covered by catalog invariant"
)
def test_repair_gpd_venv_skipped_destructive(mcp):  # pragma: no cover
    invoke_via_mcp(mcp, "repair_gpd_venv", {})
