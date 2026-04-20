import base64

import httpx
import pytest

from gpd_tests.drivers.opencode_http import HTTPClient


def _basic(user: str, pw: str) -> str:
    raw = f"{user}:{pw}".encode()
    return "Basic " + base64.b64encode(raw).decode()


@pytest.mark.unit
def test_global_health_with_basic_auth():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/global/health"
        assert request.headers["Authorization"] == _basic("opencode", "pw")
        return httpx.Response(200, json={"healthy": True, "version": "1.1.0"})

    transport = httpx.MockTransport(handler)
    c = HTTPClient(
        base_url="http://127.0.0.1:60391",
        username="opencode",
        password="pw",
        transport=transport,
    )
    assert c.health() == {"healthy": True, "version": "1.1.0"}


@pytest.mark.unit
def test_sessions_returns_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/session"
        return httpx.Response(200, json=[])

    c = HTTPClient(
        base_url="http://x",
        username="u",
        password="p",
        transport=httpx.MockTransport(handler),
    )
    assert c.sessions() == []


@pytest.mark.unit
def test_providers_returns_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/config/providers"
        return httpx.Response(200, json=[{"id": "anthropic"}])

    c = HTTPClient(
        base_url="http://x",
        username="u",
        password="p",
        transport=httpx.MockTransport(handler),
    )
    assert c.providers() == [{"id": "anthropic"}]


@pytest.fixture
def transport_401_fixture():
    return httpx.MockTransport(lambda req: httpx.Response(401, json={"error": "auth"}))


@pytest.mark.unit
def test_401_raises(transport_401_fixture):
    c = HTTPClient(
        base_url="http://x",
        username="u",
        password="p",
        transport=transport_401_fixture,
    )
    with pytest.raises(httpx.HTTPStatusError):
        c.health()
