import base64
import json

import httpx
import pytest

from gpd_tests.drivers.opencode_http import HTTPClient


def _basic(user: str, pw: str) -> str:
    raw = f"{user}:{pw}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _client(**kwargs) -> HTTPClient:
    return HTTPClient(base_url="http://x", username="u", password="p", **kwargs)


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
def test_providers_returns_config_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/config/providers"
        return httpx.Response(
            200,
            json={
                "providers": [{"id": "anthropic", "name": "Anthropic"}],
                "default": {"anthropic": "claude-4-7"},
            },
        )

    c = HTTPClient(
        base_url="http://x",
        username="u",
        password="p",
        transport=httpx.MockTransport(handler),
    )
    data = c.providers()
    assert data["providers"][0]["id"] == "anthropic"
    assert data["default"]["anthropic"] == "claude-4-7"


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


# ---------------------------------------------------------------------------
# providers() shape roundtrip — mirrors the real Provider.Info server schema
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_providers_shape_roundtrip():
    """Mock the server returning the real Provider.Info shape and validate it."""
    server_payload = {
        "providers": [
            {
                "id": "anthropic",
                "name": "Anthropic",
                "models": {"claude-4-7": {"id": "claude-4-7"}},
                "env": [],
                "options": {},
                "source": "embedded",
            }
        ],
        "default": {"anthropic": "claude-4-7"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=server_payload)

    c = _client(transport=httpx.MockTransport(handler))
    data = c.providers()

    # Top-level shape must be a dict with "providers" list and "default" dict.
    assert isinstance(data, dict), "providers() must return a dict, not a list"
    assert isinstance(data["providers"], list), '"providers" must be a list'
    assert isinstance(data["default"], dict), '"default" must be a dict'

    # Each provider entry must have "id" and "models".
    for p in data["providers"]:
        assert "id" in p, f"provider entry missing 'id': {p}"
        assert "models" in p, f"provider entry missing 'models': {p}"

    # Spot-check the anthropic entry.
    anthropic = next(p for p in data["providers"] if p["id"] == "anthropic")
    assert anthropic["models"]["claude-4-7"]["id"] == "claude-4-7"
    assert data["default"]["anthropic"] == "claude-4-7"


@pytest.mark.unit
def test_providers_unexpected_shape_fails_loudly():
    """If the server returns the OLD bare-list shape our code should not silently
    succeed — it should raise (KeyError / TypeError) so the bug is caught early.
    """
    # OLD wrong shape: server returned a bare list instead of a dict.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["anthropic", "openai"])

    c = _client(transport=httpx.MockTransport(handler))
    data = c.providers()
    # The client returns whatever the server sends, so callers that treat it
    # as a dict will raise — verify that the list shape is detectable.
    assert not isinstance(data, dict), (
        "bare-list shape should not look like the correct dict shape; "
        "if this assertion fails the server fixed itself"
    )
    with pytest.raises((TypeError, KeyError, AttributeError)):
        _ = data["providers"]  # type: ignore[index]


# ---------------------------------------------------------------------------
# sessions() — query param + error path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sessions_sends_get_to_session_endpoint():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[{"id": "ses_1"}, {"id": "ses_2"}])

    c = _client(transport=httpx.MockTransport(handler))
    result = c.sessions()
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/session"
    assert result == [{"id": "ses_1"}, {"id": "ses_2"}]


@pytest.mark.unit
def test_sessions_401_raises_http_status_error():
    c = _client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(401, json={"error": "unauthorized"})
        )
    )
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        c.sessions()
    assert exc_info.value.response.status_code == 401


# ---------------------------------------------------------------------------
# send_message() — request body verification + error path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_send_message_sends_correct_body():
    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        return httpx.Response(
            200, json={"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "ok"}]}
        )

    c = _client(transport=httpx.MockTransport(handler))
    c.send_message("ses_1", parts=[{"type": "text", "text": "hello"}])
    body = json.loads(seen[0])
    assert body["parts"] == [{"type": "text", "text": "hello"}]


@pytest.mark.unit
def test_send_message_500_raises_http_status_error():
    c = _client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(500, json={"error": "internal"})
        )
    )
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        c.send_message("ses_1", parts=[])
    assert exc_info.value.response.status_code == 500


# ---------------------------------------------------------------------------
# create_session() — query param vs body
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_session_directory_in_body_not_query_param():
    """directory is passed in the JSON body, not as a query parameter."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_new"})

    c = _client(transport=httpx.MockTransport(handler))
    c.create_session(directory="/workspace/proj")

    req = seen[0]
    body = json.loads(req.content)
    # Directory is in the body.
    assert body.get("directory") == "/workspace/proj"
    # Query string must NOT contain "directory".
    assert "directory" not in str(req.url.params), (
        "directory should not appear as a query param"
    )


# ---------------------------------------------------------------------------
# path_info() — malformed JSON error path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_path_info_malformed_json_raises():
    """If the server returns non-JSON, httpx.Response.json() raises."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all", headers={"content-type": "application/json"})

    c = _client(transport=httpx.MockTransport(handler))
    with pytest.raises(Exception):  # json.JSONDecodeError or httpx variant
        c.path_info(directory="/tmp")
