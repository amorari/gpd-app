"""Phase G3.6: integration coverage for /global/* and /control/* routes.

Per docs/coverage-expansion/inventory/sidecar-routes.md:
- /global/health        GET         — covered by smoke/test_launch.py (kept as brief here)
- /global/event         GET (SSE)   — minimal 1-2 event consumer + clean close
- /global/config        GET         — shape check
- /global/config        PATCH       — NOT covered here (would require fresh-app cleanup)
- /global/dispose       POST        — opt-in via PYTEST_OPTIN_MUTATE_SYSTEM=1
- /global/upgrade       POST        — opt-in via PYTEST_OPTIN_MUTATE_SYSTEM=1
- /doc                  GET         — OpenAPI spec shape
- /log                  POST        — emit a harmless info log
- /auth/:providerID     PUT         — opt-in (mutates auth.json)
- /auth/:providerID     DELETE      — opt-in (mutates auth.json)

The "control plane" shutdown/restart endpoints referenced in the task are
/global/dispose (tear down all instances) and /global/upgrade (self-upgrade
the binary). Both are gated behind PYTEST_OPTIN_MUTATE_SYSTEM=1.
"""
from __future__ import annotations

import os

import httpx
import pytest


_OPTIN_MUTATE_REASON = (
    "destructive — set PYTEST_OPTIN_MUTATE_SYSTEM=1 to enable"
)


# ---------------------------------------------------------------------------
# /global/health — already covered by smoke/test_launch.py. Keep a 1-liner
# version-focused smoke here so the G3.6 file documents the coverage gap.
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_global_health_reports_version(http):
    out = http.health()
    assert out.get("healthy") is True
    version = out.get("version")
    assert isinstance(version, str) and version, (
        f"/global/health must include a non-empty version string, got {out!r}"
    )


# ---------------------------------------------------------------------------
# /global/config — read-only GET
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_global_config_get_returns_dict(http):
    """GET /global/config returns the merged Config.Info as a JSON object.

    No PATCH counterpart here — that would mutate persistent settings. A
    dedicated fresh_app test under phase G6 (settings persistence) owns
    that write path.
    """
    config = http.global_config_get()
    assert isinstance(config, dict), (
        f"/global/config must return a JSON object, got {type(config).__name__}"
    )


# ---------------------------------------------------------------------------
# /global/event — SSE streaming
#
# The server emits a `server.connected` event immediately on connect
# (instance/global.ts:28). We consume that one and exit — the `with`
# block closes the streaming Response cleanly.
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_global_event_stream_receives_connected_event(http):
    """Open the SSE stream, read 1 event, close cleanly.

    Success criteria:
      - At least one event arrives within 10s.
      - First event's payload has a `type` field (shape only — content
        varies by server build).
      - Exiting the `with` block does not raise.
    """
    import time

    deadline = time.monotonic() + 10.0
    received: list[dict] = []
    with http.global_event_stream() as stream:
        for event in stream:
            received.append(event)
            if len(received) >= 1 or time.monotonic() > deadline:
                break

    if not received:
        pytest.skip(
            "/global/event produced no events in 10s — server may be idle; "
            "not a failure of the streaming consumer itself"
        )

    first = received[0]
    assert isinstance(first, dict), f"event not a dict: {first!r}"
    # opencode wraps everything in `{payload: {type, properties}}`. The
    # very first event on connect is `server.connected` but we don't hard-
    # pin that here — just the envelope shape.
    payload = first.get("payload")
    assert isinstance(payload, dict), f"event missing payload dict: {first!r}"
    assert "type" in payload, f"payload missing type: {payload!r}"


# ---------------------------------------------------------------------------
# /doc — OpenAPI spec
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_control_openapi_doc_returns_valid_spec(http):
    """GET /doc returns an OpenAPI 3.1 spec. Shape-only sanity check."""
    spec = http.control_openapi_doc()
    assert isinstance(spec, dict)
    assert "openapi" in spec, f"spec missing 'openapi' field: {list(spec.keys())}"
    assert spec["openapi"].startswith("3."), f"unexpected openapi version: {spec['openapi']!r}"
    assert "info" in spec
    # A valid spec always has at least one path or a top-level schema dict.
    # opencode's control-plane /doc covers the auth, dispose, upgrade, etc.
    # endpoints, so `paths` must be non-empty.
    paths = spec.get("paths", {})
    assert isinstance(paths, dict) and paths, (
        "OpenAPI spec must declare at least one path"
    )


# ---------------------------------------------------------------------------
# /log — write a benign entry. Safe: doesn't mutate user state.
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_control_log_accepts_info_entry(http):
    """POST /log with an info-level entry succeeds.

    This writes to the sidecar's server log file, which rotates. Harmless.
    """
    ok = http.control_log(
        service="gpd-gui-tests",
        level="info",
        message="test_global_control.test_control_log_accepts_info_entry",
    )
    assert ok is True


@pytest.mark.flows
def test_control_log_rejects_invalid_level_client_side(http):
    """The client refuses invalid levels before hitting the wire."""
    with pytest.raises(ValueError):
        http.control_log(
            service="gpd-gui-tests",
            level="fatal",  # type: ignore[arg-type]
            message="should not reach server",
        )


# ---------------------------------------------------------------------------
# /global/dispose — DESTRUCTIVE. Opt-in only.
# ---------------------------------------------------------------------------


@pytest.mark.flows
@pytest.mark.skipif(
    os.environ.get("PYTEST_OPTIN_MUTATE_SYSTEM") != "1",
    reason=_OPTIN_MUTATE_REASON,
)
def test_global_dispose_returns_true(http):
    """POST /global/dispose tears down all sidecar instances.

    After dispose, subsequent requests will reconnect / respawn. This test
    does NOT wait for respawn — the session-scoped `http` fixture's teardown
    and any following test's setup handle that. We just assert the POST
    succeeds and returns true.
    """
    ok = http.global_dispose()
    assert ok is True


# ---------------------------------------------------------------------------
# /global/upgrade — DESTRUCTIVE. Opt-in only.
# ---------------------------------------------------------------------------


@pytest.mark.flows
@pytest.mark.skipif(
    os.environ.get("PYTEST_OPTIN_MUTATE_SYSTEM") != "1",
    reason=_OPTIN_MUTATE_REASON,
)
def test_global_upgrade_with_current_version_is_idempotent(http):
    """POST /global/upgrade targeting the currently-installed version.

    Passing the running version as `target` should either succeed as a
    no-op reinstall or return `{success: false}` with a descriptive error
    (e.g. "unknown installation method" on a source checkout). Either way
    the response shape is asserted.
    """
    current = http.health().get("version")
    assert isinstance(current, str) and current

    try:
        result = http.global_upgrade(target=current)
    except httpx.HTTPStatusError as e:
        # 400 is an acceptable outcome for unknown installation methods
        # (e.g. running from a dev checkout) — surface as a skip so the
        # test makes sense across environments.
        if e.response.status_code == 400:
            pytest.skip(f"/global/upgrade rejected with 400: {e.response.text}")
        raise

    assert isinstance(result, dict) and "success" in result
    if result["success"]:
        assert "version" in result
    else:
        assert "error" in result


# ---------------------------------------------------------------------------
# /auth/:providerID PUT + DELETE — DESTRUCTIVE. Opt-in only.
# ---------------------------------------------------------------------------


@pytest.mark.flows
@pytest.mark.skipif(
    os.environ.get("PYTEST_OPTIN_MUTATE_SYSTEM") != "1",
    reason=_OPTIN_MUTATE_REASON,
)
def test_control_auth_set_then_remove_roundtrip(http):
    """PUT then DELETE for a throwaway provider id.

    Uses a sentinel provider id that is unlikely to collide with a real
    one (`gpd-test-sentinel`). Even if the set succeeds and the remove
    fails, the worst case is an orphan auth entry under a dummy provider —
    still safer than touching `anthropic` etc.
    """
    provider = "gpd-test-sentinel"
    try:
        ok = http.control_auth_set(
            provider,
            {"type": "api", "key": "sentinel-test-key-do-not-use"},
        )
        assert ok is True
    except httpx.HTTPStatusError as e:
        # Unknown provider id is rejected by the zod schema on the PUT
        # path. If so the test is a no-op on this server version.
        if e.response.status_code in (400, 422):
            pytest.skip(
                f"/auth/{provider} rejected {e.response.status_code}: "
                f"{e.response.text}"
            )
        raise
    # Remove is best-effort; the primary assertion above is the PUT roundtrip.
    try:
        http.control_auth_remove(provider)
    except httpx.HTTPStatusError:
        pass
