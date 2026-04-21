"""Unit tests for session-route HTTPClient wrappers added in Phase G3.1.

These cover the Priority-1 uncovered `/session/*` routes identified in
`docs/coverage-expansion/inventory/sidecar-routes.md`:

  * GET    /session/:sessionID              -> get_session()
  * GET    /session/:sessionID/children     -> session_children()
  * GET    /session/:sessionID/diff         -> get_session_diff()
  * GET    /session/:sessionID/message/:messageID -> get_message()
  * GET    /session/status                  -> session_status()
  * PATCH  /session/:sessionID              -> patch_session()
  * POST   /session/:sessionID/fork         -> fork_session()
  * POST   /session/:sessionID/revert       -> revert_message()
  * POST   /session/:sessionID/unrevert     -> unrevert_session()
  * POST   /session/:sessionID/prompt_async -> prompt_async() (returns 204 -> None)
  * DELETE /session/:sessionID/message/:messageID -> delete_message()

Shape-only; all requests are handled by httpx.MockTransport. No live sidecar.
"""
from __future__ import annotations

import json

import httpx
import pytest

from gpd_tests.drivers.opencode_http import HTTPClient


def _client(handler):
    return HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        transport=httpx.MockTransport(handler),
    )


# ----- GET /session/:sessionID ------------------------------------------------


@pytest.mark.unit
def test_get_session_returns_info():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/session/ses_abc"
        return httpx.Response(
            200,
            json={"id": "ses_abc", "directory": "/tmp/x", "version": 1},
        )

    with _client(handler) as c:
        info = c.get_session("ses_abc")
    assert info["id"] == "ses_abc"


@pytest.mark.unit
def test_get_session_404_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    with _client(handler) as c:
        with pytest.raises(httpx.HTTPStatusError) as exc:
            c.get_session("ses_missing")
    assert exc.value.response.status_code == 404


# ----- GET /session/:sessionID/children ---------------------------------------


@pytest.mark.unit
def test_session_children_returns_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/session/ses_parent/children"
        return httpx.Response(
            200,
            json=[{"id": "ses_child1"}, {"id": "ses_child2"}],
        )

    with _client(handler) as c:
        kids = c.session_children("ses_parent")
    assert [k["id"] for k in kids] == ["ses_child1", "ses_child2"]


# ----- GET /session/status ----------------------------------------------------


@pytest.mark.unit
def test_session_status_returns_dict():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/session/status"
        return httpx.Response(200, json={"ses_1": {"status": "idle"}})

    with _client(handler) as c:
        s = c.session_status()
    assert "ses_1" in s
    assert s["ses_1"]["status"] == "idle"


# ----- PATCH /session/:sessionID ----------------------------------------------


@pytest.mark.unit
def test_patch_session_sends_title_update():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={"id": "ses_abc", "title": "new title"},
        )

    with _client(handler) as c:
        resp = c.patch_session("ses_abc", {"title": "new title"})
    assert seen[0].method == "PATCH"
    assert seen[0].url.path == "/session/ses_abc"
    body = json.loads(seen[0].content)
    assert body == {"title": "new title"}
    assert resp["title"] == "new title"


@pytest.mark.unit
def test_patch_session_supports_time_archived():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_abc"})

    with _client(handler) as c:
        c.patch_session("ses_abc", {"time": {"archived": 1234567890}})
    body = json.loads(seen[0].content)
    assert body == {"time": {"archived": 1234567890}}


# ----- POST /session/:sessionID/fork ------------------------------------------


@pytest.mark.unit
def test_fork_session_posts_message_id_camelcased():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_fork"})

    with _client(handler) as c:
        out = c.fork_session("ses_src", after_message_id="msg_1")
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/session/ses_src/fork"
    body = json.loads(seen[0].content)
    # ForkInput (minus sessionID) uses `messageID` (camelCase).
    assert body == {"messageID": "msg_1"}
    assert out["id"] == "ses_fork"


@pytest.mark.unit
def test_fork_session_without_message_sends_empty_body():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_fork"})

    with _client(handler) as c:
        c.fork_session("ses_src")
    # Server's ForkInput makes messageID optional — body must not contain it
    # when omitted (Zod would accept but we prefer omission over null).
    body = json.loads(seen[0].content) if seen[0].content else {}
    assert body == {}


# ----- GET /session/:sessionID/diff -------------------------------------------


@pytest.mark.unit
def test_get_session_diff_with_message_id():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json=[{"path": "foo.txt", "before": "a", "after": "b"}],
        )

    with _client(handler) as c:
        diff = c.get_session_diff("ses_abc", message_id="msg_1")
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/session/ses_abc/diff"
    assert seen[0].url.params.get("messageID") == "msg_1"
    assert diff[0]["path"] == "foo.txt"


@pytest.mark.unit
def test_get_session_diff_without_message_id_omits_param():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[])

    with _client(handler) as c:
        c.get_session_diff("ses_abc")
    # server requires messageID as a query, but the driver shouldn't silently
    # inject a value. Caller decides.
    assert "messageID" not in seen[0].url.params


# ----- GET /session/:sessionID/message/:messageID ----------------------------


@pytest.mark.unit
def test_get_message_returns_info_and_parts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/session/ses_abc/message/msg_1"
        return httpx.Response(
            200,
            json={
                "info": {"id": "msg_1", "role": "user"},
                "parts": [{"type": "text", "text": "hi"}],
            },
        )

    with _client(handler) as c:
        m = c.get_message("ses_abc", "msg_1")
    assert m["info"]["id"] == "msg_1"
    assert m["parts"][0]["text"] == "hi"


# ----- POST /session/:sessionID/revert ----------------------------------------


@pytest.mark.unit
def test_revert_message_posts_message_id():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_abc"})

    with _client(handler) as c:
        out = c.revert_message("ses_abc", message_id="msg_1")
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/session/ses_abc/revert"
    body = json.loads(seen[0].content)
    assert body == {"messageID": "msg_1"}
    assert out["id"] == "ses_abc"


@pytest.mark.unit
def test_revert_message_with_part_id_included():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_abc"})

    with _client(handler) as c:
        c.revert_message("ses_abc", message_id="msg_1", part_id="part_1")
    body = json.loads(seen[0].content)
    assert body == {"messageID": "msg_1", "partID": "part_1"}


# ----- POST /session/:sessionID/unrevert --------------------------------------


@pytest.mark.unit
def test_unrevert_session_posts_empty_body():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "ses_abc"})

    with _client(handler) as c:
        out = c.unrevert_session("ses_abc")
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/session/ses_abc/unrevert"
    assert out["id"] == "ses_abc"


# ----- POST /session/:sessionID/prompt_async ---------------------------------


@pytest.mark.unit
def test_prompt_async_returns_none_on_204():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204, content=b"")

    with _client(handler) as c:
        out = c.prompt_async(
            "ses_abc",
            parts=[{"type": "text", "text": "ping"}],
        )
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/session/ses_abc/prompt_async"
    body = json.loads(seen[0].content)
    assert body["parts"] == [{"type": "text", "text": "ping"}]
    assert out is None


@pytest.mark.unit
def test_prompt_async_sends_nested_model_like_send_message():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204, content=b"")

    with _client(handler) as c:
        c.prompt_async(
            "ses_abc",
            parts=[{"type": "text", "text": "ping"}],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )
    body = json.loads(seen[0].content)
    assert body["model"] == {"modelID": "claude-4-7", "providerID": "anthropic"}
    assert body["agent"] == "default"


# ----- DELETE /session/:sessionID/message/:messageID --------------------------


@pytest.mark.unit
def test_delete_message_returns_true():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/session/ses_abc/message/msg_1"
        return httpx.Response(200, json=True)

    with _client(handler) as c:
        assert c.delete_message("ses_abc", "msg_1") is True


@pytest.mark.unit
def test_delete_message_handles_204():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, content=b"")

    with _client(handler) as c:
        # None body -> returns True (no error).
        assert c.delete_message("ses_abc", "msg_1") is True


# ----- Delete session on nonexistent id surfaces 404 --------------------------


@pytest.mark.unit
def test_delete_session_404_raises_httpx_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    with _client(handler) as c:
        with pytest.raises(httpx.HTTPStatusError) as exc:
            c.delete_session("ses_ghost")
    assert exc.value.response.status_code == 404
