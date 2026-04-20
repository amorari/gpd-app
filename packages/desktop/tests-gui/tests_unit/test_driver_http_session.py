"""Shape-only tests for HTTPClient session helpers. No live GPD required."""
from __future__ import annotations

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
    transport = _mock_transport({
        ("GET", "/session/ses_abc/message"): (
            200,
            [{"id": "msg_1", "role": "user"}, {"id": "msg_2", "role": "assistant"}],
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
    assert {m["role"] for m in msgs} == {"user", "assistant"}


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
