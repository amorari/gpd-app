"""Unit coverage for gpd_tests.pages.app_state.

All subprocess / os.kill / socket / MCP access is monkeypatched — nothing
interacts with a real GPD install.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gpd_tests.pages import app_state as mod


# --- tiny helpers ----------------------------------------------------------


def _cp(stdout: str = "", returncode: int = 0) -> SimpleNamespace:
    """Build a stand-in for subprocess.CompletedProcess."""
    return SimpleNamespace(stdout=stdout, returncode=returncode, stderr="")


class _RunRouter:
    """Route subprocess.run calls by the first argv token.

    Callers register handlers keyed on argv[0] (e.g. ``pgrep``, ``kill``,
    ``ps``, ``open``, ``osascript``). Each handler takes the full argv list
    and returns a SimpleNamespace with ``stdout``/``returncode``.

    Recorded calls are available on ``.calls`` (list[tuple[argv, kwargs]]).
    """

    def __init__(self) -> None:
        self.handlers: dict[str, callable] = {}
        self.calls: list[tuple[list[str], dict]] = []

    def bind(self, tool: str, fn):
        self.handlers[tool] = fn
        return self

    def __call__(self, argv, *args, **kwargs):
        self.calls.append((list(argv), dict(kwargs)))
        tool = argv[0]
        if tool in self.handlers:
            return self.handlers[tool](argv)
        # Safe default: exit 0 with empty stdout.
        return _cp("", 0)


# --- _pgrep / is_running ---------------------------------------------------


@pytest.mark.unit
def test_pgrep_parses_multiple_pids(monkeypatch):
    # ps -ax -o pid=,command= output: "PID command" per line
    ps_out = "1234 /path/to/anything/proc\n5678 /other/anything/proc\nabc  not-a-pid\n"
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *a, **kw: _cp(ps_out, 0),
    )
    assert mod._pgrep("anything") == [1234, 5678]


@pytest.mark.unit
def test_gpd_pid_returns_first(monkeypatch):
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **kw: _ps_with_pids(111, 222)
    )
    assert mod.AppState().gpd_pid() == 111


@pytest.mark.unit
def test_gpd_pid_none_when_empty(monkeypatch):
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **kw: _cp("", 0)
    )
    assert mod.AppState().gpd_pid() is None


# --- sidecar_pid -----------------------------------------------------------


@pytest.mark.unit
def test_sidecar_pid_none_when_no_sidecar_running(monkeypatch):
    # ps returns lines with no matching pattern
    router = _RunRouter().bind("ps", lambda argv: _cp("1 /usr/bin/some-other-proc\n", 0))
    monkeypatch.setattr(mod.subprocess, "run", router)
    assert mod.AppState().sidecar_pid() is None


@pytest.mark.unit
def test_sidecar_pid_returns_first_when_no_launched_parent(monkeypatch):
    # With no _launched_pid set, fall back to the first matching sidecar.
    ps_out = "9001 opencode-cli --print-logs serve\n9002 opencode-cli --print-logs serve\n"
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **kw: _cp(ps_out, 0)
    )
    assert mod.AppState().sidecar_pid() == 9001


@pytest.mark.unit
def test_sidecar_pid_picks_child_of_launched_pid(monkeypatch):
    ps_out = "4001 opencode-cli --print-logs serve\n4002 opencode-cli --print-logs serve\n"

    def run(argv, *a, **kw):
        tool = argv[0]
        if tool == "ps" and "-ax" in argv:
            return _cp(ps_out, 0)
        if tool == "ps":
            # ps -o ppid= -p <pid>
            pid = int(argv[-1])
            # 4002 is the real child; 4001 has an unrelated parent.
            return _cp("1\n" if pid == 4001 else "7777\n", 0)
        return _cp("", 0)

    monkeypatch.setattr(mod.subprocess, "run", run)
    s = mod.AppState()
    s._launched_pid = 7777
    assert s.sidecar_pid() == 4002


@pytest.mark.unit
def test_sidecar_pid_returns_none_when_ppid_lookup_fails_for_all(monkeypatch):
    ps_out = "5001 opencode-cli --print-logs serve\n5002 opencode-cli --print-logs serve\n"

    def run(argv, *a, **kw):
        if "-ax" in argv:
            return _cp(ps_out, 0)
        if argv[0] == "ps":
            return _cp("\n", 0)  # non-digit ppid output
        return _cp("", 0)

    monkeypatch.setattr(mod.subprocess, "run", run)
    s = mod.AppState()
    s._launched_pid = 9999
    assert s.sidecar_pid() is None


@pytest.mark.unit
def test_sidecar_pid_swallows_exceptions_from_ps(monkeypatch):
    ps_out = "6001 opencode-cli --print-logs serve\n6002 opencode-cli --print-logs serve\n"
    state = {"ppid_calls": 0}

    def run(argv, *a, **kw):
        if "-ax" in argv:
            return _cp(ps_out, 0)
        if argv[0] == "ps":
            state["ppid_calls"] += 1
            if state["ppid_calls"] == 1:
                raise OSError("boom")
            return _cp("4242\n", 0)
        return _cp("", 0)

    monkeypatch.setattr(mod.subprocess, "run", run)
    s = mod.AppState()
    s._launched_pid = 4242
    assert s.sidecar_pid() == 6002


# --- kill_stale ------------------------------------------------------------


def _ps_empty(argv):
    """ps -ax returning no matching processes."""
    return _cp("1 /sbin/launchd\n", 0)


def _ps_with_pids(*pids):
    """ps -ax returning rows that match the module's _PGREP_PATTERN."""
    lines = "\n".join(f"{p} {mod._PGREP_PATTERN}GPD" for p in pids) + "\n"
    return _cp(lines, 0)


@pytest.mark.unit
def test_kill_stale_noop_when_already_dead(monkeypatch):
    router = _RunRouter()
    router.bind("ps", lambda argv: _ps_empty(argv))
    router.bind("kill", lambda argv: _cp("", 0))
    monkeypatch.setattr(mod.subprocess, "run", router)
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: True)
    killed: list[int] = []
    monkeypatch.setattr(mod.os, "kill", lambda pid, sig: killed.append(pid))
    mod.AppState().kill_stale()
    assert killed == []


@pytest.mark.unit
def test_kill_stale_sigterm_sufficient(monkeypatch):
    """ps returns pids; wait_until succeeds → no SIGKILL escalation."""
    def ps_both_patterns(argv):
        # Return matching rows for both _PGREP_PATTERN and opencode-cli.*serve.
        lines = (
            f"101 {mod._PGREP_PATTERN}GPD\n"
            f"102 {mod._PGREP_PATTERN}GPD\n"
            "101 opencode-cli --print-logs serve\n"
            "102 opencode-cli --print-logs serve\n"
        )
        return _cp(lines, 0)

    router = _RunRouter()
    router.bind("ps", ps_both_patterns)
    router.bind("kill", lambda argv: _cp("", 0))
    monkeypatch.setattr(mod.subprocess, "run", router)
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: True)
    killed: list[int] = []
    monkeypatch.setattr(mod.os, "kill", lambda pid, sig: killed.append(pid))
    mod.AppState().kill_stale()
    kill_invocations = [c for c in router.calls if c[0][0] == "kill"]
    # Two patterns × two pids = four TERM calls.
    assert len(kill_invocations) == 4
    assert killed == []  # no SIGKILL since wait_until succeeded


@pytest.mark.unit
def test_kill_stale_escalates_to_sigkill(monkeypatch, capsys):
    def ps_both(argv):
        lines = (
            f"555 {mod._PGREP_PATTERN}GPD\n"
            f"556 {mod._PGREP_PATTERN}GPD\n"
            "555 opencode-cli --print-logs serve\n"
            "556 opencode-cli --print-logs serve\n"
        )
        return _cp(lines, 0)

    router = _RunRouter()
    router.bind("ps", ps_both)
    router.bind("kill", lambda argv: _cp("", 0))
    monkeypatch.setattr(mod.subprocess, "run", router)

    state = {"n": 0}

    def fake_wait(pred, **kw):
        state["n"] += 1
        return state["n"] >= 2

    monkeypatch.setattr(mod, "wait_until", fake_wait)
    killed: list[int] = []
    monkeypatch.setattr(mod.os, "kill", lambda pid, sig: killed.append(pid))
    mod.AppState().kill_stale()
    out = capsys.readouterr().out
    assert "SIGKILL" in out
    assert killed  # non-empty


@pytest.mark.unit
def test_kill_stale_sigkill_swallows_process_lookup_error(monkeypatch):
    router = _RunRouter()
    router.bind("ps", lambda argv: _ps_with_pids(900))
    router.bind("kill", lambda argv: _cp("", 0))
    monkeypatch.setattr(mod.subprocess, "run", router)
    state = {"n": 0}

    def fake_wait(pred, **kw):
        state["n"] += 1
        return state["n"] >= 2

    monkeypatch.setattr(mod, "wait_until", fake_wait)
    monkeypatch.setattr(mod.os, "kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError(pid)))
    mod.AppState().kill_stale()


@pytest.mark.unit
def test_kill_stale_raises_when_sigkill_insufficient(monkeypatch):
    router = _RunRouter()
    router.bind("ps", lambda argv: _ps_with_pids(200))
    router.bind("kill", lambda argv: _cp("", 0))
    monkeypatch.setattr(mod.subprocess, "run", router)
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: False)
    monkeypatch.setattr(mod.os, "kill", lambda pid, sig: None)
    with pytest.raises(TimeoutError, match="still alive after SIGKILL"):
        mod.AppState().kill_stale()


# --- launch ----------------------------------------------------------------


@pytest.mark.unit
def test_launch_always_foreground(monkeypatch):
    """launch() uses `open -a` without -g so the webview is always active."""
    calls: list[list[str]] = []

    def run(argv, *a, **kw):
        calls.append(list(argv))
        if argv[0] == "ps":
            return _ps_with_pids(8080)
        return _cp("", 0)

    monkeypatch.setattr(mod.subprocess, "run", run)
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: True)
    s = mod.AppState()
    s.launch()
    open_calls = [c for c in calls if c[0] == "open"]
    assert open_calls, "expected an `open` call"
    assert "-g" not in open_calls[0], "-g must not be present (foreground launch required in VM)"
    assert s._launched_pid == 8080


@pytest.mark.unit
def test_launch_times_out_when_not_running(monkeypatch):
    """wait_until returns False → raises RuntimeError with pids captured."""

    def run(argv, *a, **kw):
        if argv[0] == "ps":
            return _cp("1 /sbin/launchd\n", 0)  # no matching pids
        return _cp("", 0)

    monkeypatch.setattr(mod.subprocess, "run", run)
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: False)
    with pytest.raises(RuntimeError, match=r"GPD failed to launch within"):
        mod.AppState().launch()


@pytest.mark.unit
def test_launch_timeout_message_includes_stale_pids(monkeypatch):
    def run(argv, *a, **kw):
        if argv[0] == "ps":
            return _ps_with_pids(77, 88)  # pids exist but predicate stub lies
        return _cp("", 0)

    monkeypatch.setattr(mod.subprocess, "run", run)
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: False)
    with pytest.raises(RuntimeError) as exc_info:
        mod.AppState().launch()
    assert "77,88" in str(exc_info.value)


# --- quit / wait_quit ------------------------------------------------------


@pytest.mark.unit
def test_quit_sends_osascript_and_clears_launched_pid(monkeypatch):
    calls: list[list[str]] = []

    def run(argv, *a, **kw):
        calls.append(list(argv))
        return _cp("", 0)

    monkeypatch.setattr(mod.subprocess, "run", run)
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: True)
    s = mod.AppState()
    s._launched_pid = 1234
    s.quit()
    assert any(c[0] == "osascript" for c in calls)
    assert s._launched_pid is None


@pytest.mark.unit
def test_wait_quit_raises_on_timeout(monkeypatch):
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **kw: _ps_with_pids(42)
    )
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: False)
    with pytest.raises(TimeoutError, match="did not quit"):
        mod.AppState().wait_quit(timeout_s=0.01)


@pytest.mark.unit
def test_wait_quit_success(monkeypatch):
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: _cp("1 /sbin/launchd\n", 0))
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: True)
    assert mod.AppState().wait_quit(timeout_s=0.01) is None


# --- refresh_launched_pid --------------------------------------------------


@pytest.mark.unit
def test_refresh_launched_pid_rebinds(monkeypatch):
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **kw: _ps_with_pids(5150)
    )
    s = mod.AppState()
    assert s._launched_pid is None
    s.refresh_launched_pid()
    assert s._launched_pid == 5150


# --- wait_launched ---------------------------------------------------------


@pytest.mark.unit
def test_wait_launched_raises_when_not_ready(monkeypatch):
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **kw: _cp("1 /sbin/launchd\n", 0)
    )
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: False)
    with pytest.raises(TimeoutError, match="did not reach a running"):
        mod.AppState().wait_launched(timeout_s=0.01)


@pytest.mark.unit
def test_wait_launched_success_rebinds_pid(monkeypatch):
    """wait_until succeeds → refresh_launched_pid is invoked."""
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **kw: _ps_with_pids(4242)
    )
    monkeypatch.setattr(mod, "wait_until", lambda pred, **kw: True)
    s = mod.AppState()
    s.wait_launched(timeout_s=0.01)
    assert s._launched_pid == 4242


@pytest.mark.unit
def test_wait_launched_ready_predicate_paths(monkeypatch, tmp_path):
    """Exercise the internal ``_ready`` predicate through its three branches:
    not-running, socket-missing, socket-present+ping-ok, and auth-error→ready.
    """
    import gpd_tests.drivers.mcp as mcp_mod

    # Capture the predicate passed to wait_until so we can drive it.
    captured: dict[str, callable] = {}

    def wait_stub(pred, **kw):
        captured["pred"] = pred
        return True

    monkeypatch.setattr(mod, "wait_until", wait_stub)

    # State toggles for a fresh AppState per scenario. We'll share the test
    # body across scenarios by mutating closures.
    running_flag = {"v": False}
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *a, **kw: _ps_with_pids(7) if running_flag["v"] else _cp("1 /sbin/launchd\n", 0),
    )

    sock_path = str(tmp_path / "sock")
    # app_state imports _discover_socket_path at module load, so patch it
    # on the app_state module namespace (not the mcp module).
    monkeypatch.setattr(mod, "_discover_socket_path", lambda: sock_path)

    class _PingClient:
        behavior = "ok"

        def __init__(self, *a, **kw):
            pass

        def ping(self):
            if _PingClient.behavior == "ok":
                return None
            raise RuntimeError(_PingClient.behavior)

    monkeypatch.setattr(mcp_mod, "MCPClient", _PingClient)

    s = mod.AppState()
    # Kick off wait_launched to capture the predicate (wait_until is stubbed
    # True so this completes immediately; refresh_launched_pid then runs).
    s.wait_launched(timeout_s=0.01)
    pred = captured["pred"]

    # 1) Not running → False.
    running_flag["v"] = False
    assert pred() is False

    # 2) Running + socket file missing → False.
    running_flag["v"] = True
    assert pred() is False

    # 3) Socket exists + ping ok → True.
    open(sock_path, "w").close()
    _PingClient.behavior = "ok"
    assert pred() is True

    # 4) Socket exists + ping raises unrelated error → False.
    _PingClient.behavior = "something unrelated"
    assert pred() is False

    # 5) Socket exists + ping raises auth-ish error → True (treated as ready).
    _PingClient.behavior = "unauthorized: bad token"
    assert pred() is True

    # 6) _discover_socket_path raises FileNotFoundError → False.
    def raise_fnf():
        raise FileNotFoundError("gone")

    monkeypatch.setattr(mod, "_discover_socket_path", raise_fnf)
    assert pred() is False


# --- _APP_NAME / _PGREP_PATTERN derivation ---------------------------------


@pytest.mark.unit
def test_default_app_path_respects_env(monkeypatch):
    monkeypatch.setenv("GPD_APP_PATH", "/tmp/GPD Dev.app")
    assert mod._default_app_path() == "/tmp/GPD Dev.app"


@pytest.mark.unit
def test_default_app_path_fallback(monkeypatch):
    monkeypatch.delenv("GPD_APP_PATH", raising=False)
    assert mod._default_app_path() == "/Applications/GPD.app"
