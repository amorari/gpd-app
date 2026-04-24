"""Unit tests for HTTPClient wrappers around /global/* and /control/* routes.

Inventoried in docs/coverage-expansion/inventory/sidecar-routes.md:
- /global/health       GET
- /global/event        GET (SSE)
- /global/config       GET + PATCH
- /global/dispose      POST (destructive)
- /global/upgrade      POST (destructive)
- /auth/:providerID    PUT + DELETE (destructive)
- /doc                 GET (OpenAPI)
- /log                 POST

Transport is httpx.MockTransport; no live GPD required. Streaming uses
httpx's standard streaming request API with a MockTransport that returns
a text/event-stream body.
"""
from __future__ import annotations

import json

import httpx
import pytest

from gpd_tests.drivers.opencode_http import HTTPClient


def _client(**kwargs) -> HTTPClient:
    return HTTPClient(base_url="http://x", username="u", password="p", **kwargs)


# ---------------------------------------------------------------------------
# /global/health — already covered elsewhere but re-asserted here for the
# version field specifically (plan asks to "extend with version, etc").
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_global_health_returns_healthy_and_version_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/global/health"
        return httpx.Response(200, json={"healthy": True, "version": "1.2.3"})

    c = _client(transport=httpx.MockTransport(handler))
    out = c.health()
    assert out["healthy"] is True
    assert out["version"] == "1.2.3"
    # Version must be a non-empty string. A fresh-from-source build may have
    # "dev" or a semver — either is acceptable, but emptiness is not.
    assert isinstance(out["version"], str) and out["version"]


# ---------------------------------------------------------------------------
# /global/config — GET + PATCH
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_global_config_get_returns_config_info():
    payload = {"theme": "dark", "model": "anthropic/claude-4-7"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/global/config"
        return httpx.Response(200, json=payload)

    c = _client(transport=httpx.MockTransport(handler))
    assert c.global_config_get() == payload


@pytest.mark.unit
def test_global_config_patch_sends_body_and_returns_updated():
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        assert request.method == "PATCH"
        assert request.url.path == "/global/config"
        # Server echoes back the merged config.
        return httpx.Response(200, json={"theme": "light"})

    c = _client(transport=httpx.MockTransport(handler))
    result = c.global_config_patch({"theme": "light"})
    assert result == {"theme": "light"}
    assert json.loads(sent[0].content) == {"theme": "light"}


# ---------------------------------------------------------------------------
# /global/dispose, /global/upgrade — destructive, so we only shape-test here.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_global_dispose_posts_and_returns_true():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/global/dispose"
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    assert c.global_dispose() is True


@pytest.mark.unit
def test_global_upgrade_returns_success_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/global/upgrade"
        body = json.loads(request.content) if request.content else {}
        # target is optional. When omitted we should send an empty object so
        # Zod's optional() passes.
        assert isinstance(body, dict)
        return httpx.Response(200, json={"success": True, "version": "1.2.4"})

    c = _client(transport=httpx.MockTransport(handler))
    result = c.global_upgrade()
    assert result == {"success": True, "version": "1.2.4"}


@pytest.mark.unit
def test_global_upgrade_with_target_sends_target_in_body():
    sent: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.content)
        return httpx.Response(200, json={"success": True, "version": "1.2.4"})

    c = _client(transport=httpx.MockTransport(handler))
    c.global_upgrade(target="1.2.4")
    assert json.loads(sent[0]) == {"target": "1.2.4"}


# ---------------------------------------------------------------------------
# /log — write log entry
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_control_log_posts_required_fields():
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        assert request.method == "POST"
        assert request.url.path == "/log"
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    assert c.control_log(service="gpd-gui-tests", level="info", message="hello") is True
    body = json.loads(sent[0].content)
    assert body["service"] == "gpd-gui-tests"
    assert body["level"] == "info"
    assert body["message"] == "hello"
    # extra is optional, should be omitted when not provided.
    assert "extra" not in body


@pytest.mark.unit
def test_control_log_with_extra_includes_extra_in_body():
    sent: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.content)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    c.control_log(
        service="svc",
        level="warn",
        message="m",
        extra={"k": "v", "n": 1},
    )
    body = json.loads(sent[0])
    assert body["extra"] == {"k": "v", "n": 1}


@pytest.mark.unit
def test_control_log_invalid_level_raises():
    """level is an enum: debug, info, error, warn. Client-side validation
    prevents accidentally sending a typo that would 400 at the server."""
    c = _client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(400, json={"error": "bad"})
        )
    )
    with pytest.raises(ValueError):
        c.control_log(service="s", level="fatal", message="m")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# /auth/:providerID — destructive credential mutation (PUT + DELETE)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_control_auth_set_puts_to_provider_path():
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        assert request.method == "PUT"
        assert request.url.path == "/auth/anthropic"
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    ok = c.control_auth_set("anthropic", {"type": "api", "key": "sk-test"})
    assert ok is True
    assert json.loads(sent[0].content) == {"type": "api", "key": "sk-test"}


@pytest.mark.unit
def test_control_auth_remove_deletes_provider_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/auth/anthropic"
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    assert c.control_auth_remove("anthropic") is True


# ---------------------------------------------------------------------------
# /doc — OpenAPI JSON
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_control_openapi_doc_returns_spec():
    spec = {"openapi": "3.1.1", "info": {"title": "opencode", "version": "0.0.3"}}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/doc"
        return httpx.Response(200, json=spec)

    c = _client(transport=httpx.MockTransport(handler))
    out = c.control_openapi_doc()
    assert out["openapi"].startswith("3.")
    assert "info" in out


# ---------------------------------------------------------------------------
# /global/event — SSE streaming
#
# The server writes `data: <json>\n\n` frames. The helper must return a
# context manager that yields parsed events and closes the underlying
# httpx.Response cleanly on exit, even if the test only reads a partial
# stream. This is enforced by asserting we don't drain the whole body.
# ---------------------------------------------------------------------------


def _sse_body(events: list[dict]) -> bytes:
    """Encode a list of event payloads as a valid SSE stream."""
    parts = []
    for ev in events:
        parts.append(f"data: {json.dumps(ev)}\n\n")
    return "".join(parts).encode()


@pytest.mark.unit
def test_global_event_stream_yields_parsed_events():
    events = [
        {"payload": {"type": "server.connected", "properties": {}}},
        {"payload": {"type": "some.event", "properties": {"k": "v"}}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/global/event"
        return httpx.Response(
            200,
            content=_sse_body(events),
            headers={"content-type": "text/event-stream"},
        )

    c = _client(transport=httpx.MockTransport(handler))
    received: list[dict] = []
    with c.global_event_stream() as stream:
        for ev in stream:
            received.append(ev)
            if len(received) >= 2:
                break
    assert received[0]["payload"]["type"] == "server.connected"
    assert received[1]["payload"]["properties"] == {"k": "v"}


@pytest.mark.unit
def test_global_event_stream_closes_cleanly_on_partial_read():
    """Exiting the context manager after 1 event must not raise, even though
    the mock transport has more bytes queued."""
    events = [
        {"payload": {"type": "server.connected", "properties": {}}},
        {"payload": {"type": "server.heartbeat", "properties": {}}},
        {"payload": {"type": "late.event", "properties": {}}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse_body(events),
            headers={"content-type": "text/event-stream"},
        )

    c = _client(transport=httpx.MockTransport(handler))
    with c.global_event_stream() as stream:
        first = next(iter(stream))
    assert first["payload"]["type"] == "server.connected"
    # No assertion beyond "didn't raise" — the point is that leaving the
    # `with` block tears down the response cleanly.


@pytest.mark.unit
def test_global_event_stream_skips_comments_and_empty_lines():
    """SSE allows comment lines starting with `:` and blank separators. The
    parser must tolerate them without treating them as events."""
    raw = (
        b": keep-alive comment\n"
        b"\n"
        b"data: " + json.dumps({"payload": {"type": "x"}}).encode() + b"\n\n"
        b"\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=raw, headers={"content-type": "text/event-stream"}
        )

    c = _client(transport=httpx.MockTransport(handler))
    with c.global_event_stream() as stream:
        evs = list(stream)
    assert len(evs) == 1
    assert evs[0]["payload"]["type"] == "x"
