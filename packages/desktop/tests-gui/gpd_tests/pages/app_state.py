"""GPD application-lifecycle helpers."""
from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from pathlib import Path

from gpd_tests.drivers.mcp import _discover_socket_path
from gpd_tests.helpers.timings import wait_until

def _default_app_path() -> str:
    """Resolve the GPD app bundle path.

    Order:
      1. GPD_APP_PATH env override
      2. Installed /Applications/GPD.app (production)
      3. In-tree debug build  (packages/desktop/src-tauri/target/debug/bundle/macos/GPD Dev.app)
      4. In-tree release build (…/release/…/GPD.app)
    """
    if env := os.environ.get("GPD_APP_PATH"):
        return env

    prod = "/Applications/GPD.app"
    if os.path.exists(prod):
        return prod

    # Walk up from this file to the repo root and probe the Tauri bundle dirs.
    here = Path(__file__).resolve()
    # gpd_tests/pages/app_state.py → tests-gui → desktop → packages → repo root
    desktop = here.parents[3]
    bundle_base = desktop / "src-tauri" / "target"
    for variant, name in [("debug", "GPD Dev.app"), ("release", "GPD.app")]:
        candidate = bundle_base / variant / "bundle" / "macos" / name
        if candidate.exists():
            return str(candidate)

    return prod  # fall back; will fail loudly if missing


APP_PATH = _default_app_path()

# Derive app name (bundle label) from the .app path: "GPD Dev" or "GPD".
# NOTE: the binary inside Tauri's bundle uses `mainBinaryName`, not the product
# name — debug builds ship `GPD Dev.app/Contents/MacOS/GPD` (no " Dev"). Match
# on the MacOS/ directory prefix so we don't have to replicate Tauri's naming.
_APP_NAME = Path(APP_PATH).stem
# Include the binary name so we match only the GPD main process and not the
# opencode-cli sidecar (which also lives under Contents/MacOS/).
_PGREP_PATTERN = f"{_APP_NAME}.app/Contents/MacOS/GPD"


# PPID-scoped MCP-server cleanup: kills only children of the dying sidecar,
# never a live same-user GPD instance's MCP servers. Keep the pattern in sync
# with scripts/reset.py::_MCP_SERVERS_PATTERN.
#
# Pattern anchors on `-m gpd.mcp.servers`, not a bare basename, to avoid
# false-matches on pytest invocations whose argv happens to contain
# `gpd.mcp.servers`. `python\S*` tolerates `python`, `python3`,
# `python3.11`, and full-path interpreter forms the venv may expose.
_MCP_SERVERS_PATTERN = r"python\S*\s+-m\s+gpd\.mcp\.servers"


def _pgrep(pattern: str) -> list[int]:
    # macOS pgrep -f silently fails when the pattern contains spaces
    # (e.g. "GPD Dev.app/Contents/MacOS/"). Use ps and filter in Python.
    # -ww disables argv truncation so long venv paths + module names don't
    # silently drop off the right edge and produce false negatives.
    out = subprocess.run(
        ["ps", "-ax", "-ww", "-o", "pid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        pid_str, command = parts
        if pid_str.isdigit() and re.search(pattern, command):
            pids.append(int(pid_str))
    return pids


def _ppid_of(pid: int) -> int | None:
    """Return parent PID of `pid`, or None if lookup fails."""
    try:
        out = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    raw = out.stdout.strip()
    return int(raw) if raw.isdigit() else None


def _mcp_children_of(parent_pids: set[int]) -> list[int]:
    """Snapshot MCP-server PIDs whose PPID is in `parent_pids`.

    Scoped kill — only children of a known dying sidecar get signaled.
    Prevents friendly-fire on a live same-user GPD instance and prevents
    the respawn race where newly-spawned children of a fresh sidecar get
    killed by a stale pattern-match loop.
    """
    if not parent_pids:
        return []
    out: list[int] = []
    for pid in _pgrep(_MCP_SERVERS_PATTERN):
        parent = _ppid_of(pid)
        if parent is not None and parent in parent_pids:
            out.append(pid)
    return out


def _mcp_launchd_orphans() -> list[int]:
    """Return MCP-server PIDs currently reparented to launchd (PPID=1).

    Closes the late-spawn race: if the sidecar spawned a fresh MCP child
    between ``_mcp_children_of()`` snapshot and sidecar death, the child
    missed the snapshot and is now an orphan under launchd. A live
    same-user GPD instance's MCP children still have their live sidecar
    as PPID, not 1, so this filter is clean for the live case.

    NOTE: assumes a single concurrent GPD test session. Parallel pytest
    runs are already rejected by ``pytest_configure`` (xdist → UsageError
    in tests-gui/conftest.py), and a crashed dev GPD leaving launchd
    orphans would in practice also want those cleaned up. If parallel
    sessions ever become supported, switch to a per-run PID tag.
    """
    out: list[int] = []
    for pid in _pgrep(_MCP_SERVERS_PATTERN):
        parent = _ppid_of(pid)
        if parent == 1:
            out.append(pid)
    return out


def _proc_state(pid: int) -> str | None:
    """Return the single-char ps state for `pid`, or None if lookup fails.

    Used to skip zombies in `_proc_alive`: on macOS `os.kill(pid, 0)` still
    succeeds for <defunct> processes, which would make the kill loop waste
    its full SIGTERM budget before a redundant SIGKILL attempt.
    """
    try:
        out = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    s = out.stdout.strip()
    return s[:1] if s else None


def _proc_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # On macOS `kill(pid, 0)` succeeds for zombies — filter them out here
    # so the SIGTERM/SIGKILL cycle terminates immediately once a child is
    # reaped by its (re)parent.
    return _proc_state(pid) != "Z"


def _proc_matches(pid: int, pattern: str) -> bool:
    """Return True iff `pid`'s current argv still matches `pattern`.

    Guard against PID-reuse between SIGTERM and SIGKILL: if the original
    process exited and the OS recycled the PID for an unrelated program,
    the command field will no longer match and we must not signal it.
    """
    try:
        out = subprocess.run(
            ["ps", "-ww", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    cmd = out.stdout.strip()
    if not cmd:
        return False
    return bool(re.search(pattern, cmd))


def _kill_snapshot(
    pids: list[int],
    *,
    term_timeout_s: float = 2.0,
    verify_pattern: str | None = None,
) -> None:
    """SIGTERM `pids`, wait `term_timeout_s`, SIGKILL survivors.

    Operates on a frozen PID list rather than re-querying by pattern, so no
    newly-spawned replacement process can accidentally be signaled. When
    `verify_pattern` is set, each survivor is re-checked against it before
    SIGKILL to defeat PID reuse during the escalation window. Default is
    `None` (no reuse guard) so callers must explicitly opt in — mirrors
    reset.py's `_kill_snapshot` signature to avoid drift.
    """
    if not pids:
        return
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    step = 0.1
    elapsed = 0.0
    while elapsed < term_timeout_s:
        if not any(_proc_alive(p) for p in pids):
            return
        time.sleep(step)
        elapsed += step
    for pid in pids:
        if not _proc_alive(pid):
            continue
        if verify_pattern is not None and not _proc_matches(pid, verify_pattern):
            # PID has been recycled to an unrelated process — do not signal.
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


class AppState:
    def __init__(self) -> None:
        self._launched_pid: int | None = None

    def is_running(self) -> bool:
        return bool(_pgrep(_PGREP_PATTERN))

    def gpd_pid(self) -> int | None:
        pids = _pgrep(_PGREP_PATTERN)
        return pids[0] if pids else None

    def sidecar_pid(self) -> int | None:
        """Return the opencode-cli serve pid.

        Preference order:
        1. A sidecar whose PPID matches ``_launched_pid`` (the Popen PID).
        2. A sidecar whose PPID matches *any* currently-running GPD process.
           Needed after quit+relaunch when macOS ``open -a`` spawns a second
           GPD process (PID B) and the sidecar is parented to B while
           ``_launched_pid`` still holds the original Popen PID (A).
        3. ``pids[0]`` — after ``wait_launched()`` confirmed the sidecar is
           healthy, there is exactly one sidecar and it is ours.  Falling back
           here avoids returning None when PPID tracking breaks entirely.
        """
        pids = _pgrep("opencode-cli.*serve")
        if not pids:
            return None

        # Collect the set of all live GPD process PIDs for step-2 matching.
        gpd_pids = set(_pgrep(_PGREP_PATTERN))

        # Step 1 + 2: check PPID of each sidecar candidate.
        step1_match: int | None = None
        step2_match: int | None = None
        for pid in pids:
            try:
                out = subprocess.run(
                    ["ps", "-o", "ppid=", "-p", str(pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                ppid_raw = out.stdout.strip()
                if not ppid_raw.isdigit():
                    continue
                ppid = int(ppid_raw)
                if self._launched_pid is not None and ppid == self._launched_pid:
                    step1_match = pid
                    break  # Best possible match — stop searching.
                if ppid in gpd_pids and step2_match is None:
                    step2_match = pid
            except Exception:
                continue

        if step1_match is not None:
            return step1_match
        if step2_match is not None:
            return step2_match
        # Step 3: PPID matching failed entirely — return the only known sidecar.
        return pids[0]

    def kill_stale(self) -> None:
        """Terminate any leftover GPD / opencode-cli / MCP-server processes.

        MCP-server cleanup is PPID-scoped: snapshot the children of the
        currently-running opencode-cli sidecars BEFORE signaling anything,
        then kill only that frozen set. Prevents two failure modes flagged
        in review:
        - Friendly fire: a live same-user GPD instance in another
          workspace / `/Applications/GPD.app` does not get its MCP
          children SIGKILLed by a global regex match.
        - Respawn race: once the sidecar dies and a fresh one is starting,
          a pattern-based alive() loop would re-match the new sidecar's
          freshly-spawned children and kill them; PID-set tracking can't.
        """
        sidecar_pids = set(_pgrep("opencode-cli.*serve"))
        mcp_snapshot = _mcp_children_of(sidecar_pids)
        for pattern in (_PGREP_PATTERN, "opencode-cli.*serve"):
            for pid in _pgrep(pattern):
                subprocess.run(
                    ["kill", "-TERM", str(pid)],
                    capture_output=True,
                    check=False,
                )
        # Poll after SIGTERM on GPD + sidecar; escalate to SIGKILL if any
        # remain. MCP snapshot is handled by _kill_snapshot below with its
        # own SIGTERM/SIGKILL cycle scoped to the frozen PID list.
        alive = lambda: bool(
            _pgrep(_PGREP_PATTERN) or _pgrep("opencode-cli.*serve")
        )
        if not wait_until(lambda: not alive(), timeout_s=3.0):
            survivors: list[int] = []
            for pattern in (_PGREP_PATTERN, "opencode-cli.*serve"):
                survivors.extend(_pgrep(pattern))
            print(
                f"kill_stale: escalating to SIGKILL for pids {survivors}"
            )
            for pid in survivors:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if not wait_until(lambda: not alive(), timeout_s=5.0):
                raise TimeoutError(
                    "kill_stale: processes still alive after SIGKILL"
                )
        # GPD + sidecar are gone; reap the MCP children parented to the
        # sidecar we just killed, plus any late-spawned children that
        # missed the snapshot and reparented to launchd.
        kill_list = list({*mcp_snapshot, *_mcp_launchd_orphans()})
        _kill_snapshot(kill_list, verify_pattern=_MCP_SERVERS_PATTERN)

    def launch(self) -> None:
        """Launch GPD as a detached process and record the exact PID.

        Using open -a can produce a late second process when it silently
        succeeds exit-code-wise but lags behind a Popen fallback, creating
        two GPD instances whose PPIDs confuse sidecar_pid(). Launching via
        Popen directly avoids the race and gives us proc.pid immediately.
        """
        binary = Path(APP_PATH) / "Contents" / "MacOS" / "GPD"
        if not binary.exists():
            binary_dir = Path(APP_PATH) / "Contents" / "MacOS"
            candidates = [
                f for f in binary_dir.iterdir()
                if f.is_file() and f.name != "opencode-cli"
            ]
            if not candidates:
                raise RuntimeError(f"No binary found in {binary_dir}")
            binary = candidates[0]
        proc = subprocess.Popen(
            [str(binary)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._launched_pid = proc.pid
        timeout_s = 10.0
        ok = wait_until(lambda: self.is_running(), timeout_s=timeout_s)
        if not ok:
            pids = _pgrep(_PGREP_PATTERN)
            pids_str = ",".join(str(p) for p in pids) if pids else "none"
            raise RuntimeError(
                f"GPD failed to launch within {timeout_s}s "
                f"(matching pids: {pids_str})"
            )
        # Bring the app to the foreground so the webview is active.
        # open -a on an already-running app activates the existing window
        # without spawning a second process — safe to call here.
        subprocess.run(
            ["open", "-a", APP_PATH],
            capture_output=True,
            check=False,
        )

    def quit(self) -> None:
        # Graceful quit via osascript. Bound the wait: if GPD is showing a
        # native modal (NSOpenPanel, unsaved-changes sheet, etc.), osascript
        # blocks forever — that deadlocks pytest because the thread-method
        # test timeout cannot interrupt a blocking subprocess call. If the
        # graceful path times out, SIGTERM then SIGKILL the PIDs directly.
        #
        # Snapshot the sidecar + its MCP-server children BEFORE issuing
        # the quit. Without this, session teardown under PYTEST_QUIT_GPD=1
        # (conftest.py:464) leaves ~8 × ~65 MB Python procs orphaned to
        # launchd per run.
        sidecar_pids = set(_pgrep("opencode-cli.*serve"))
        mcp_snapshot = _mcp_children_of(sidecar_pids)
        try:
            subprocess.run(
                ["osascript", "-e", f'tell application "{_APP_NAME}" to quit'],
                capture_output=True,
                check=False,
                timeout=8.0,
            )
        except subprocess.TimeoutExpired:
            pass

        if not wait_until(lambda: not self.is_running(), timeout_s=5.0):
            pids = _pgrep(_PGREP_PATTERN)
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            if not wait_until(lambda: not self.is_running(), timeout_s=3.0):
                pids = _pgrep(_PGREP_PATTERN)
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

        self.wait_quit()
        # Pair the pre-quit snapshot with a post-quit launchd-orphan sweep
        # to cover MCP children spawned after the snapshot.
        kill_list = list({*mcp_snapshot, *_mcp_launchd_orphans()})
        _kill_snapshot(kill_list, verify_pattern=_MCP_SERVERS_PATTERN)
        self._launched_pid = None

    def refresh_launched_pid(self) -> None:
        """Re-bind parent/PPID tracking to the currently-running GPD.

        Call after any out-of-band restart (restart_app, tier reset, manual
        relaunch) so sidecar_pid() keeps matching against the live process
        instead of a stale PID.
        """
        self._launched_pid = self.gpd_pid()

    def wait_launched(self, *, timeout_s: float = 20.0) -> None:
        from gpd_tests.drivers.mcp import MCPClient, MCPError, MCPTimeout

        def _mcp_ready() -> bool:
            if not self.is_running():
                return False
            try:
                sock = _discover_socket_path()
            except FileNotFoundError:
                return False
            if not os.path.exists(sock):
                return False
            # Socket file alone isn't proof: after restart it can persist
            # while the new GPD instance is still starting. Probe via ping.
            # An auth-related rejection proves the peer is alive and speaking
            # MCP — treat it as ready. The mcp fixture handles token setup.
            try:
                MCPClient(socket_path=sock, timeout_s=2.0).ping()
                return True
            except Exception as e:
                msg = str(e).lower()
                if "auth" in msg or "token" in msg or "unauthoriz" in msg:
                    return True
                return False

        ok = wait_until(_mcp_ready, timeout_s=timeout_s)
        if not ok:
            raise TimeoutError(
                "GPD did not reach a running+socket state in time"
            )
        # Rebind parent-PID tracking so sidecar_pid() matches the live tree
        # after restart/reset/manual relaunch.
        self.refresh_launched_pid()

        # Wait for the opencode-cli sidecar to start.  The MCP socket being
        # available only means the Tauri host is ready; the sidecar spawns
        # asynchronously and may lag by several seconds on first launch.
        # Tests that call http.rediscover() after a relaunch need sidecar_pid()
        # to return a live PID, so we gate here rather than forcing every test
        # to implement its own wait.
        sidecar_ok = wait_until(
            lambda: self.sidecar_pid() is not None,
            timeout_s=15.0,
        )
        if not sidecar_ok:
            raise TimeoutError(
                "opencode-cli sidecar did not start within 15s of GPD launch"
            )

        # Wait for the webview JS bridge to be STABLY responsive.
        # MCP ping only proves the socket listener is up; execute_js routes
        # through the webview which mounts asynchronously.  On a cold start,
        # the webview has a brief transient window (during SolidJS hydration)
        # where execute_js succeeds for 1-2 calls then times out again.
        # Requiring 3 consecutive successes filters out that transient state
        # and ensures tests never trigger execute_js before it is truly ready.
        #
        # Recovery: if the bridge is dead because the webview was left at
        # tauri://localhost/ from a previous run (cross-protocol navigation
        # breaks Tauri IPC bridge injection in cfg(dev) mode), a one-time
        # redirect to the devUrl (http://localhost:1420) restores the bridge
        # immediately without a full GPD restart.
        _consecutive_ok = [0]
        _bridge_recovery_attempted = [False]
        _bridge_fail_count = [0]
        _RECOVERY_AFTER_FAILURES = 10  # ~20s at poll_s=2.0

        def _js_bridge_ready() -> bool:
            try:
                MCPClient(timeout_s=3.0).execute_js("null")
                _consecutive_ok[0] += 1
                return _consecutive_ok[0] >= 3
            except (FileNotFoundError, ConnectionRefusedError):
                _consecutive_ok[0] = 0
                _bridge_fail_count[0] += 1
            except MCPTimeout:
                _consecutive_ok[0] = 0
                _bridge_fail_count[0] += 1
            except MCPError as e:
                msg = str(e).lower()
                if "timeout" in msg:
                    _consecutive_ok[0] = 0
                    _bridge_fail_count[0] += 1
                else:
                    # Non-timeout MCPError (e.g. auth): bridge replied — count it.
                    _consecutive_ok[0] += 1
                    return _consecutive_ok[0] >= 3
            except Exception:
                _consecutive_ok[0] = 0
                _bridge_fail_count[0] += 1

            # After repeated failures, try once to redirect to the devUrl.
            # This recovers from a stale tauri://localhost/ state left by a
            # prior test run (navigating back to http://localhost:1420 re-injects
            # the Tauri IPC bridge initialization scripts which are per-origin).
            if (
                not _bridge_recovery_attempted[0]
                and _bridge_fail_count[0] >= _RECOVERY_AFTER_FAILURES
            ):
                _bridge_recovery_attempted[0] = True
                try:
                    # Only redirect if the webview is currently at tauri://.
                    current = MCPClient(timeout_s=2.0).current_url()
                    if current.startswith("tauri://"):
                        MCPClient(timeout_s=5.0).navigate("http://localhost:1420")
                except Exception:
                    pass
                _consecutive_ok[0] = 0  # reset counter after recovery attempt

            return False

        js_ok = wait_until(_js_bridge_ready, timeout_s=60.0, poll_s=2.0)
        if not js_ok:
            raise TimeoutError(
                "GPD webview JS bridge (execute_js) did not reach stable "
                "responsiveness within 60s of launch"
            )

    def wait_quit(self, *, timeout_s: float = 10.0) -> None:
        ok = wait_until(lambda: not self.is_running(), timeout_s=timeout_s)
        if not ok:
            raise TimeoutError("GPD did not quit in time")
