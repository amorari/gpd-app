"""Unit tests for HTTPClient wrappers over /permission/* and /question/*.

TDD for G3.5. These tests pin the wire contract for the sidecar routes:

  - GET  /permission                       -> list pending permissions
  - POST /permission/{requestID}/reply     -> body {reply, message?}
  - GET  /question                         -> list pending questions
  - POST /question/{requestID}/reply       -> body {answers: string[][]}
  - POST /question/{requestID}/reject      -> no body

Routes are thin — the server is authoritative — so we assert method + path +
body shape + response passthrough. The server's zod validators stripping
unknown fields is a product concern (tested in @opencode-ai), not here.
"""
from __future__ import annotations

import json

import httpx
import pytest

from gpd_tests.drivers.opencode_http import HTTPClient


def _client(**kwargs) -> HTTPClient:
    return HTTPClient(base_url="http://x", username="u", password="p", **kwargs)


# ---------------------------------------------------------------------------
# /permission
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_permissions_list_returns_array():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[])

    c = _client(transport=httpx.MockTransport(handler))
    result = c.permissions()

    assert seen[0].method == "GET"
    assert seen[0].url.path == "/permission"
    assert result == []


@pytest.mark.unit
def test_permissions_list_returns_full_request_shape():
    """Server returns Permission.Request[] — driver must not mangle it."""
    payload = [
        {
            "id": "permission_01ABC",
            "sessionID": "session_01DEF",
            "permission": "bash",
            "patterns": ["rm -rf *"],
            "metadata": {"cwd": "/tmp"},
            "always": [],
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    c = _client(transport=httpx.MockTransport(handler))
    result = c.permissions()
    assert isinstance(result, list)
    assert result[0]["id"] == "permission_01ABC"
    assert result[0]["permission"] == "bash"
    assert result[0]["patterns"] == ["rm -rf *"]


@pytest.mark.unit
def test_permission_reply_once_sends_correct_body():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    ok = c.permission_reply("permission_01ABC", reply="once")
    assert ok is True
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/permission/permission_01ABC/reply"
    body = json.loads(seen[0].content)
    assert body == {"reply": "once"}


@pytest.mark.unit
def test_permission_reply_reject_with_message_sends_message():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    c.permission_reply("permission_01ABC", reply="reject", message="too dangerous")
    body = json.loads(seen[0].content)
    assert body == {"reply": "reject", "message": "too dangerous"}


@pytest.mark.unit
def test_permission_reply_always_omits_message_when_absent():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    c.permission_reply("permission_01ABC", reply="always")
    body = json.loads(seen[0].content)
    assert "message" not in body, "message must be absent when caller didn't pass one"
    assert body == {"reply": "always"}


@pytest.mark.unit
def test_permission_reply_rejects_invalid_reply_value():
    """Driver must guard against a typo reaching the server.

    Server enforces z.enum(['once','always','reject']); catching it client-side
    gives a clearer error and avoids burning a round-trip for an impossible
    payload.
    """
    c = _client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=True)))
    with pytest.raises(ValueError):
        c.permission_reply("permission_01ABC", reply="approve")  # type: ignore[arg-type]


@pytest.mark.unit
def test_permission_reply_404_raises():
    c = _client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(404, json={"error": "not found"})
        )
    )
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        c.permission_reply("permission_missing", reply="once")
    assert exc_info.value.response.status_code == 404


# ---------------------------------------------------------------------------
# /question
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_questions_list_returns_array():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[])

    c = _client(transport=httpx.MockTransport(handler))
    result = c.questions()
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/question"
    assert result == []


@pytest.mark.unit
def test_questions_list_returns_full_request_shape():
    """Mirrors Question.Request — array of questions with options."""
    payload = [
        {
            "id": "question_01ABC",
            "sessionID": "session_01DEF",
            "questions": [
                {
                    "question": "Which provider should I use?",
                    "header": "provider",
                    "options": [
                        {"label": "Anthropic", "description": "Claude"},
                        {"label": "OpenAI", "description": "GPT"},
                    ],
                }
            ],
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    c = _client(transport=httpx.MockTransport(handler))
    result = c.questions()
    assert isinstance(result, list)
    q = result[0]
    assert q["id"] == "question_01ABC"
    assert q["questions"][0]["options"][0]["label"] == "Anthropic"


@pytest.mark.unit
def test_question_reply_sends_answers_array_of_arrays():
    """Contract: answers is string[][] — one array of selected labels per question."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    ok = c.question_reply("question_01ABC", answers=[["Anthropic"]])
    assert ok is True
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/question/question_01ABC/reply"
    body = json.loads(seen[0].content)
    assert body == {"answers": [["Anthropic"]]}


@pytest.mark.unit
def test_question_reply_multiselect_sends_multiple_labels():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    c.question_reply("question_01ABC", answers=[["a", "b"], ["c"]])
    body = json.loads(seen[0].content)
    assert body == {"answers": [["a", "b"], ["c"]]}


@pytest.mark.unit
def test_question_reply_rejects_flat_string_list():
    """Catch a common mistake: passing answers=['a','b'] instead of [['a'],['b']]."""
    c = _client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=True))
    )
    with pytest.raises((TypeError, ValueError)):
        c.question_reply("question_01ABC", answers=["Anthropic"])  # type: ignore[list-item]


@pytest.mark.unit
def test_question_reject_sends_post_with_no_body():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    ok = c.question_reject("question_01ABC")
    assert ok is True
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/question/question_01ABC/reject"
    # Body may be empty or "{}" — server has no json validator on this route.
    body = seen[0].content
    assert body in (b"", b"null", b"{}"), f"unexpected body on reject: {body!r}"


@pytest.mark.unit
def test_question_reject_404_raises():
    c = _client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(404, json={"error": "not found"})
        )
    )
    with pytest.raises(httpx.HTTPStatusError):
        c.question_reject("question_missing")
