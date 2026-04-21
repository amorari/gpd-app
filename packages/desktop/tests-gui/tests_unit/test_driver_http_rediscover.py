"""Unit tests for HTTPClient.rediscover(pid) — F9.

After a GPD quit+launch or sidecar SIGKILL+respawn, the opencode-cli sidecar
reappears on a fresh port with fresh basic-auth credentials. rediscover(pid)
must look up both, close the old httpx.Client, and rebuild a fresh one so the
caller can continue making requests against the new sidecar.
"""
from __future__ import annotations

import base64

import httpx
import pytest

from gpd_tests.drivers import opencode_http
from gpd_tests.drivers.opencode_http import HTTPClient


def _basic(user: str, pw: str) -> str:
    raw = f"{user}:{pw}".encode()
    return "Basic " + base64.b64encode(raw).decode()


@pytest.mark.unit
def test_rediscover_calls_discover_port_and_credentials_with_pid(monkeypatch):
    """rediscover(pid) must forward the pid to both discovery helpers."""
    port_calls: list[dict] = []
    cred_calls: list[int] = []

    def fake_port(*, pid=None, timeout_s=15.0):
        port_calls.append({"pid": pid, "timeout_s": timeout_s})
        return 61000

    def fake_creds(pid):
        cred_calls.append(pid)
        return ("opencode", "newpw")

    monkeypatch.setattr(opencode_http, "discover_sidecar_port", fake_port)
    monkeypatch.setattr(opencode_http, "discover_sidecar_credentials", fake_creds)

    # Build a client with a MockTransport so the constructor doesn't need a
    # live sidecar; we won't issue requests before rediscover() here.
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    c = HTTPClient(
        base_url="http://127.0.0.1:60000",
        username="opencode",
        password="oldpw",
        transport=transport,
    )

    c.rediscover(pid=9999)

    assert port_calls == [{"pid": 9999, "timeout_s": 15.0}]
    assert cred_calls == [9999]


@pytest.mark.unit
def test_rediscover_repoints_client_at_new_port_with_new_auth(monkeypatch):
    """After rediscover, subsequent requests must carry new base URL + auth."""
    monkeypatch.setattr(
        opencode_http, "discover_sidecar_port", lambda *, pid, timeout_s=15.0: 62222
    )
    monkeypatch.setattr(
        opencode_http, "discover_sidecar_credentials", lambda pid: ("newuser", "newpw")
    )

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"healthy": True, "version": "1.1.0"})

    transport = httpx.MockTransport(handler)
    c = HTTPClient(
        base_url="http://127.0.0.1:60000",
        username="olduser",
        password="oldpw",
        transport=transport,
    )

    c.rediscover(pid=4242)
    # A fresh request after rediscover must hit the NEW port and carry the
    # NEW basic-auth header. Using MockTransport means the URL still funnels
    # through our handler regardless of port, which is exactly what we want
    # for an isolated unit test.
    c.health()

    assert len(seen) == 1, "expected exactly one request after rediscover"
    req = seen[0]
    assert req.url.host == "127.0.0.1"
    assert req.url.port == 62222, f"expected new port 62222, got {req.url.port}"
    assert req.headers["Authorization"] == _basic("newuser", "newpw")


@pytest.mark.unit
def test_rediscover_closes_old_client(monkeypatch):
    """The old httpx.Client must be closed so its connection pool is freed."""
    monkeypatch.setattr(
        opencode_http, "discover_sidecar_port", lambda *, pid, timeout_s=15.0: 63333
    )
    monkeypatch.setattr(
        opencode_http, "discover_sidecar_credentials", lambda pid: ("u2", "p2")
    )

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    c = HTTPClient(
        base_url="http://127.0.0.1:60000",
        username="u",
        password="p",
        transport=transport,
    )
    old = c._client
    assert old.is_closed is False

    c.rediscover(pid=1234)

    assert old.is_closed is True, "old httpx.Client must be closed after rediscover"
    assert c._client is not old, "rediscover must install a NEW httpx.Client"
    assert c._client.is_closed is False


@pytest.mark.unit
def test_rediscover_preserves_transport_and_timeout(monkeypatch):
    """Transport + timeout passed to __init__ must survive across rediscover.

    Otherwise a MockTransport-backed test client would silently fall back to a
    real network transport after rediscover, and a caller-supplied non-default
    timeout would silently reset to 120s.
    """
    monkeypatch.setattr(
        opencode_http, "discover_sidecar_port", lambda *, pid, timeout_s=15.0: 64444
    )
    monkeypatch.setattr(
        opencode_http, "discover_sidecar_credentials", lambda pid: ("u3", "p3")
    )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    c = HTTPClient(
        base_url="http://127.0.0.1:60000",
        username="u",
        password="p",
        transport=transport,
        timeout_s=7.5,
    )

    c.rediscover(pid=77)

    # Transport survived: request is captured by our handler rather than
    # escaping to a real socket.
    c._get("/global/health")
    assert calls == ["/global/health"]

    # Timeout survived: the underlying client was rebuilt with 7.5s, not the
    # default 120s.
    assert c._client.timeout.connect == 7.5
    assert c._client.timeout.read == 7.5
