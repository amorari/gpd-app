"""Shape-only tests for HTTPClient session helpers. No live GPD required."""
from __future__ import annotations

import json

import httpx
import pytest

from gpd_tests.drivers.opencode_http import HTTPClient


def _mock_transport(routes: dict[tuple[str, str], tuple[int, dict]]):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key not in routes:
            return httpx.Response(404, json={"error": "no route"})
        status, body = routes[key]
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler)


@pytest.mark.unit
def test_create_session_posts_directory_and_returns_info():
    transport = _mock_transport({
        ("POST", "/session"): (
            200,
            {"id": "ses_abc", "directory": "/tmp/x", "version": 1},
        ),
    })
    with HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=transport,
    ) as c:
        info = c.create_session(directory="/tmp/x")
    assert info["id"] == "ses_abc"
    assert info["directory"] == "/tmp/x"


@pytest.mark.unit
def test_send_message_posts_and_returns_parsed_response():
    transport = _mock_transport({
        ("POST", "/session/ses_abc/message"): (
            200,
            {
                "info": {"role": "assistant", "id": "msg_1"},
                "parts": [{"type": "text", "text": "hi"}],
            },
        ),
    })
    with HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=transport,
    ) as c:
        resp = c.send_message(
            "ses_abc",
            parts=[{"type": "text", "text": "Say hi"}],
        )
    assert resp["info"]["role"] == "assistant"
    assert resp["parts"][0]["text"] == "hi"


@pytest.mark.unit
def test_messages_returns_list():
    """messages() returns the real MessageV2.WithParts[] envelope from the server."""
    transport = _mock_transport({
        ("GET", "/session/ses_abc/message"): (
            200,
            [
                {
                    "info": {
                        "id": "msg_1",
                        "role": "user",
                        "sessionID": "ses_abc",
                        "time": {"created": 1713600000},
                    },
                    "parts": [{"type": "text", "text": "hi"}],
                },
                {
                    "info": {
                        "id": "msg_2",
                        "role": "assistant",
                        "sessionID": "ses_abc",
                        "time": {"created": 1713600001},
                    },
                    "parts": [{"type": "text", "text": "hello"}],
                },
            ],
        ),
    })
    with HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=transport,
    ) as c:
        msgs = c.messages("ses_abc")
    assert len(msgs) == 2
    # Real shape: role lives under info, not at top level.
    assert msgs[0]["info"]["role"] == "user"
    assert msgs[1]["info"]["role"] == "assistant"
    assert msgs[0]["parts"][0]["text"] == "hi"


@pytest.mark.unit
def test_delete_session_returns_true():
    transport = _mock_transport({
        ("DELETE", "/session/ses_abc"): (200, True),
    })
    with HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=transport,
    ) as c:
        assert c.delete_session("ses_abc") is True


@pytest.mark.unit
def test_create_session_sends_directory_as_query_param():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_1"})

    transport = httpx.MockTransport(handler)
    with HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=transport,
    ) as c:
        c.create_session(directory="/tmp/x")
    assert seen[0].url.params.get("directory") == "/tmp/x"
    # Directory must NOT appear in the body (Zod would strip it).
    body = json.loads(seen[0].content) if seen[0].content else {}
    assert "directory" not in body


@pytest.mark.unit
def test_create_session_includes_parent_id_camelcased():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_1"})

    transport = httpx.MockTransport(handler)
    with HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=transport,
    ) as c:
        c.create_session(directory="/tmp/x", parent_id="ses_parent")
    assert seen[0].url.params.get("directory") == "/tmp/x"
    body = json.loads(seen[0].content)
    assert body == {"parentID": "ses_parent"}


@pytest.mark.unit
def test_send_message_uses_nested_model_object():
    """send_message() sends model as a nested object matching server PromptInput shape."""
    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        return httpx.Response(
            200,
            json={"info": {"role": "assistant"}, "parts": []},
        )

    transport = httpx.MockTransport(handler)
    with HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=transport,
    ) as c:
        c.send_message(
            "ses_abc",
            parts=[{"type": "text", "text": "hi"}],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )
    body = json.loads(seen[0])
    assert body["parts"] == [{"type": "text", "text": "hi"}]
    assert body["model"] == {"modelID": "claude-4-7", "providerID": "anthropic"}
    assert body["agent"] == "default"
    # Must NOT include flat keys (would be stripped by Zod, silently ignoring model selection).
    assert "modelID" not in body
    assert "providerID" not in body


@pytest.mark.unit
def test_create_session_directory_sent_as_query_param():
    """directory travels as ?directory=... not in the body (server's CreateInput strips body directory)."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_new"})

    transport = httpx.MockTransport(handler)
    with HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=transport,
    ) as c:
        c.create_session(directory="/workspace/myproject")

    req = seen[0]
    assert req.url.params.get("directory") == "/workspace/myproject"
    body = json.loads(req.content) if req.content else {}
    assert "directory" not in body


@pytest.mark.unit
def test_delete_session_handles_204():
    """Server may return 204 No Content for delete — driver should return True."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/session/ses_abc"
        return httpx.Response(204, content=b"")

    transport = httpx.MockTransport(handler)
    with HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=transport,
    ) as c:
        result = c.delete_session("ses_abc")
    # 204 → _delete returns None → delete_session returns True (None is "no error")
    assert result is True
