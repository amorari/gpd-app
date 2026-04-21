"""Unit tests for HTTPClient SSE parsing + sidecar discovery helpers + remaining
error paths (G9.4 coverage-expansion).

Covers the tail of gpd_tests/drivers/opencode_http.py not hit by earlier test
files:

- ``_iter_sse_events`` edge cases (malformed JSON frames, partial frames,
  ``data:`` without a leading space, multi-line ``data:`` accumulation).
- ``discover_sidecar_port`` (pid-given alive / pid-given dead / pid-missing
  via ``pgrep``, timeout, multiple PIDs).
- ``discover_sidecar_credentials`` + ``_extract_env`` (env extraction /
  missing password).
- ``_pid_alive`` (both branches + exception swallow).
- ``_probe_port_once`` (pgrep-empty, lsof returns no LISTEN line, lsof
  returns ``127.0.0.1:PORT (LISTEN)`` line).
- Misc driver branches not hit elsewhere: ``sessions(directory=...)``,
  ``path_info``, ``_post``/``_patch`` text-body branches, ``send_message``
  / ``prompt_async`` XOR validator, ``get_project`` missing path,
  ``create_workspace`` with ``id``, every MCP / experimental flag wrapper,
  ``set_experimental_flag`` validators, ``question_reply`` validators,
  ``control_auth_set`` 204 branch.

Everything is harness-only; no live sidecar. All HTTP calls go through
``httpx.MockTransport`` and all ``subprocess.run`` calls are
``monkeypatch``-ed.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

import httpx
import pytest

from gpd_tests.drivers import opencode_http
from gpd_tests.drivers.opencode_http import HTTPClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(**kwargs: Any) -> HTTPClient:
    return HTTPClient(
        base_url="http://127.0.0.1:9999",
        username="u",
        password="p",
        **kwargs,
    )


class _FakeCompletedProcess:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = ""


# ---------------------------------------------------------------------------
# _iter_sse_events — edge cases
# ---------------------------------------------------------------------------


def _sse_bytes(s: str) -> bytes:
    return s.encode()


@pytest.mark.unit
def test_sse_invalid_json_frame_is_skipped_not_fatal():
    """A ``data:`` frame whose body isn't valid JSON must be silently dropped.

    Rationale: the opencode server today emits only JSON frames, but the
    parser is spec-compliant — stray bytes mid-stream must not crash the
    consumer. Covers the JSONDecodeError branch (driver.py ~line 799).
    """
    raw = (
        b"data: not-json-at-all\n\n"
        b"data: " + json.dumps({"payload": {"type": "good"}}).encode() + b"\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=raw, headers={"content-type": "text/event-stream"}
        )

    c = _client(transport=httpx.MockTransport(handler))
    with c.global_event_stream() as stream:
        evs = list(stream)
    assert len(evs) == 1
    assert evs[0]["payload"]["type"] == "good"


@pytest.mark.unit
def test_sse_partial_frame_at_stream_close_is_dropped():
    """A trailing ``data:`` line with no terminating blank line is discarded.

    Matches EventSource semantics. No exception should escape the stream iter.
    """
    raw = (
        b"data: "
        + json.dumps({"payload": {"type": "first"}}).encode()
        + b"\n\n"
        + b"data: {\"payload\": {\"type\": \"truncated\"}"  # no closing \n\n
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=raw, headers={"content-type": "text/event-stream"}
        )

    c = _client(transport=httpx.MockTransport(handler))
    with c.global_event_stream() as stream:
        evs = list(stream)
    assert len(evs) == 1
    assert evs[0]["payload"]["type"] == "first"


@pytest.mark.unit
def test_sse_data_line_without_leading_space_preserved():
    """``data:{json}`` (no leading space) must parse identically to
    ``data: {json}``. Covers the ``if value.startswith(' ')`` branch.
    """
    raw = b"data:" + json.dumps({"payload": {"x": 1}}).encode() + b"\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=raw, headers={"content-type": "text/event-stream"}
        )

    c = _client(transport=httpx.MockTransport(handler))
    with c.global_event_stream() as stream:
        evs = list(stream)
    assert evs == [{"payload": {"x": 1}}]


@pytest.mark.unit
def test_sse_multi_line_data_is_joined_with_newline():
    """Per SSE spec, consecutive ``data:`` lines accumulate, joined by \\n."""
    # Two data lines that together form a JSON array.
    raw = b"data: [1,\ndata: 2,3]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=raw, headers={"content-type": "text/event-stream"}
        )

    c = _client(transport=httpx.MockTransport(handler))
    with c.global_event_stream() as stream:
        evs = list(stream)
    # "[1,\n2,3]" is valid JSON.
    assert evs == [[1, 2, 3]]


@pytest.mark.unit
def test_sse_unknown_field_lines_are_ignored():
    """Lines starting with ``event:`` / ``id:`` / ``retry:`` are non-data and
    must not be accumulated. They should be silently skipped.
    """
    raw = (
        b"event: message\n"
        b"id: 42\n"
        b"retry: 1000\n"
        b"data: " + json.dumps({"payload": {"k": "v"}}).encode() + b"\n"
        b"\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=raw, headers={"content-type": "text/event-stream"}
        )

    c = _client(transport=httpx.MockTransport(handler))
    with c.global_event_stream() as stream:
        evs = list(stream)
    assert evs == [{"payload": {"k": "v"}}]


# ---------------------------------------------------------------------------
# discover_sidecar_port + helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_probe_port_once_with_given_pid_returns_port_from_lsof(monkeypatch):
    """When pid is supplied, ``_probe_port_once`` skips pgrep and runs lsof."""
    calls: list[list[str]] = []

    def fake_run(argv, capture_output=True, text=True, check=False, **_):
        calls.append(argv)
        assert argv[0] == "lsof"
        return _FakeCompletedProcess(
            stdout=(
                "COMMAND  PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
                "node   12345 me  20u IPv4   0     0t0   TCP 127.0.0.1:61234 (LISTEN)\n"
            ),
            returncode=0,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    port = opencode_http._probe_port_once(pid=12345)
    assert port == 61234
    assert calls[0][0] == "lsof"
    # pgrep must NOT have been invoked when pid is supplied.
    assert not any(c[0] == "pgrep" for c in calls)


@pytest.mark.unit
def test_probe_port_once_no_pid_uses_pgrep_then_lsof(monkeypatch):
    """No pid → pgrep picks the first opencode-cli pid, lsof resolves port."""
    commands: list[str] = []

    def fake_run(argv, capture_output=True, text=True, check=False, **_):
        commands.append(argv[0])
        if argv[0] == "pgrep":
            return _FakeCompletedProcess(stdout="777\n888\n", returncode=0)
        if argv[0] == "lsof":
            assert "777" in argv, "lsof must be invoked with the first pgrep pid"
            return _FakeCompletedProcess(
                stdout="node 777 me 20u IPv4 TCP 127.0.0.1:55555 (LISTEN)\n",
                returncode=0,
            )
        raise AssertionError(f"unexpected command {argv[0]}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    port = opencode_http._probe_port_once(pid=None)
    assert port == 55555
    assert commands == ["pgrep", "lsof"]


@pytest.mark.unit
def test_probe_port_once_pgrep_empty_raises(monkeypatch):
    def fake_run(argv, capture_output=True, text=True, check=False, **_):
        if argv[0] == "pgrep":
            return _FakeCompletedProcess(stdout="", returncode=1)
        raise AssertionError("should not reach lsof when pgrep is empty")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="opencode-cli not running"):
        opencode_http._probe_port_once(pid=None)


@pytest.mark.unit
def test_probe_port_once_lsof_without_listen_line_raises(monkeypatch):
    """lsof runs successfully but no line contains 127.0.0.1:PORT → raise."""

    def fake_run(argv, capture_output=True, text=True, check=False, **_):
        return _FakeCompletedProcess(stdout="irrelevant line\n", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="no listening port found for pid"):
        opencode_http._probe_port_once(pid=7777)


@pytest.mark.unit
def test_probe_port_once_strips_parenthesized_state(monkeypatch):
    """lsof appends ``(LISTEN)`` to the port token — that must be stripped."""

    def fake_run(argv, capture_output=True, text=True, check=False, **_):
        return _FakeCompletedProcess(
            stdout="node 1 me 20u IPv4 TCP 127.0.0.1:60000(LISTEN)\n",
            returncode=0,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert opencode_http._probe_port_once(pid=1) == 60000


@pytest.mark.unit
def test_discover_sidecar_port_returns_immediately_when_probe_succeeds(monkeypatch):
    """Happy path through the retry loop: first probe wins."""
    monkeypatch.setattr(
        opencode_http, "_pid_alive", lambda pid: True
    )
    monkeypatch.setattr(
        opencode_http, "_probe_port_once", lambda *, pid: 65432
    )
    # timeout_s irrelevant; we should return before sleeping.
    assert opencode_http.discover_sidecar_port(pid=42) == 65432


@pytest.mark.unit
def test_discover_sidecar_port_rediscovers_when_pid_dead(monkeypatch):
    """If the supplied pid is not alive, the next iteration must probe without
    it (so pgrep finds the respawned sidecar).
    """
    alive_calls: list[int] = []

    def fake_alive(pid: int) -> bool:
        alive_calls.append(pid)
        return False  # the old pid is dead

    probe_args: list[int | None] = []

    def fake_probe(*, pid):
        probe_args.append(pid)
        # Succeed on the first attempt with rediscovered pid.
        return 60006

    monkeypatch.setattr(opencode_http, "_pid_alive", fake_alive)
    monkeypatch.setattr(opencode_http, "_probe_port_once", fake_probe)

    port = opencode_http.discover_sidecar_port(pid=999)
    assert port == 60006
    # After seeing the pid is dead, the driver must call _probe_port_once
    # with pid=None so pgrep rediscovers.
    assert probe_args[0] is None
    assert alive_calls == [999]


@pytest.mark.unit
def test_discover_sidecar_port_retries_then_succeeds(monkeypatch):
    """First probe raises; second probe succeeds → return the port."""
    monkeypatch.setattr(opencode_http, "_pid_alive", lambda pid: True)
    calls = {"n": 0}

    def fake_probe(*, pid):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("not ready yet")
        return 61111

    monkeypatch.setattr(opencode_http, "_probe_port_once", fake_probe)
    # discover_sidecar_port imports ``time`` at call-time; patch time.sleep
    # so the retry loop doesn't actually wait 0.25s between iterations.
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda _: None)

    assert opencode_http.discover_sidecar_port(pid=5, timeout_s=5.0) == 61111
    assert calls["n"] == 2


@pytest.mark.unit
def test_discover_sidecar_port_timeout_raises(monkeypatch):
    """If every probe raises for the full timeout, the final error is surfaced."""
    monkeypatch.setattr(opencode_http, "_pid_alive", lambda pid: True)

    def always_fail(*, pid):
        raise RuntimeError("still no port")

    monkeypatch.setattr(opencode_http, "_probe_port_once", always_fail)

    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="no listening port after"):
        # Very small timeout so the loop exits quickly even with the no-op sleep.
        opencode_http.discover_sidecar_port(pid=5, timeout_s=0.01)


# ---------------------------------------------------------------------------
# _pid_alive
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pid_alive_true_when_kill_returns_zero(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _FakeCompletedProcess(returncode=0),
    )
    assert opencode_http._pid_alive(1234) is True


@pytest.mark.unit
def test_pid_alive_false_when_kill_returns_nonzero(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _FakeCompletedProcess(returncode=1),
    )
    assert opencode_http._pid_alive(1234) is False


@pytest.mark.unit
def test_pid_alive_swallows_exception(monkeypatch):
    def boom(*a, **k):
        raise OSError("broken pipe")

    monkeypatch.setattr(subprocess, "run", boom)
    # Must NOT propagate — _pid_alive returns False instead.
    assert opencode_http._pid_alive(1234) is False


# ---------------------------------------------------------------------------
# discover_sidecar_credentials + _extract_env
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_discover_sidecar_credentials_reads_env(monkeypatch):
    def fake_run(argv, capture_output=True, text=True, check=False, **_):
        assert argv[0] == "ps"
        # `ps -E -ww -p PID` output: pid + TTY + STAT + TIME + COMMAND + env vars
        stdout = (
            "  PID TTY      STAT      TIME COMMAND\n"
            "12345 ??     S     0:00.01 opencode-cli serve "
            "OPENCODE_SERVER_USERNAME=alice "
            "OPENCODE_SERVER_PASSWORD=s3cret "
            "HOME=/Users/alice\n"
        )
        return _FakeCompletedProcess(stdout=stdout, returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    user, pw = opencode_http.discover_sidecar_credentials(12345)
    assert user == "alice"
    assert pw == "s3cret"


@pytest.mark.unit
def test_discover_sidecar_credentials_defaults_username_to_opencode(monkeypatch):
    """Username missing from env → fall back to literal 'opencode'."""

    def fake_run(*a, **k):
        return _FakeCompletedProcess(
            stdout="PID TTY ... OPENCODE_SERVER_PASSWORD=hunter2 OTHER=y\n",
            returncode=0,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    user, pw = opencode_http.discover_sidecar_credentials(1)
    assert user == "opencode"
    assert pw == "hunter2"


@pytest.mark.unit
def test_discover_sidecar_credentials_missing_password_raises(monkeypatch):
    def fake_run(*a, **k):
        return _FakeCompletedProcess(
            stdout="PID TTY ... OPENCODE_SERVER_USERNAME=nobody\n",
            returncode=0,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="OPENCODE_SERVER_PASSWORD not found"):
        opencode_http.discover_sidecar_credentials(1)


@pytest.mark.unit
def test_extract_env_returns_value_up_to_next_space():
    blob = "A=1 FOO=bar BAR=baz\n"
    assert opencode_http._extract_env(blob, "FOO") == "bar"


@pytest.mark.unit
def test_extract_env_returns_value_to_end_when_last_token():
    # No trailing space after the value — extract to end of string.
    blob = " OTHER=1 OPENCODE_SERVER_PASSWORD=lastvalue"
    assert (
        opencode_http._extract_env(blob, "OPENCODE_SERVER_PASSWORD") == "lastvalue"
    )


@pytest.mark.unit
def test_extract_env_missing_key_returns_none():
    assert opencode_http._extract_env(" FOO=1", "BAR") is None


# ---------------------------------------------------------------------------
# HTTPClient small-surface uncovered branches
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sessions_with_directory_passes_query_param():
    """``sessions(directory=...)`` takes a different branch than bare sessions."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[{"id": "ses_1"}])

    c = _client(transport=httpx.MockTransport(handler))
    out = c.sessions(directory="/tmp/x")
    assert out == [{"id": "ses_1"}]
    assert seen[0].url.params.get("directory") == "/tmp/x"


@pytest.mark.unit
def test_path_info_returns_dict():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/path"
        return httpx.Response(200, json={"cwd": "/tmp"})

    c = _client(transport=httpx.MockTransport(handler))
    assert c.path_info() == {"cwd": "/tmp"}


@pytest.mark.unit
def test_post_with_text_body_returns_text():
    """_post: non-JSON body, content-type text/plain → returns r.text."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Use a route that reaches _post: abort is a parameterless POST.
        return httpx.Response(
            200, content=b"plain response", headers={"content-type": "text/plain"}
        )

    c = _client(transport=httpx.MockTransport(handler))
    # abort() routes through _post and must return the plain-text body verbatim.
    assert c.abort("ses_abc") == "plain response"


@pytest.mark.unit
def test_patch_returns_text_when_not_json():
    """_patch: content-type is not json AND body doesn't look like json."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"ok", headers={"content-type": "text/plain"}
        )

    c = _client(transport=httpx.MockTransport(handler))
    # patch_session routes through _patch.
    out = c.patch_session("ses_abc", {"title": "t"})
    assert out == "ok"


@pytest.mark.unit
def test_patch_204_returns_none():
    """_patch: 204 No Content → None."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, content=b"")

    c = _client(transport=httpx.MockTransport(handler))
    assert c.patch_session("ses_abc", {"title": "t"}) is None


@pytest.mark.unit
def test_send_message_requires_model_and_provider_together():
    c = _client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    with pytest.raises(ValueError, match="provided together"):
        c.send_message("ses", parts=[], model_id="m")  # missing provider
    with pytest.raises(ValueError, match="provided together"):
        c.send_message("ses", parts=[], provider_id="p")  # missing model


@pytest.mark.unit
def test_prompt_async_requires_model_and_provider_together():
    c = _client(
        transport=httpx.MockTransport(lambda r: httpx.Response(204, content=b""))
    )
    with pytest.raises(ValueError, match="provided together"):
        c.prompt_async("ses", parts=[], model_id="m")
    with pytest.raises(ValueError, match="provided together"):
        c.prompt_async("ses", parts=[], provider_id="p")


@pytest.mark.unit
def test_get_project_returns_match_or_none():
    """Cover both branches of get_project."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"id": "prj_a", "worktree": "/tmp/a"},
                {"id": "prj_b", "worktree": "/tmp/b"},
            ],
        )

    c = _client(transport=httpx.MockTransport(handler))
    match = c.get_project("prj_b")
    assert match is not None
    assert match["id"] == "prj_b"

    # Missing id → None.
    missing = c.get_project("prj_nope")
    assert missing is None


@pytest.mark.unit
def test_create_workspace_includes_id_when_supplied():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "wsp_new"})

    c = _client(transport=httpx.MockTransport(handler))
    c.create_workspace(type="worktree", id="wsp_custom")
    body = json.loads(seen[0].content)
    assert body["id"] == "wsp_custom"
    assert body["type"] == "worktree"


# ---------------------------------------------------------------------------
# /mcp wrappers (shape-only, they all are one-liners over _get/_post)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_mcp_servers_gets_mcp_path():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"srv": {"connected": True}})

    c = _client(transport=httpx.MockTransport(handler))
    out = c.list_mcp_servers()
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/mcp"
    assert out == {"srv": {"connected": True}}


@pytest.mark.unit
def test_invoke_mcp_tool_posts_arguments_wrapper():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"result": "ok"})

    c = _client(transport=httpx.MockTransport(handler))
    out = c.invoke_mcp_tool("srv", "tool", {"k": "v"})
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/mcp/srv/tool/tool"
    body = json.loads(seen[0].content)
    assert body == {"arguments": {"k": "v"}}
    assert out == {"result": "ok"}


@pytest.mark.unit
def test_invoke_mcp_tool_none_args_sent_as_empty_dict():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    c.invoke_mcp_tool("srv", "tool", None)  # type: ignore[arg-type]
    body = json.loads(seen[0].content)
    assert body == {"arguments": {}}


@pytest.mark.unit
def test_connect_mcp_server_posts_connect_path():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    c.connect_mcp_server("foo")
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/mcp/foo/connect"


@pytest.mark.unit
def test_disconnect_mcp_server_posts_disconnect_path():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    c.disconnect_mcp_server("foo")
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/mcp/foo/disconnect"


# ---------------------------------------------------------------------------
# /experimental flags & friends
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_experimental_flags_hits_console_endpoint():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"accountID": "acc", "orgID": "org"})

    c = _client(transport=httpx.MockTransport(handler))
    out = c.get_experimental_flags()
    assert seen[0].url.path == "/experimental/console"
    assert out["accountID"] == "acc"


@pytest.mark.unit
def test_list_experimental_tool_ids_returns_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/experimental/tool/ids"
        return httpx.Response(200, json=["bash", "edit"])

    c = _client(transport=httpx.MockTransport(handler))
    assert c.list_experimental_tool_ids() == ["bash", "edit"]


@pytest.mark.unit
def test_list_experimental_resources_returns_dict():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/experimental/resource"
        return httpx.Response(200, json={"uri://foo": {"mime": "text/plain"}})

    c = _client(transport=httpx.MockTransport(handler))
    assert c.list_experimental_resources() == {"uri://foo": {"mime": "text/plain"}}


@pytest.mark.unit
def test_set_experimental_flag_console_posts_switch():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=True)

    c = _client(transport=httpx.MockTransport(handler))
    c.set_experimental_flag("console", {"accountID": "a", "orgID": "o"})
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/experimental/console/switch"
    body = json.loads(seen[0].content)
    assert body == {"accountID": "a", "orgID": "o"}


@pytest.mark.unit
def test_set_experimental_flag_console_missing_fields_raises():
    c = _client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=True))
    )
    # Missing orgID.
    with pytest.raises(ValueError, match="missing fields"):
        c.set_experimental_flag("console", {"accountID": "a"})


@pytest.mark.unit
def test_set_experimental_flag_unknown_key_raises():
    c = _client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=True))
    )
    with pytest.raises(ValueError, match="unknown experimental flag"):
        c.set_experimental_flag("nosuch", {"x": 1})


# ---------------------------------------------------------------------------
# question_reply — type validators
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_question_reply_rejects_non_list_top_level():
    c = _client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=True))
    )
    with pytest.raises(TypeError, match="answers must be list"):
        c.question_reply("q", answers="not a list")  # type: ignore[arg-type]


@pytest.mark.unit
def test_question_reply_rejects_non_string_label():
    c = _client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=True))
    )
    with pytest.raises(ValueError, match="must be str"):
        c.question_reply("q", answers=[[123]])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# control_auth_set — 204 No Content branch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_control_auth_set_204_returns_true():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/auth/anthropic"
        return httpx.Response(204, content=b"")

    c = _client(transport=httpx.MockTransport(handler))
    assert c.control_auth_set("anthropic", {"type": "api", "key": "k"}) is True
