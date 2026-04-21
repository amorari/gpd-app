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


# ---------------------------------------------------------------------------
# G4.3 — Deep server command coverage.
#
# These tests extend the happy-path contracts above with:
#   * A strict round-trip for `get_default_server_url`/`set_default_server_url`
#     that snapshots and restores the caller's prior value to avoid leaking
#     test state into the dev environment.
#   * A regression guard pinning the current hardcoded `{enabled: false}`
#     shape of `get_wsl_config`. server.rs currently returns a constant
#     regardless of store contents (the store-read branch is commented out;
#     see `packages/desktop/src-tauri/src/server.rs:57-69`). If that branch
#     is ever uncommented, this test will fail — by design — so the change
#     is visible in code review.
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_set_and_get_default_server_url_roundtrip_with_cleanup(mcp):
    """Snapshot prior value, round-trip set/get for a string and for None,
    then restore the snapshot.

    Covers the two-branch write path in `set_default_server_url`:
      * `Some(url)` -> store.set(...)
      * `None` -> store.delete(...)
    and the two-branch read path in `get_default_server_url`:
      * `Some(Value::String(_))` -> Ok(Some(s))
      * `None` -> Ok(None)
    """
    # Snapshot whatever is currently in the store so this test does not leak
    # state into the user's dev environment.
    prior = invoke_via_mcp(mcp, "get_default_server_url", {})
    assert prior is None or isinstance(prior, str)

    try:
        url = "http://127.0.0.1:65534/roundtrip"
        set_result = invoke_via_mcp(mcp, "set_default_server_url", {"url": url})
        assert set_result is None
        assert invoke_via_mcp(mcp, "get_default_server_url", {}) == url

        # Now clear the value — hits the `None` branch which calls
        # store.delete(DEFAULT_SERVER_URL_KEY).
        clear_result = invoke_via_mcp(mcp, "set_default_server_url", {"url": None})
        assert clear_result is None
        assert invoke_via_mcp(mcp, "get_default_server_url", {}) is None
    finally:
        # Restore the pre-test value to the store. Passing None is the only
        # way to actually delete the key; setting to a string replaces it.
        invoke_via_mcp(mcp, "set_default_server_url", {"url": prior})


@pytest.mark.ipc
def test_get_wsl_config_pins_hardcoded_shape_regression_guard(mcp):
    """Regression guard on the currently-hardcoded shape of `get_wsl_config`.

    `server.rs::get_wsl_config` is effectively a constant: it returns
    `WslConfig { enabled: false }` regardless of store contents (the
    store-read branch is commented out in the Rust source). This test pins
    that contract so that if the branch is ever uncommented, the assertion
    here fails and the code-review surface flags it explicitly.

    We also exercise the "setter-does-not-affect-getter" invariant: write
    `enabled: true` via `set_wsl_config`, then call `get_wsl_config` and
    assert the returned value is still `{enabled: false}`. Restores the
    store to `enabled: false` on teardown regardless of assertion outcome.
    """
    # First: unconditionally pinned shape.
    result = invoke_via_mcp(mcp, "get_wsl_config", {})
    assert result == {"enabled": False}, (
        "get_wsl_config is hardcoded to return {enabled: false} in "
        "server.rs:57-69; if this assertion fails, the commented-out "
        "store-read branch has been uncommented — update this test and "
        "the companion set/get roundtrip coverage accordingly."
    )

    # Second: write true via setter, confirm getter still returns false.
    try:
        invoke_via_mcp(mcp, "set_wsl_config", {"config": {"enabled": True}})
        after = invoke_via_mcp(mcp, "get_wsl_config", {})
        assert after == {"enabled": False}, (
            "get_wsl_config returned a non-constant value after "
            "set_wsl_config({enabled: true}) — the getter now reads "
            "from the store. Update this regression guard."
        )
    finally:
        invoke_via_mcp(mcp, "set_wsl_config", {"config": {"enabled": False}})
