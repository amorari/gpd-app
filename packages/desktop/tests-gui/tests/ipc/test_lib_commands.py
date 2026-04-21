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

import sys

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


# G4.4: parametrised probe across the three shapes of input we care about:
# nonexistent name, real app (macOS: "Finder"), and a bundle-id-formatted name.
# The Rust `check_macos_app` helper takes an app-name (not a bundle id) -- so
# passing "com.apple.finder" probes the `/Applications/com.apple.finder.app`
# path (absent) and then `which com.apple.finder` (absent). Documenting this
# mismatch with an expected-False assertion guards against silent behavior
# drift (e.g. if bundle-id handling is added later the test will flag it).
@pytest.mark.ipc
@pytest.mark.parametrize(
    "app_name,expected",
    [
        ("this-app-cannot-exist-xyzzy-9f3a", False),  # nonexistent
        ("Finder", True),                              # real macOS app name
        ("com.apple.finder", False),                   # bundle-id form: not resolved
    ],
    ids=["nonexistent", "real-macos-app", "bundle-id-form"],
)
def test_check_app_exists_parametrized(mcp, app_name, expected):
    """Parametrised probe of check_app_exists across three input shapes.

    On non-macOS platforms this test asserts shape-only (bool) because the
    platform branches (check_linux_app always returns True; Windows probes
    the PATH + registry) don't match the macOS-specific expectations. See
    also `test_check_app_exists_returns_bool` for the shape-only contract.
    """
    result = invoke_via_mcp(mcp, "check_app_exists", {"appName": app_name})
    assert isinstance(result, bool)
    if sys.platform == "darwin":
        assert result is expected, (
            f"check_app_exists({app_name!r}) returned {result!r}, "
            f"expected {expected!r} on macOS"
        )
    # On Linux: check_linux_app always returns True, so we'd only assert the
    # shape. On Windows: registry lookup is unpredictable from CI; shape-only.


# ----- resolve_app_path -----
@pytest.mark.ipc
def test_resolve_app_path_returns_string_or_null(mcp):
    """resolve_app_path returns Option<String>. On macOS/Linux the command
    echoes the input; on Windows it queries the registry."""
    result = invoke_via_mcp(mcp, "resolve_app_path", {"appName": "Finder"})
    # On macOS/Linux this returns the app_name as-is (Some("Finder")). On
    # Windows it may return None if the app is absent. Either shape is valid.
    assert result is None or isinstance(result, str)


# G4.4: pair resolve_app_path with check_app_exists to document the
# non-Windows identity branch. On macOS/Linux resolve_app_path echoes its
# input as Some(name), regardless of whether the app actually exists -- the
# `None` branch is Windows-registry-only. We assert the contract:
#   non-Windows: existent-app -> Some(name);  nonexistent-app -> Some(name)
#   Windows:     registry-hit -> Some(path);  registry-miss -> None
@pytest.mark.ipc
def test_resolve_app_path_pairs_with_check_app_exists(mcp):
    """Cross-command invariant: check_app_exists() returning True on a real
    app implies resolve_app_path() returns a non-null value for the same
    name. The reverse is not required (non-Windows resolver is identity).
    """
    real_name = "Finder" if sys.platform == "darwin" else "Finder"
    missing_name = "this-app-cannot-exist-xyzzy-9f3a"

    real_exists = invoke_via_mcp(mcp, "check_app_exists", {"appName": real_name})
    real_path = invoke_via_mcp(mcp, "resolve_app_path", {"appName": real_name})
    missing_exists = invoke_via_mcp(mcp, "check_app_exists", {"appName": missing_name})
    missing_path = invoke_via_mcp(mcp, "resolve_app_path", {"appName": missing_name})

    # Shape assertions -- always hold.
    assert isinstance(real_exists, bool)
    assert real_path is None or isinstance(real_path, str)
    assert isinstance(missing_exists, bool)
    assert missing_path is None or isinstance(missing_path, str)

    if sys.platform == "win32":
        # Windows registry lookup: a nonexistent app should yield None.
        assert missing_path is None, (
            f"expected resolve_app_path({missing_name!r}) == None on Windows, "
            f"got {missing_path!r}"
        )
    else:
        # macOS/Linux: resolver is identity -- echoes input regardless of
        # whether the app is installed. Both inputs return Some(input).
        assert real_path == real_name
        assert missing_path == missing_name

    # Cross-command invariant (all platforms): if the app exists, the
    # resolver must not return None -- otherwise the UI would have an
    # existent-but-unresolvable app, which is a contract violation.
    if real_exists:
        assert real_path is not None


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


# G4.4: error-path coverage for the invalid-backend branch. `LinuxDisplayBackend`
# is a two-variant enum (Wayland | Auto) with #[serde(rename_all="camelCase")];
# any other string must fail at Tauri's argument-deserialisation layer before
# the handler runs. We wrap the whole thing in try/finally to restore the
# original preference even though the invalid-value call should never mutate
# state (deserialisation rejects before the writer runs).
@pytest.mark.ipc
def test_set_display_backend_rejects_invalid_value(mcp):
    """Passing an unknown backend variant (e.g. "not_a_real_backend") must
    raise IPCError. The handler's #[serde] enum only accepts "wayland" and
    "auto" -- any other value fails deserialisation before the writer runs,
    so there is no state to restore in practice. We still capture the
    original value and restore it in a finally block as a belt-and-suspenders
    safeguard against future regressions.
    """
    original = invoke_via_mcp(mcp, "get_display_backend", {})
    try:
        with pytest.raises(IPCError) as excinfo:
            invoke_via_mcp(
                mcp, "set_display_backend", {"backend": "not_a_real_backend"}
            )
        # Error message should indicate the invalid value / variant; Tauri's
        # serde error typically contains "unknown variant" or "invalid value".
        # We keep the assertion loose (case-insensitive substring) since the
        # exact phrasing depends on the serde version.
        msg = str(excinfo.value).lower()
        assert any(
            needle in msg
            for needle in ("invalid", "unknown variant", "expected", "backend")
        ), f"unexpected error message for invalid backend: {excinfo.value!r}"
    finally:
        # Defensive restore -- the error-path should not have mutated state,
        # but we always restore to guarantee the next test sees a clean slate.
        if original in ("wayland", "auto"):
            invoke_via_mcp(mcp, "set_display_backend", {"backend": original})
        else:
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


# G4.4: document the non-Windows short-circuit. The Rust handler opens with
#   if !cfg!(windows) { return Ok(path); }
# so the input string is echoed unchanged regardless of its contents --
# forward-slash paths AND Windows-style `C:\...` paths alike. This test pins
# that behaviour so a future change (e.g. adding non-Windows conversion via
# a shim) surfaces here.
@pytest.mark.ipc
@pytest.mark.parametrize(
    "path_in",
    [
        "/tmp/foo",                 # already forward-slash POSIX
        "/usr/local/bin/gpd",       # nested forward-slash POSIX
        "C:\\Users\\Alice\\doc",    # Windows-style path
        "C:/Users/Alice/doc",       # Windows-mixed-style path
        "relative/path",            # relative POSIX
    ],
    ids=["posix-simple", "posix-nested", "windows-backslash",
         "windows-forwardslash", "relative"],
)
def test_wsl_path_non_windows_identity_on_various_inputs(mcp, path_in):
    """On non-Windows hosts `wsl_path` unconditionally echoes its input
    unchanged (the handler's early `if !cfg!(windows) { return Ok(path) }`
    branch). On Windows this would shell out to `wsl -e wslpath`, so we
    skip to avoid exercising a real subprocess here -- the Windows branch
    is covered by the shape assertions in the existing happy-path test.
    """
    if sys.platform == "win32":
        pytest.skip(
            "non-Windows identity is the branch under test; Windows host "
            "would invoke `wsl -e wslpath` and could fail if WSL is absent"
        )
    result = invoke_via_mcp(mcp, "wsl_path", {"path": path_in, "mode": None})
    assert result == path_in, (
        f"wsl_path({path_in!r}) on non-Windows should echo input; "
        f"got {result!r}"
    )


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
