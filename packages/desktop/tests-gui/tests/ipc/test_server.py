"""Contract tests for server.rs Tauri commands.

server.rs exposes four commands that wrap the tauri-plugin-store settings for
the opencode-cli sidecar:

  - get_default_server_url(app)            -> Option<String>
  - set_default_server_url(app, url: Option<String>) -> ()
  - get_wsl_config(app)                    -> WslConfig { enabled: bool }
  - set_wsl_config(app, config: WslConfig) -> ()

These tests verify the Tauri wrapper behaves correctly (accepts/returns the
right JSON shapes, rejects bad args) — they do not re-test the HTTP sidecar
health-check logic.
"""
from __future__ import annotations

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


# ---------------------------------------------------------------------------
# get_default_server_url — no args, returns Option<String> (null or a string).
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_get_default_server_url_happy_path(mcp):
    """Returns either null or a string; never throws for a fresh store."""
    result = invoke_via_mcp(mcp, "get_default_server_url", {})
    assert result is None or isinstance(result, str)


# single-return, no failure mode — command takes no args and only reads the
# settings store. Store-open failures aren't reproducible from the test
# harness without corrupting on-disk state.


# ---------------------------------------------------------------------------
# set_default_server_url — takes Option<String>, returns ().
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_set_default_server_url_happy_path(mcp):
    """Round-trip: set a URL, read it back, then clear it."""
    url = "http://127.0.0.1:65535"  # port high enough to be unused
    try:
        set_result = invoke_via_mcp(mcp, "set_default_server_url", {"url": url})
        # Rust returns Result<(), String>; Ok(()) serializes to null.
        assert set_result is None
        read_back = invoke_via_mcp(mcp, "get_default_server_url", {})
        assert read_back == url
    finally:
        # Restore prior state: passing None deletes the key.
        invoke_via_mcp(mcp, "set_default_server_url", {"url": None})


@pytest.mark.ipc
def test_set_default_server_url_rejects_wrong_type(mcp):
    """Passing a non-string, non-null url must fail deserialization."""
    with pytest.raises(IPCError):
        invoke_via_mcp(mcp, "set_default_server_url", {"url": 12345})


# ---------------------------------------------------------------------------
# get_wsl_config — no args, returns WslConfig { enabled: bool }.
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_get_wsl_config_happy_path(mcp):
    """Returns a WslConfig struct with an `enabled` boolean field."""
    result = invoke_via_mcp(mcp, "get_wsl_config", {})
    assert isinstance(result, dict)
    assert "enabled" in result
    assert isinstance(result["enabled"], bool)


# single-return, no failure mode — command takes no args and the current
# implementation hardcodes `WslConfig { enabled: false }`, so there is no
# input-driven failure path to exercise.


# ---------------------------------------------------------------------------
# set_wsl_config — takes WslConfig, returns ().
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_set_wsl_config_happy_path(mcp):
    """Round-trip: set a config, then restore. Value is persisted via store."""
    try:
        set_result = invoke_via_mcp(
            mcp, "set_wsl_config", {"config": {"enabled": True}}
        )
        assert set_result is None
        # Note: get_wsl_config currently hardcodes `enabled: false` regardless
        # of what was stored, so we cannot read-back-assert here. The contract
        # we verify is that setter accepts a valid WslConfig without error.
    finally:
        invoke_via_mcp(mcp, "set_wsl_config", {"config": {"enabled": False}})


@pytest.mark.ipc
def test_set_wsl_config_rejects_missing_field(mcp):
    """WslConfig requires an `enabled` bool; empty object must fail."""
    with pytest.raises(IPCError):
        invoke_via_mcp(mcp, "set_wsl_config", {"config": {}})
